# app.py — Phiên bản D (hoàn chỉnh, có phân quyền admin & investor)
import streamlit as st
import pandas as pd
from datetime import datetime, date
import bcrypt
import altair as alt
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ================== CẤU HÌNH CƠ BẢN ================== #
st.set_page_config(page_title="Quản Lý Quỹ", page_icon="📊", layout="wide", initial_sidebar_state="expanded")

# --- Ẩn logo Streamlit & GitHub avatar ---
hide_ui = """
<style>
#MainMenu, header, footer {visibility: hidden !important;}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"],
section[data-testid="stBottom"], img[alt*="GitHub"], img[alt*="streamlit"] {
    display: none !important;
}
</style>
"""
st.markdown(hide_ui, unsafe_allow_html=True)

# ================== GOOGLE SHEETS ================== #
SHEET_ID = "1icpLUH3UNvMKuoB_hdiCTiwZ-tbY9aPJEOHGSfBWECY"

def gs_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    except Exception:
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=350)
def read_df(ws_name):
    sh = gs_client().open_by_key(SHEET_ID)
    ws = sh.worksheet(ws_name)
    values = ws.get_all_values()
    if not values: return pd.DataFrame()
    header, rows = values[0], values[1:]
    return pd.DataFrame(rows, columns=header)

def append_row(ws_name, values):
    sh = gs_client().open_by_key(SHEET_ID)
    sh.worksheet(ws_name).append_row(values)

def update_cell(ws_name, row, col, value):
    sh = gs_client().open_by_key(SHEET_ID)
    sh.worksheet(ws_name).update_cell(row, col, value)

# ================== AUTH ================== #
from auth_module import init_users_sheet_once, signup_view, login_view
init_users_sheet_once()

# ================== LOGIN GATE ================== #
st.sidebar.title("Tài khoản")
if not st.session_state.get("auth", False):
    mode = st.sidebar.radio("Chọn", ["Đăng nhập", "Đăng ký"], horizontal=True)
    if mode == "Đăng ký": signup_view()
    else: login_view()
    st.stop()

# Lấy thông tin role
try:
    users_df = read_df("Users")
    role = users_df.loc[
        users_df["username"] == st.session_state["username"], "role"
    ].values[0].strip().lower()
except Exception:
    role = "investor"

st.sidebar.success(f"Xin chào {st.session_state.get('username','')} ({role})!")
if st.sidebar.button("Đăng xuất"):
    for k in ["auth", "username"]:
        st.session_state.pop(k, None)
    st.rerun()

# ================== SIDEBAR MENU ================== #
if role == "admin":
    section = st.sidebar.selectbox("Tuỳ chọn (Admin)", [
        "Trang chủ", "Quản lý khách hàng", "Duyệt yêu cầu CCQ",
        "Cập nhật danh mục", "Quản trị nội dung"
    ])
else:
    section = st.sidebar.selectbox("Tuỳ chọn", [
        "Trang chủ", "Giới thiệu", "Liên hệ", "Giao dịch",
        "Thông tin cá nhân", "Lịch sử giao dịch"
    ])

# ================== PAGE: ADMIN - QUẢN LÝ KHÁCH HÀNG ================== #
if role == "admin" and section == "Quản lý khách hàng":
    st.title("📂 Quản lý khách hàng")
    df_users = read_df("Users")
    if df_users.empty:
        st.warning("Chưa có người dùng nào.")
    else:
        df_users = df_users.fillna("")
        st.dataframe(df_users, use_container_width=True)
        selected = st.selectbox("Chọn khách hàng để xem giao dịch", df_users["username"])
        if selected:
            df_txn = read_df("YCGD")
            df_txn = df_txn[df_txn["investor_name"].astype(str).str.lower() == selected.lower()]
            if df_txn.empty:
                st.info("Khách hàng này chưa có giao dịch.")
            else:
                st.dataframe(df_txn, use_container_width=True)

# ================== PAGE: ADMIN - DUYỆT YÊU CẦU CCQ ================== #
elif role == "admin" and section == "Duyệt yêu cầu CCQ":
    st.title("🧾 Duyệt yêu cầu chứng chỉ quỹ")
    df = read_df("YCGD")
    if df.empty:
        st.info("Chưa có yêu cầu nào.")
    else:
        df = df.fillna("")
        df.reset_index(inplace=True)
        for i, row in df.iterrows():
            with st.expander(f"{row['investor_name']} - {row['fund_name']} ({row['status']})"):
                st.write(f"Số tiền: {row['amount_vnd']}")
                st.write(f"Thời gian: {row['timestamp']}")
                st.write(f"Ghi chú: {row.get('note','')}")
                col1, col2, col3 = st.columns(3)
                if col1.button("✅ Duyệt", key=f"approve_{i}"):
                    update_cell("YCGD", i+2, 5, "Chờ thanh toán")
                    st.success("Đã duyệt.")
                if col2.button("💰 Đã thanh toán", key=f"paid_{i}"):
                    update_cell("YCGD", i+2, 5, "Thành công")
                    st.success("Đã xác nhận thanh toán.")
                if col3.button("❌ Từ chối", key=f"reject_{i}"):
                    note = st.text_input("Lý do từ chối:", key=f"note_{i}")
                    if note:
                        update_cell("YCGD", i+2, 5, "Không thành công")
                        update_cell("YCGD", i+2, 6, note)
                        st.warning("Đã từ chối yêu cầu.")

