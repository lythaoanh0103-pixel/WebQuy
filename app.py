import json
import streamlit as st
import pandas as pd
from datetime import datetime, date
import bcrypt
import altair as alt
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ================== CẤU HÌNH CƠ BẢN ================== #
st.set_page_config(
    page_title="Quản Lý Quỹ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Ẩn toàn bộ logo, GitHub link, toolbar, footer, link web ---
hide_streamlit_ui = """
<style>
#MainMenu {visibility: hidden;}
header {visibility: hidden !important;}
footer {visibility: hidden !important;}
footer:after {content:''; display:none;}
[data-testid="stToolbar"] {display: none !important;}
[data-testid="stDecoration"] {display: none !important;}
[data-testid="stStatusWidget"] {display: none !important;}
[data-testid="stAppViewBlockContainer"] div:has(a[href*='streamlit.io']) {display: none !important;}
[data-testid="stAppViewBlockContainer"] div:has(img[alt*='GitHub']) {display: none !important;}
section[data-testid="stBottom"] {display: none !important;}
img[alt*="streamlit"], img[alt*="GitHub"] {display: none !important;}
</style>
"""
st.markdown(hide_streamlit_ui, unsafe_allow_html=True)

# ================== CONFIG GOOGLE SHEETS ================== #
SHEET_ID = "1icpLUH3UNvMKuoB_hdiCTiwZ-tbY9aPJEOHGSfBWECY"

def gs_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # 🔹 Dùng secrets khi deploy online
        gcp_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_info, scope)
    except Exception:
        # 🔹 Dùng local credentials.json khi chạy offline
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=350)
def read_df(ws_name: str) -> pd.DataFrame:
    sh = gs_client().open_by_key(SHEET_ID)
    ws = sh.worksheet(ws_name)
    values = ws.get_all_values()
    if not values:
        return pd.DataFrame()
    header, rows = values[0], values[1:]
    df = pd.DataFrame(rows, columns=header)
    return df

def append_row(ws_name: str, values: list):
    sh = gs_client().open_by_key(SHEET_ID)
    ws = sh.worksheet(ws_name)
    ws.append_row(values)

def ensure_headers(ws_name: str, headers: list):
    sh = gs_client().open_by_key(SHEET_ID)
    ws = sh.worksheet(ws_name)
    if not ws.get_all_values():
        ws.append_row(headers)

# ================== AUTH ================== #
from auth_module import init_users_sheet_once, signup_view, login_view

st.sidebar.title("Tài khoản")
init_users_sheet_once()

if not st.session_state.get("auth", False):
    mode = st.sidebar.radio("Chọn", ["Đăng nhập", "Đăng ký"], horizontal=True)
    if mode == "Đăng ký":
        signup_view()
    else:
        login_view()
    st.stop()

st.sidebar.success(f"Xin chào {st.session_state.get('username','')}!")
if st.sidebar.button("Đăng xuất", key="logout_btn"):
    for k in ["auth", "username"]:
        st.session_state.pop(k, None)
    st.rerun()

# ================== CÁC SHEET ================== #
TONG_QUAN_WS     = "Tổng Quan"
DANH_MUC_WS      = "Danh mục đầu tư"
DONG_TIEN_WS     = "Dòng tiền quỹ"
GIAO_DICH_CCQ_WS = "Giao dịch chứng chỉ quỹ"
CHI_PHI_NO_WS    = "Chi phí & nợ"
NAV_WS           = "Giá trị tài sản ròng"
KHACH_HANG_WS    = "Thông tin khách hàng"

# ================== SIDEBAR CHÍNH ================== #
st.sidebar.markdown("---")
section = st.sidebar.selectbox(
    "Tuỳ chọn",
    ["Trang chủ", "Giới thiệu", "Liên hệ", "Giao dịch", "Thông tin cá nhân", "Lịch sử giao dịch"],
    index=0
)

