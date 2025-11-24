# app.py — Phiên bản D+ (Admin & Investor hoàn chỉnh)
import streamlit as st
import pandas as pd
from datetime import datetime
import altair as alt
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import bcrypt

# ================== CẤU HÌNH CƠ BẢN ================== #
st.set_page_config(page_title="Quản Lý Quỹ", page_icon="📊", layout="wide")

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

@st.cache_data(ttl=300)
def read_df(ws_name):
    sh = gs_client().open_by_key(SHEET_ID)
    ws = sh.worksheet(ws_name)
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    return pd.DataFrame(values[1:], columns=values[0])

def append_row(ws_name, values):
    sh = gs_client().open_by_key(SHEET_ID)
    sh.worksheet(ws_name).append_row(values)

def update_cell(ws_name, row, col, value):
    sh = gs_client().open_by_key(SHEET_ID)
    ws = sh.worksheet(ws_name)
    ws.update_cell(row, col, value)

# ================== AUTH ================== #
from auth_module import init_users_sheet_once, signup_view, login_view
init_users_sheet_once()

st.sidebar.title("Tài khoản")
if not st.session_state.get("auth", False):
    mode = st.sidebar.radio("Chọn", ["Đăng nhập", "Đăng ký"], horizontal=True)
    if mode == "Đăng ký": signup_view()
    else: login_view()
    st.stop()

# Lấy role người dùng
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

# ================== MENU ================== #
if role == "admin":
    section = st.sidebar.selectbox("Tuỳ chọn (Admin)", [
        "Trang chủ", "Quản lý khách hàng", "Duyệt yêu cầu CCQ",
        "Cập nhật danh mục", "Quản trị nội dung"
    ])
else:
    section = st.sidebar.selectbox("Tuỳ chọn", [
        "Trang chủ", "Thông báo", "Giới thiệu", "Liên hệ", "Giao dịch",
        "Thông tin cá nhân", "Lịch sử giao dịch"
    ])

# ================== ADMIN ================== #
if role == "admin" and section == "Trang chủ":
    st.title("📊 Tổng quan toàn bộ quỹ")
    try:
        df = read_df("Tổng Quan")
        if df.empty:
            st.info("Chưa có dữ liệu Tổng Quan.")
        else:
            df.columns = [c.strip().lower() for c in df.columns]
            funds = sorted(df["fund_name"].dropna().unique())
            pick = st.selectbox("Chọn quỹ", funds)
            fund_df = df[df["fund_name"] == pick]
            st.dataframe(fund_df, use_container_width=True)
    except Exception as e:
        st.error(f"Lỗi đọc sheet: {e}")

elif role == "admin" and section == "Quản lý khách hàng":
    st.title("📂 Quản lý khách hàng")
    df_users = read_df("Users")
    if df_users.empty:
        st.info("Chưa có khách hàng.")
    else:
        st.dataframe(df_users, use_container_width=True)

elif role == "admin" and section == "Duyệt yêu cầu CCQ":
    st.title("🧾 Duyệt yêu cầu mua CCQ")
    df = read_df("YCGD")
    if df.empty:
        st.info("Không có yêu cầu.")
    else:
        df = df.fillna("")
        for i, r in df.iterrows():
            status = r["status"].strip().lower()
            with st.expander(f"{r['investor_name']} - {r['fund_name']} ({r['status']})"):
                st.write(f"Số tiền: {r['amount_vnd']}")
                st.write(f"Thời gian: {r['timestamp']}")
                if status == "pending":
                    c1, c2 = st.columns(2)
                    if c1.button("✅ Duyệt", key=f"approve_{i}"):
                        update_cell("YCGD", i+2, 5, "Chờ thanh toán")
                        update_cell("YCGD", i+2, 7, "FALSE")
                        st.success("Đã duyệt yêu cầu.")
                        st.rerun()
                    if c2.button("❌ Từ chối", key=f"reject_{i}"):
                        note = st.text_input("Lý do từ chối", key=f"note_{i}")
                        if note:
                            update_cell("YCGD", i+2, 5, "Không thành công")
                            update_cell("YCGD", i+2, 6, note)
                            update_cell("YCGD", i+2, 7, "FALSE")
                            st.warning("Đã từ chối.")
                            st.rerun()
                elif status == "chờ thanh toán":
                    if st.button("💰 Đã thanh toán", key=f"paid_{i}"):
                        update_cell("YCGD", i+2, 5, "Thành công")
                        update_cell("YCGD", i+2, 7, "FALSE")
                        append_row("Dòng tiền quỹ", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), r["fund_name"], r["amount_vnd"], "NĐT mua CCQ"])
                        st.success("Xác nhận thanh toán thành công.")
                        st.rerun()

