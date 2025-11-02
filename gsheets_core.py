import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
from typing import List, Callable

SHEET_ID = "1icpLUH3UNvMKuoB_hdiCTiwZ-tbY9aPJEOHGSfBWECY"


# ===== Kết nối Google Sheets (cache 1 lần cho toàn app) ===== #
@st.cache_resource
def gs_client() -> gspread.client.Client:
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # ✅ Khi chạy trên Streamlit Cloud (dùng secrets)
        gcp_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_info, scope)
    except Exception:
        # ✅ Khi chạy local (dùng file credentials.json)
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


@st.cache_resource
def open_sheet():
    """Mở Google Sheet theo ID."""
    return gs_client().open_by_key(SHEET_ID)


def retry(fn: Callable, tries=4, base_delay=0.8):
    """Retry đơn giản cho lỗi quota/429."""
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            msg = str(e)
            if "429" in msg or "Rate Limit" in msg or "quota" in msg.lower():
                time.sleep(base_delay * (2 ** i))
                continue
            raise
    raise RuntimeError("Retry hết lần mà vẫn lỗi quota.")


def ensure_headers(ws_name: str, headers: List[str]):
    """Đảm bảo hàng đầu tiên của sheet chứa header mong muốn."""
    sh = open_sheet()
    try:
        ws = retry(lambda: sh.worksheet(ws_name))
    except gspread.WorksheetNotFound:
        ws = retry(lambda: sh.add_worksheet(title=ws_name, rows="1000", cols="26"))

    current = retry(lambda: ws.row_values(1))
    want = headers
    if current[:len(want)] != want:
        retry(lambda: ws.update(f"A1:{chr(ord('A') + len(want) - 1)}1", [want]))


@st.cache_data(ttl=500)
def read_df(ws_name: str) -> pd.DataFrame:
    """Đọc dữ liệu 1 worksheet -> DataFrame"""
    sh = open_sheet()
    ws = retry(lambda: sh.worksheet(ws_name))
    data = retry(lambda: ws.get_all_records())
    return pd.DataFrame(data)


def append_row(ws_name: str, values: list):
    """Thêm 1 dòng dữ liệu mới vào cuối sheet"""
    sh = open_sheet()
    ws = retry(lambda: sh.worksheet(ws_name))
    retry(lambda: ws.append_row(values))