# ================== TRANG CHỦ ================== #
if section == "Trang chủ":
    st.title("📊 Dashboard Quản Lý Quỹ")

    # Bảo đảm các sheet có header
    for ws_name, headers in [
        (DANH_MUC_WS, ["fund_name","ticker","side","qty","price","fee","timestamp"]),
        (DONG_TIEN_WS, ["timestamp","fund_name","amount_vnd","note"]),
        (GIAO_DICH_CCQ_WS, ["timestamp","investor_name","fund_name","amount_vnd","status"]),
        (CHI_PHI_NO_WS, ["timestamp","fund_name","type","amount_vnd","note"]),
        (NAV_WS, ["date","fund_name","nav_per_unit"]),
        (KHACH_HANG_WS, ["investor_name","phone","email"]),
        (TONG_QUAN_WS, ["fund_name","units_outstanding","hang_muc","tỷ_trọng","lợi_suất",
                        "cơ_cấu_vốn_mục_tiêu","cơ_cấu_vốn_thực_tế",
                        "tổng_vốn_đầu_tư","tổng_giá_trị_thị_trường","lợi_nhuận"]),
    ]:
        try:
            ensure_headers(ws_name, headers)
        except Exception as e:
            st.warning(f"Không thể đảm bảo header cho sheet {ws_name}: {e}")

    # ---- TỔNG QUAN ---- #
    def load_tong_quan() -> pd.DataFrame:
        df = read_df(TONG_QUAN_WS)
        if df.empty:
            return df
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        for c in ["tỷ_trọng","lợi_suất"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace("%",""), errors="coerce") / 100
        return df

    df = load_tong_quan()
    st.subheader("📁 Dữ liệu Tổng Quan")
    if df.empty:
        st.info("Chưa có dữ liệu trong 'Tổng Quan'.")
    else:
        funds = sorted(df["fund_name"].dropna().unique().tolist())
        picked_fund = st.selectbox("Chọn quỹ", funds)
        fund_df = df[df["fund_name"] == picked_fund].copy()
        st.dataframe(fund_df, use_container_width=True)

        detail_df = fund_df[fund_df["hang_muc"].astype(str).str.lower() != "tổng"]

        if "tỷ_trọng" in detail_df.columns:
            st.subheader("🥧 Cơ cấu tỷ trọng")
            pie = (
                alt.Chart(detail_df)
                .mark_arc()
                .encode(theta="tỷ_trọng:Q", color="hang_muc:N",
                        tooltip=["hang_muc", alt.Tooltip("tỷ_trọng:Q", format=".1%")])
                .properties(height=300)
            )
            st.altair_chart(pie, use_container_width=True)

        if "lợi_suất" in detail_df.columns:
            st.subheader("📈 Biểu đồ lợi suất")
            line = (
                alt.Chart(detail_df)
                .mark_line(point=True)
                .encode(x="hang_muc:N", y=alt.Y("lợi_suất:Q", axis=alt.Axis(format="%")),
                        tooltip=["hang_muc", alt.Tooltip("lợi_suất:Q", format=".2%")])
                .properties(height=280)
            )
            st.altair_chart(line, use_container_width=True)

    st.divider()
    st.subheader("📌 NAV gần đây")
    try:
        df_nav = read_df(NAV_WS)
        if df_nav.empty:
            st.info("Chưa có dữ liệu NAV.")
        else:
            funds_nav = sorted(df_nav["fund_name"].astype(str).unique())
            pick = st.selectbox("Chọn quỹ để xem NAV", funds_nav)
            nav_sel = df_nav[df_nav["fund_name"] == pick].copy()
            nav_sel["date"] = pd.to_datetime(nav_sel["date"], errors="coerce").dt.date
            st.line_chart(nav_sel.set_index("date")["nav_per_unit"])
            st.dataframe(nav_sel.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"Lỗi đọc NAV: {e}")

    with st.expander("🔍 Kiểm tra kết nối Google Sheets"):
        st.write("SHEET_ID:", SHEET_ID)
        try:
            gc = gs_client()
            sh = gc.open_by_key(SHEET_ID)
            worksheets = [ws.title for ws in sh.worksheets()]
            st.write("Danh sách worksheet:", worksheets)
        except Exception as e:
            st.error(f"Lỗi kết nối: {e}")

# ================== GIỚI THIỆU ================== #
elif section == "Giới thiệu":
    st.title("ℹ️ Giới thiệu")
    st.write("""
    Ứng dụng quản lý quỹ MVP:
    - Ghi lệnh giao dịch, dòng tiền, chi phí, NAV/CCQ.
    - Xem tỷ trọng, lợi suất, cơ cấu vốn.
    - Đăng nhập để truy cập nội dung.
    """)

# ================== LIÊN HỆ ================== #
elif section == "Liên hệ":
    st.title("📮 Liên hệ")
    with st.form("contact_form"):
        email = st.text_input("Email")
        msg = st.text_area("Nội dung")
        ok = st.form_submit_button("Gửi")
    if ok:
        try:
            ensure_headers("Liên hệ", ["timestamp", "email", "message"])
            append_row("Liên hệ", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email, msg])
            st.success("✅ Đã ghi nhận liên hệ của bạn!")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"❌ Lỗi ghi liên hệ: {e}")

# ================== GIAO DỊCH ================== #
elif section == "Giao dịch":
    st.title("💸 Giao dịch chứng chỉ quỹ")
    with st.form("buy_ccq_form", clear_on_submit=True):
        investor_name = st.text_input("Tên nhà đầu tư")
        fund_name = st.text_input("Tên quỹ muốn mua")
        amount = st.number_input("Số tiền (VND)", min_value=0.0, step=1_000_000.0, format="%.0f")
        submitted = st.form_submit_button("Gửi yêu cầu")
    if submitted:
        if not investor_name or not fund_name or amount <= 0:
            st.error("Vui lòng nhập đầy đủ thông tin.")
        else:
            ensure_headers(GIAO_DICH_CCQ_WS, ["timestamp","investor_name","fund_name","amount_vnd","status"])
            append_row(GIAO_DICH_CCQ_WS, [datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                          investor_name, fund_name, amount, "PENDING"])
            st.success("✅ Đã gửi yêu cầu mua CCQ.")

# ================== THÔNG TIN CÁ NHÂN ================== #
elif section == "Thông tin cá nhân":
    from app_utils import get_user_profile
    st.title("👤 Thông tin cá nhân")
    username = st.session_state.get("username", "")
    prof = get_user_profile(username)
    if not prof:
        st.warning("Không tìm thấy thông tin người dùng.")
    else:
        st.write(f"**Tên:** {prof.get('display_name','')} — **Vai trò:** {prof.get('role','')}")
        st.write(f"**Email:** {prof.get('email','')} — **SĐT:** {prof.get('phone','')}")
        st.write(f"**Địa chỉ:** {prof.get('address','')} — **STK:** {prof.get('bank_acct','')}")