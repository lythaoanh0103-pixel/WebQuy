# app.py  — phiên bản đã dọn sạch + login gate + sidebar gọn

import json
import streamlit as st
import pandas as pd
from datetime import datetime, date
import bcrypt
import altair as alt
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from auth_module import init_users_sheet_once, signup_view, login_view

# ================== CẤU HÌNH CƠ BẢN ================== #
st.set_page_config(
    page_title="Quản Lý Quỹ",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)
SHEET_ID = "1icpLUH3UNvMKuoB_hdiCTiwZ-tbY9aPJEOHGSfBWECY"

# ================== IMPORT AUTH ================== #
# YÊU CẦU: trong auth_module.py, khi đăng nhập thành công phải set:
#   st.session_state["auth"] = True
#   st.session_state["username"] = <ten_dang_nhap>
#   st.rerun()

# ================== CÁC HẰNG TÊN SHEET ================== #
TONG_QUAN_WS     = "Tổng Quan"
DANH_MUC_WS      = "Danh mục đầu tư"
DONG_TIEN_WS     = "Dòng tiền quỹ"
GIAO_DICH_CCQ_WS = "Giao dịch chứng chỉ quỹ"
CHI_PHI_NO_WS    = "Chi phí & nợ"
NAV_WS           = "Giá trị tài sản ròng"
KHACH_HANG_WS    = "Thông tin khách hàng"


# ================== HÀM GOOGLE SHEETS ================== #

def gs_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        # 🔹 Nếu chạy trên Streamlit Cloud (đã thêm secrets)
        gcp_info = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gcp_info, scope)
    except Exception:
        # 🔹 Nếu chạy local (trong máy)
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)


@st.cache_data(ttl=300)
def read_df(ws_name: str) -> pd.DataFrame:
    """Đọc toàn bộ dữ liệu của worksheet vào DataFrame (giữ dạng chuỗi để tránh lỗi pyarrow)."""
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


# ================== LOGIN GATE (CHẶN UI KHI CHƯA LOGIN) ================== #
st.sidebar.title("Tài khoản")
init_users_sheet_once()


if not st.session_state.get("auth", False):
    mode = st.sidebar.radio("Chọn", ["Đăng nhập", "Đăng ký"], horizontal=True)
    if mode == "Đăng ký":
        signup_view()
    else:
        login_view()
    # Debug (có thể bỏ nếu không cần):
    # st.sidebar.code({"auth": st.session_state.get("auth"), "username": st.session_state.get("username")})
    st.stop()  # 🔴 Quan trọng: chặn toàn bộ UI bên dưới nếu chưa login


# ĐÃ LOGIN → hiện menu phụ + nút đăng xuất
st.sidebar.success(f"Xin chào {st.session_state.get('username','')}!")
if st.sidebar.button("Đăng xuất"):
    for k in ["auth", "username"]:
        st.session_state.pop(k, None)
    st.rerun()


# ================== SIDEBAR CHÍNH (SAU KHI LOGIN) ================== #
st.sidebar.markdown("---")
section = st.sidebar.selectbox("Tuỳ chọn", ["Trang chủ", "Giới thiệu", "Liên hệ", "Giao dịch", "Thông tin cá nhân"], index=0)