# ================== PAGE: ADMIN - CẬP NHẬT DANH MỤC ================== #
elif role == "admin" and section == "Cập nhật danh mục":
    st.title("📈 Cập nhật danh mục đầu tư")
    fund = st.text_input("Tên quỹ")
    ticker = st.text_input("Mã CK")
    side = st.selectbox("Loại giao dịch", ["BUY", "SELL"])
    qty = st.number_input("Số lượng", min_value=0.0)
    price = st.number_input("Giá", min_value=0.0)
    fee = st.number_input("Phí", min_value=0.0)
    if st.button("Ghi giao dịch"):
        append_row("Danh mục đầu tư", [
            fund, ticker, side, qty, price, fee,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])
        st.success("Đã ghi giao dịch.")

# ================== PAGE: ADMIN - QUẢN TRỊ NỘI DUNG ================== #
elif role == "admin" and section == "Quản trị nội dung":
    st.title("⚙️ Quản trị nội dung (Giới thiệu & Liên hệ)")
    tab1, tab2 = st.tabs(["Giới thiệu", "Liên hệ"])
    with tab1:
        st.subheader("📝 Chỉnh sửa phần Giới thiệu")
        df_cfg = read_df("Config")
        intro_text = ""
        if not df_cfg.empty:
            row = df_cfg[df_cfg["section"] == "intro"]
            if not row.empty:
                intro_text = row.iloc[0]["content"]
        new_intro = st.text_area("Nội dung", intro_text, height=200)
        if st.button("💾 Lưu"):
            sh = gs_client().open_by_key(SHEET_ID)
            ws = sh.worksheet("Config")
            ws.update("B2", new_intro)
            st.success("Đã lưu nội dung mới.")
    with tab2:
        st.subheader("📮 Liên hệ của người dùng")
        df_contact = read_df("Liên hệ")
        if df_contact.empty:
            st.info("Chưa có liên hệ nào.")
        else:
            st.dataframe(df_contact, use_container_width=True)

# ================== TRANG CỦA NHÀ ĐẦU TƯ ================== #
elif section == "Giới thiệu":
    st.title("ℹ️ Giới thiệu")
    df_cfg = read_df("Config")
    if not df_cfg.empty and "content" in df_cfg.columns:
        st.write(df_cfg[df_cfg["section"] == "intro"]["content"].iloc[0])

elif section == "Liên hệ":
    st.title("📮 Liên hệ")
    with st.form("contact_form"):
        email = st.text_input("Email")
        msg = st.text_area("Nội dung")
        ok = st.form_submit_button("Gửi")
    if ok:
        append_row("Liên hệ", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email, msg])
        st.success("✅ Đã gửi liên hệ thành công.")

elif section == "Giao dịch":
    st.title("💸 Gửi yêu cầu mua CCQ")
    investor_name = st.text_input("Tên nhà đầu tư")
    fund = st.text_input("Tên quỹ")
    amount = st.number_input("Số tiền (VND)", min_value=0.0)
    if st.button("Gửi"):
        append_row("YCGD", [
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), investor_name, fund,
            amount, "PENDING", ""
        ])
        st.success("✅ Đã gửi yêu cầu, chờ duyệt.")

elif section == "Lịch sử giao dịch":
    st.title("💹 Lịch sử giao dịch")
    df = read_df("YCGD")
    username = st.session_state["username"]
    df = df[df["investor_name"].astype(str).str.lower() == username.lower()]
    if df.empty:
        st.info("Chưa có giao dịch.")
    else:
        for _, r in df.iterrows():
            with st.expander(f"{r['fund_name']} - {r['status']}"):
                st.write(f"Số tiền: {r['amount_vnd']}")
                st.write(f"Thời gian: {r['timestamp']}")
                if r['status'] == "Chờ thanh toán":
                    st.info("💰 Vui lòng chuyển tiền theo hướng dẫn trên web quỹ.")
                elif r['status'] == "Không thành công":
                    st.warning(f"❌ Lý do: {r.get('note','Không xác định')}")
                elif r['status'] == "Thành công":
                    st.success("✅ Giao dịch hoàn tất.")
