# app.py — bản B hoàn chỉnh, tối ưu cho deploy (Cloud + Local)
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
SHEET_ID = "1icpLUH3UNvMKuoB_hdiCTiwZ-tbY9aPJEOHGSfBWECY"

# --- Ẩn logo, GitHub link, toolbar, footer, link web ---
hide_streamlit_ui = """
<style>
#MainMenu, header, footer {visibility: hidden !important;}
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {display: none !important;}
[data-testid="stAppViewBlockContainer"] div:has(a[href*='streamlit.io']),
[data-testid="stAppViewBlockContainer"] div:has(img[alt*='GitHub']) {
    display: none !important;
}
</style>
"""
st.markdown(hide_streamlit_ui, unsafe_allow_html=True)

# ================== IMPORT AUTH ================== #
from auth_module import init_users_sheet_once, signup_view, login_view

# ================== CÁC HẰNG TÊN SHEET ================== #
TONG_QUAN_WS     = "Tổng Quan"
DANH_MUC_WS      = "Danh mục đầu tư"
DONG_TIEN_WS     = "Dòng tiền quỹ"
GIAO_DICH_CCQ_WS = "Giao dịch chứng chỉ quỹ"
CHI_PHI_NO_WS    = "Chi phí & nợ"
NAV_WS           = "Giá trị tài sản ròng"
KHACH_HANG_WS    = "Thông tin khách hàng"

# ================== KẾT NỐI GOOGLE SHEETS ================== #
def gs_client():
    """Tự nhận dạng môi trường (Cloud hoặc Local) để kết nối Google Sheets."""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        # 🔹 Nếu chạy trên Streamlit Cloud (đã cấu hình secrets)
        gcp_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_info, scope)
    except Exception:
        # 🔹 Nếu chạy local (trong máy)
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


@st.cache_data(ttl=350)
def read_df(ws_name: str) -> pd.DataFrame:
    """Đọc toàn bộ dữ liệu của worksheet vào DataFrame."""
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