# ================== TRANG CHỦ (NỘI DUNG CHÍNH) ================== #
if section == "Trang chủ":
    st.title("📊 Dashboard Quản Lý Quỹ")


    # Bảo đảm các sheet có header (chỉ tạo nếu sheet đang trống)
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
        # chuẩn hoá tên cột
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if "" in df.columns:
            df = df.rename(columns={"": "hang_muc"})
        # ép kiểu số có chọn lọc
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
        # chọn quỹ
        if "fund_name" not in df.columns:
            st.error("Sheet 'Tổng Quan' cần cột 'fund_name'.")
        else:
            funds = sorted(df["fund_name"].dropna().unique().tolist())
            picked_fund = st.selectbox("Chọn quỹ", funds)
            fund_df = df[df["fund_name"] == picked_fund].copy()
            st.dataframe(fund_df, use_container_width=True)


            # vẽ biểu đồ (nếu có dữ liệu chi tiết hạng mục)
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
                    .properties(height=300)
                )
                st.altair_chart(pie, use_container_width=True)


            if not detail_df.empty and "lợi_suất" in detail_df.columns:
                st.subheader("📈 Biểu đồ lợi suất")
                line = (
                    alt.Chart(detail_df)
                    .mark_line(point=True)
                    .encode(
                        x=alt.X("hang_muc:N", title="Hạng mục"),
                        y=alt.Y("lợi_suất:Q", axis=alt.Axis(format="%"), title="Lợi suất"),
                        tooltip=["hang_muc", alt.Tooltip("lợi_suất:Q", format=".2%")],
                    )
                    .properties(height=280)
                )
                st.altair_chart(line, use_container_width=True)


            if not detail_df.empty and {"cơ_cấu_vốn_mục_tiêu", "cơ_cấu_vốn_thực_tế"}.issubset(detail_df.columns):
                st.subheader("🧱 Cơ cấu vốn mục tiêu vs thực tế")
                co = detail_df[["hang_muc","cơ_cấu_vốn_mục_tiêu","cơ_cấu_vốn_thực_tế"]].melt(
                    id_vars="hang_muc", var_name="loại", value_name="tỷ_lệ"
                )
                bar = (
                    alt.Chart(co)
                    .mark_bar()
                    .encode(
                        x=alt.X("hang_muc:N", title="Hạng mục"),
                        y=alt.Y("tỷ_lệ:Q", title="Tỷ lệ"),
                        color="loại:N",
                        tooltip=["hang_muc","loại","tỷ_lệ"],
                    )
                    .properties(height=280)
                )
                st.altair_chart(bar, use_container_width=True)


    st.divider()
       
    # ---- NAV gần đây ---- #
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


    st.divider()


    # ---- Diagnostics ---- #
    with st.expander("🔍 Kiểm tra kết nối Google Sheets"):
        st.write("SHEET_ID đang dùng:", SHEET_ID)
        try:
            import json
            with open("credentials.json", "r", encoding="utf-8") as f:
                creds_obj = json.load(f)
            client_email = creds_obj.get("client_email", "(không thấy client_email)")
            st.write("Service Account email:", client_email)
        except Exception as e:
            st.error(f"Không đọc được credentials.json: {e}")


        try:
            gc = gs_client()
            sh = gc.open_by_key(SHEET_ID)
            worksheets = [ws.title for ws in sh.worksheets()]
            st.write("Danh sách worksheet:", worksheets)
        except Exception as e:
            st.error(f"Không mở được Sheet (thiếu quyền Editor hoặc sai SHEET_ID): {e}")


        test_sheet = st.selectbox("Chọn sheet để thử ghi",
                                  [DANH_MUC_WS, TONG_QUAN_WS, DONG_TIEN_WS,
                                   GIAO_DICH_CCQ_WS, CHI_PHI_NO_WS, NAV_WS, KHACH_HANG_WS])
        if st.button("➡️ Thử ghi 1 dòng test"):
            try:
                append_row(test_sheet, [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "TEST_ROW"])
                st.success(f"✅ Ghi test thành công vào '{test_sheet}'.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"❌ Thử ghi thất bại: {e}")


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
        st.success("Đã ghi nhận liên hệ. (Demo)")
       
# 3) Gửi yêu cầu mua CCQ -> 'Giao dịch chứng chỉ quỹ'
if section == "Giao dịch":
    st.title("Giao dịch")
    st.subheader("4) Gửi yêu cầu mua CCQ")


    with st.form("sub_form_buy_ccq"):
        investor_name = st.text_input("Tên nhà đầu tư", key="inv_name")
        fund_pick     = st.text_input("Quỹ muốn mua", placeholder="VD: Alpha Fund", key="fund_pick")
        amount_vnd    = st.number_input("Số tiền (VND)", min_value=0.0, step=1_000_000.0, format="%.0f", key="amount_vnd")
        submit        = st.form_submit_button("Gửi yêu cầu")


    if submit:
        if not (investor_name and fund_pick and amount_vnd > 0):
            st.error("Vui lòng điền đủ thông tin.")
    else:
            ensure_headers("Giao dịch chứng chỉ quỹ",
                           ["timestamp","investor_name","fund_name","amount_vnd","status"])
            append_row("Giao dịch chứng chỉ quỹ", [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                investor_name, fund_pick, float(amount_vnd), "PENDING"
            ])
            st.success("✅ Đã gửi yêu cầu. Chờ quỹ duyệt.")
            st.cache_data.clear()
    st.divider()


def _norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _mask(s: str, keep_left=3, keep_right=3, fill="•"):
    s = str(s or "")
    if len(s) <= keep_left + keep_right:
        return fill * len(s)
    return s[:keep_left] + (fill * (len(s) - keep_left - keep_right)) + s[-keep_right:]


def _fmt_date(s: str):
    s = str(s or "").strip()
    if not s:
        return ""
    # thử các format hay gặp
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%d/%m/%Y")
        except Exception:
            pass
    # fallback: để nguyên
    return s


def get_user_profile(username: str) -> dict:
    """Đọc hồ sơ người dùng từ sheet 'Users' theo username."""
    try:
        df = read_df("Users")
    except Exception as e:
        st.error(f"Không đọc được sheet Users: {e}")
        return {}


    if df.empty:
        return {}


    df = _norm_cols(df)


    # Map các key thường dùng -> có thể thiếu tuỳ file của bạn
    # Chúng ta sẽ get() an toàn, nếu thiếu sẽ trả "".
    cols = set(df.columns)
    row = df[df.get("username", pd.Series(dtype=str)).astype(str) == str(username)].head(1)
    if row.empty:
        return {}


    r = row.iloc[0].to_dict()


    profile = {
        "username":       r.get("username", ""),
        "display_name":   r.get("display_name", ""),
        "email":          r.get("email", ""),
        "cccd_mst":       r.get("cccd/mst", r.get("cccd_mst", "")),
        "dob":            r.get("dob", ""),
        "phone":          r.get("sđt", r.get("sdt", r.get("phone", ""))),
        "address":        r.get("address", ""),
        "bank_acct":      r.get("stk", r.get("bank_acct", "")),
        "role":           r.get("role", ""),
        "fund":           r.get("fund", r.get("fund_name", "")),  # nếu có cột fund
    }
    return profile


# ================== PAGE: THÔNG TIN CÁ NHÂN ================== #
if section == "Thông tin cá nhân":
    if not st.session_state.get("auth"):
        st.warning("Vui lòng đăng nhập để xem thông tin cá nhân.")
        st.stop()


    username = st.session_state.get("username", "")
    prof = get_user_profile(username)


    st.title("👤 Thông tin cá nhân")


    # Header card
    initials = (
        (prof.get("display_name") or prof.get("username") or "U")
        .strip()[:1]
        .upper()
    )
    role_badge = (prof.get("role") or "").strip() or "unknown"


    st.markdown(
        f"""
        <div style="
            display:flex; align-items:center; gap:16px;
            padding:16px; border:1px solid #EEF2FF; border-radius:16px;
            background:linear-gradient(180deg,#F8FAFF 0%, #FFFFFF 100%);
        ">
          <div style="
              width:60px;height:60px;border-radius:50%;
              background:#E5E7EB; display:flex;align-items:center;justify-content:center;
              font-weight:700;font-size:22px;color:#374151;">
            {initials}
          </div>
          <div style="flex:1">
            <div style="font-size:20px;font-weight:700;color:#111827;">
              {prof.get("display_name") or prof.get("username")}
            </div>
            <div style="color:#6B7280;">@{prof.get("username")}</div>
          </div>
          <div>
            <span style="
              padding:6px 10px;border-radius:999px;
              background:#EEF2FF;color:#1D4ED8;
              font-weight:600;font-size:12px;text-transform:uppercase;">
              {role_badge}
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


    st.write("")


    # Hai cột thông tin
    col1, col2 = st.columns(2)


    with col1:
        st.subheader("📬 Liên lạc")
        st.write(f"**Email:** {prof.get('email') or '—'}")
        st.write(f"**SĐT:** {prof.get('phone') or '—'}")
        st.write(f"**Địa chỉ:** {prof.get('address') or '—'}")


        st.subheader("🏦 Thanh toán")
        st.write(f"**STK:** {prof.get('bank_acct') or '—'}")


    with col2:
        st.subheader("🪪 Định danh")
        st.write(f"**CCCD/MST:** {prof.get('cccd_mst') or '—'}")
        st.write(f"**Ngày sinh/Ngày ĐK:** {prof.get('dob') or '—'}")


        st.subheader("🏷️ Khác")
        st.write(f"**Vai trò:** {prof.get('role') or '—'}")
        if prof.get("fund"):
            st.write(f"**Thuộc quỹ:** {prof.get('fund')}")

hide_github = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    [data-testid="stToolbar"] {display: none;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stStatusWidget"] {display: none;}
    </style>
"""
st.markdown(hide_github, unsafe_allow_html=True)