elif role == "admin" and section == "Cập nhật danh mục":
    st.title("📈 Cập nhật danh mục đầu tư")
    fund = st.text_input("Tên quỹ")
    ticker = st.text_input("Mã CK")
    side = st.selectbox("Loại giao dịch", ["BUY", "SELL"])
    qty = st.number_input("Số lượng", min_value=0.0)
    price = st.number_input("Giá", min_value=0.0)
    fee = st.number_input("Phí", min_value=0.0)
    if st.button("Ghi giao dịch"):
        append_row("Danh mục đầu tư", [fund, ticker, side, qty, price, fee, datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
        st.success("Đã ghi giao dịch.")

elif role == "admin" and section == "Quản trị nội dung":
    st.title("⚙️ Quản trị nội dung")
    tab1, tab2, tab3 = st.tabs(["Giới thiệu", "Liên hệ", "Hướng dẫn thanh toán"])
    with tab1:
        df_cfg = read_df("Config")
        intro = ""
        if not df_cfg.empty and "intro" in df_cfg["section"].values:
            intro = df_cfg[df_cfg["section"] == "intro"]["content"].iloc[0]
        new_intro = st.text_area("Nội dung giới thiệu", intro, height=200)
        if st.button("💾 Lưu giới thiệu"):
            sh = gs_client().open_by_key(SHEET_ID).worksheet("Config")
            sh.update("B2", new_intro)
            st.success("Đã lưu nội dung.")
    with tab2:
        df_contact = read_df("Liên hệ")
        if df_contact.empty: st.info("Chưa có liên hệ.")
        else: st.dataframe(df_contact, use_container_width=True)
    with tab3:
        df_cfg = read_df("Config")
        payment = ""
        if not df_cfg.empty and "payment" in df_cfg["section"].values:
            payment = df_cfg[df_cfg["section"] == "payment"]["content"].iloc[0]
        new_payment = st.text_area("Thông tin thanh toán", payment, height=200, placeholder="Ví dụ: STK, ngân hàng, tên chủ tài khoản...")
        if st.button("💾 Lưu hướng dẫn"):
            sh = gs_client().open_by_key(SHEET_ID).worksheet("Config")
            sh.update("B3", new_payment)
            st.success("Đã cập nhật hướng dẫn thanh toán.")

# ================== NHÀ ĐẦU TƯ ================== #
elif role == "investor" and section == "Thông báo":
    st.title("🔔 Thông báo")
    try:
        df_notify = read_df("YCGD")
        username = st.session_state["username"]
        df_notify = df_notify[df_notify["investor_name"].astype(str).str.lower() == username.lower()]
        if df_notify.empty:
            st.info("Không có thông báo mới.")
        else:
            for i, row in df_notify.iterrows():
                status = row["status"].strip().lower()
                note = row.get("note", "")
                notified_col = "notified" if "notified" in df_notify.columns else None
                if status == "chờ thanh toán":
                    st.warning(f"💳 Yêu cầu mua CCQ {row['fund_name']} đã được duyệt. Vui lòng thanh toán.")
                    if st.button("📄 Xem hướng dẫn thanh toán", key=f"pay_{i}"):
                        st.session_state["section"] = "Giao dịch"
                        st.rerun()
                elif status == "thành công":
                    st.success(f"✅ Giao dịch {row['fund_name']} thành công!")
                if notified_col:
                    update_cell("YCGD", i+2, df_notify.columns.get_loc("notified")+1, "TRUE")
    except Exception as e:
        st.error(f"Lỗi tải thông báo: {e}")

elif role == "investor" and section == "Giao dịch":
    st.title("💸 Giao dịch CCQ & Hướng dẫn thanh toán")
    st.subheader("🪙 Gửi yêu cầu mua CCQ")
    investor_name = st.text_input("Tên nhà đầu tư")
    fund = st.text_input("Tên quỹ")
    amount = st.number_input("Số tiền (VND)", min_value=0.0)
    if st.button("Gửi"):
        append_row("YCGD", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), investor_name, fund, amount, "PENDING", "", "FALSE"])
        st.success("✅ Đã gửi yêu cầu, chờ duyệt.")
    st.divider()
    st.subheader("📄 Hướng dẫn thanh toán")
    try:
        df_cfg = read_df("Config")
        if not df_cfg.empty and "payment" in df_cfg["section"].values:
            pay_text = df_cfg[df_cfg["section"] == "payment"]["content"].iloc[0]
            st.info(pay_text)
        else:
            st.warning("Hiện chưa có hướng dẫn thanh toán.")
    except Exception as e:
        st.error(f"Lỗi đọc hướng dẫn: {e}")