# ================== LOGIN GATE ================== #
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
if st.sidebar.button("Đăng xuất"):
    for k in ["auth", "username"]:
        st.session_state.pop(k, None)
    st.rerun()

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

    # Bảo đảm header các sheet
    for ws_name, headers in [
        (DANH_MUC_WS,        ["fund_name","ticker","side","qty","price","fee","timestamp"]),
        (DONG_TIEN_WS,       ["timestamp","fund_name","amount_vnd","note"]),
        (GIAO_DICH_CCQ_WS,   ["timestamp","investor_name","fund_name","amount_vnd","status"]),
        (CHI_PHI_NO_WS,      ["timestamp","fund_name","type","amount_vnd","note"]),
        (NAV_WS,             ["date","fund_name","nav_per_unit"]),
        (KHACH_HANG_WS,      ["investor_name","phone","email"]),
        (TONG_QUAN_WS,       ["fund_name","units_outstanding","hang_muc","tỷ_trọng","lợi_suất",
                              "cơ_cấu_vốn_mục_tiêu","cơ_cấu_vốn_thực_tế","tổng_vốn_đầu_tư",
                              "tổng_giá_trị_thị_trường","lợi_nhuận"]),
    ]:
        try:
            ensure_headers(ws_name, headers)
        except Exception as e:
            st.warning(f"Không thể đảm bảo header cho sheet {ws_name}: {e}")

    # ---- TỔNG QUAN QUỸ ---- #
    def load_tong_quan() -> pd.DataFrame:
        df = read_df(TONG_QUAN_WS)
        if df.empty:
            return df
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if "" in df.columns:
            df = df.rename(columns={"": "hang_muc"})
        for c in ["tổng_vốn_đầu_tư","tổng_giá_trị_thị_trường","lợi_nhuận",
                  "cơ_cấu_vốn_mục_tiêu","cơ_cấu_vốn_thực_tế"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(",",""), errors="coerce")
        for c in ["tỷ_trọng","lợi_suất"]:
            if c in df.columns:
                df[c] = (
                    pd.to_numeric(df[c].astype(str).str.replace(",","").str.replace("%",""),
                                  errors="coerce") / 100.0
                )
        return df

    df = load_tong_quan()
    st.subheader("📁 Dữ liệu Tổng Quan")
    if df.empty:
        st.info("Chưa có dữ liệu trong 'Tổng Quan'.")
    else:
        if "fund_name" not in df.columns:
            st.error("Sheet 'Tổng Quan' cần cột 'fund_name'.")
        else:
            funds = sorted(df["fund_name"].dropna().unique().tolist())
            picked_fund = st.selectbox("Chọn quỹ", funds)
            fund_df = df[df["fund_name"] == picked_fund].copy()
            st.dataframe(fund_df, use_container_width=True)

            # ---- Biểu đồ ----
            detail_df = fund_df.copy()
            if "hang_muc" in detail_df.columns:
                detail_df = detail_df[detail_df["hang_muc"].astype(str).str.lower().ne("tổng")]

            if not detail_df.empty and "tỷ_trọng" in detail_df.columns:
                st.subheader("🥧 Cơ cấu tỷ trọng")
                pie = (
                    alt.Chart(detail_df)
                    .mark_arc()
                    .encode(
                        theta="tỷ_trọng:Q",
                        color="hang_muc:N",
                        tooltip=["hang_muc", alt.Tooltip("tỷ_trọng:Q", format=".1%")],
                    )
                )
                st.altair_chart(pie, use_container_width=True)

            if not detail_df.empty and "lợi_suất" in detail_df.columns:
                st.subheader("📈 Biểu đồ lợi suất")
                line = (
                    alt.Chart(detail_df)
                    .mark_line(point=True)
                    .encode(
                        x="hang_muc:N",
                        y=alt.Y("lợi_suất:Q", axis=alt.Axis(format="%")),
                        tooltip=["hang_muc", alt.Tooltip("lợi_suất:Q", format=".2%")],
                    )
                )
                st.altair_chart(line, use_container_width=True)

            if not detail_df.empty and {"cơ_cấu_vốn_mục_tiêu","cơ_cấu_vốn_thực_tế"}.issubset(detail_df.columns):
                st.subheader("🧱 Cơ cấu vốn mục tiêu vs thực tế")
                co = detail_df[["hang_muc","cơ_cấu_vốn_mục_tiêu","cơ_cấu_vốn_thực_tế"]].melt(
                    id_vars="hang_muc", var_name="loại", value_name="tỷ_lệ"
                )
                bar = (
                    alt.Chart(co)
                    .mark_bar()
                    .encode(
                        x="hang_muc:N", y="tỷ_lệ:Q", color="loại:N",
                        tooltip=["hang_muc","loại","tỷ_lệ"],
                    )
                )
                st.altair_chart(bar, use_container_width=True)

    # ---- NAV gần đây ---- #
    st.divider()
    st.subheader("📌 NAV gần đây")
    try:
        df_nav = read_df(NAV_WS)
        if df_nav.empty:
            st.info("Chưa có dữ liệu NAV.")
        else:
            funds_nav = sorted(df_nav["fund_name"].astype(str).unique())
            pick = st.selectbox("Chọn quỹ để xem NAV", funds_nav, key="nav_fund_select")
            nav_sel = df_nav[df_nav["fund_name"] == pick].copy()
            nav_sel["date"] = pd.to_datetime(nav_sel["date"], errors="coerce").dt.date
            nav_sel = nav_sel.sort_values("date")
            st.line_chart(nav_sel.set_index("date")["nav_per_unit"])
            st.dataframe(nav_sel.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"Lỗi đọc NAV: {e}")

    # ---- Danh mục đầu tư ---- #
    st.divider()
    st.subheader("📘 Danh mục đầu tư")
    try:
        df_quan = read_df("Danh mục đầu tư").copy()
    except Exception as e:
        st.error(f"Lỗi đọc 'Danh mục đầu tư': {e}")
    else:
        if df_quan.empty:
            st.info("Chưa có dữ liệu trong 'Danh mục đầu tư'.")
        elif "fund_name" not in df_quan.columns:
            st.error("Sheet 'Danh mục đầu tư' cần cột 'fund_name'.")
        else:
            df_quan["fund_name"] = df_quan["fund_name"].astype(str).str.strip()
            funds = sorted(df_quan["fund_name"].dropna().unique().tolist())
            picked_fund = st.selectbox("Chọn quỹ", funds, key="fund_pick_danh_muc")
            df_filtered = df_quan[df_quan["fund_name"] == picked_fund].copy()
            st.dataframe(df_filtered, use_container_width=True)

