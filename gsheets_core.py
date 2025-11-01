import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
import pandas as pd
from typing import List, Callable
SHEET_ID = "1icpLUH3UNvMKuoB_hdiCTiwZ-tbY9aPJEOHGSfBWECY"

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