# ================== GIỚI THIỆU ================== #
elif section == "Giới thiệu":
    st.title("ℹ️ Giới thiệu")
    st.write("""
    Đây là ứng dụng quản lý quỹ dạng MVP, dùng Google Sheets làm backend:
    - Ghi lệnh giao dịch, dòng tiền, chi phí, NAV/CCQ.
    - Xem tỷ trọng, lợi suất, cơ cấu vốn theo quỹ.
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
            ensure_headers("Liên hệ", ["timestamp","email","message"])
            append_row("Liên hệ", [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email, msg
            ])
            st.success("✅ Đã ghi nhận liên hệ của bạn! Cảm ơn bạn đã gửi phản hồi.")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"❌ Ghi liên hệ thất bại: {e}")

# ================== GIAO DỊCH ================== #
elif section == "Giao dịch":
    st.title("💸 Giao dịch")
    st.subheader("Gửi yêu cầu mua CCQ")

    if "last_buy_token" not in st.session_state:
        st.session_state["last_buy_token"] = None

    with st.form("sub_form_buy_ccq", clear_on_submit=True):
        investor_name = st.text_input("Tên nhà đầu tư", key="inv_name")
        fund_pick     = st.text_input("Quỹ muốn mua", placeholder="VD: Alpha Fund", key="fund_pick")
        amount_vnd    = st.number_input("Số tiền (VND)", min_value=0.0, step=1_000_000.0, format="%.0f")
        submitted     = st.form_submit_button("Gửi yêu cầu")

    SUBMIT_WS = "YCGD"
    if submitted:
        investor_name, fund_pick = investor_name.strip(), fund_pick.strip()
        if not investor_name or not fund_pick or amount_vnd <= 0:
            st.error("Vui lòng điền đủ thông tin hợp lệ.")
        else:
            token = f"{investor_name}|{fund_pick}|{amount_vnd}|{datetime.now():%Y-%m-%d %H:%M:%S}"
            if token == st.session_state["last_buy_token"]:
                st.info("Yêu cầu này đã được ghi nhận.")
            else:
                try:
                    ensure_headers(SUBMIT_WS, ["timestamp","investor_name","fund_name","amount_vnd","status"])
                    append_row(SUBMIT_WS, [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), investor_name, fund_pick, float(amount_vnd), "PENDING"])
                    st.session_state["last_buy_token"] = token
                    st.success("✅ Đã gửi yêu cầu. Chờ quỹ duyệt.")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"❌ Ghi yêu cầu thất bại: {e}")

# ================== THÔNG TIN CÁ NHÂN ================== #
elif section == "Thông tin cá nhân":
    def get_user_profile(username: str) -> dict:
        try:
            df = read_df("Users")
        except Exception:
            return {}
        if df.empty:
            return {}
        df.columns = [c.strip().lower() for c in df.columns]
        row = df[df["username"].astype(str) == str(username)]
        if row.empty:
            return {}
        r = row.iloc[0].to_dict()
        return {
            "username": r.get("username",""),
            "display_name": r.get("display_name",""),
            "email": r.get("email",""),
            "phone": r.get("sđt", r.get("phone","")),
            "address": r.get("address",""),
            "bank_acct": r.get("stk",""),
            "role": r.get("role",""),
            "fund": r.get("fund","")
        }

    username = st.session_state.get("username","")
    prof = get_user_profile(username)
    st.title("👤 Thông tin cá nhân")

    initials = (prof.get("display_name") or prof.get("username") or "U")[:1].upper()
    role_badge = (prof.get("role") or "unknown").upper()

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:16px;
    padding:16px;border:1px solid #EEF2FF;border-radius:16px;
    background:linear-gradient(180deg,#F8FAFF 0%, #FFFFFF 100%);">
      <div style="width:60px;height:60px;border-radius:50%;
      background:#E5E7EB;display:flex;align-items:center;justify-content:center;
      font-weight:700;font-size:22px;color:#374151;">{initials}</div>
      <div style="flex:1">
        <div style="font-size:20px;font-weight:700;color:#111827;">
          {prof.get("display_name") or prof.get("username")}
        </div>
        <div style="color:#6B7280;">@{prof.get("username")}</div>
      </div>
      <div><span style="padding:6px 10px;border-radius:999px;
      background:#EEF2FF;color:#1D4ED8;font-weight:600;font-size:12px;">
      {role_badge}</span></div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("📬 Liên lạc")
        st.write(f"**Email:** {prof.get('email','—')}")
        st.write(f"**SĐT:** {prof.get('phone','—')}")
        st.write(f"**Địa chỉ:** {prof.get('address','—')}")
        st.subheader("🏦 Thanh toán")
        st.write(f"**STK:** {prof.get('bank_acct','—')}")
    with col2:
        st.subheader("🏷️ Khác")
        st.write(f"**Vai trò:** {prof.get('role','—')}")
        st.write(f"**Thuộc quỹ:** {prof.get('fund','—')}")

# ================== LỊCH SỬ GIAO DỊCH ================== #
elif section == "Lịch sử giao dịch":
    st.title("💹 Lịch sử giao dịch CCQ")
    try:
        df_txn = read_df("YCGD")
        if df_txn.empty:
            st.info("Chưa có giao dịch nào.")
        else:
            df_txn.columns = [c.strip().lower() for c in df_txn.columns]
            username = st.session_state.get("username","")
            df_user = df_txn[df_txn["investor_name"].astype(str).str.lower()==username.lower()]
            if df_user.empty:
                st.info("Bạn chưa có giao dịch nào được ghi nhận.")
            else:
                if "timestamp" in df_user.columns:
                    df_user["timestamp"] = pd.to_datetime(df_user["timestamp"], errors="coerce")
                df_user = df_user.sort_values("timestamp", ascending=False)
                rename = {"timestamp":"Thời gian","fund_name":"Tên quỹ","amount_vnd":"Số tiền (VND)","status":"Trạng thái"}
                df_show = df_user.rename(columns=rename)
                st.dataframe(df_show[["Thời gian","Tên quỹ","Số tiền (VND)","Trạng thái"]], use_container_width=True)
                total_amt = pd.to_numeric(df_user["amount_vnd"], errors="coerce").sum()
                st.metric("💰 Tổng giá trị giao dịch", f"{total_amt:,.0f} VND")
    except Exception as e:
        st.error(f"Lỗi đọc lịch sử giao dịch: {e}")
