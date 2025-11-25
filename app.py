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
# ================== HÀM LẤY THÔNG TIN NGƯỜI DÙNG ================== #
def get_user_profile(username: str) -> dict:
    """Đọc thông tin người dùng từ sheet 'Users'"""
    try:
        df = read_df("Users")
    except Exception:
        return {}
    if df.empty:
        return {}
    df.columns = [c.strip().lower() for c in df.columns]
    row = df[df["username"].astype(str).str.lower() == username.lower()]
    if row.empty:
        return {}
    r = row.iloc[0].to_dict()
    return {
        "username": r.get("username", ""),
        "display_name": r.get("display_name", r.get("username", "")),
        "email": r.get("email", ""),
        "phone": r.get("sđt", r.get("phone", "")),
        "address": r.get("address", ""),
        "bank_acct": r.get("stk", ""),
        "cccd_mst": r.get("cccd_mst", ""),
        "dob": r.get("dob", ""),
        "role": r.get("role", ""),
        "fund": r.get("fund", "")
    }
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
# ================== PAGE: ADMIN - TRANG CHỦ (TỔNG QUAN QUỸ) ================== #
if role == "admin" and section == "Trang chủ":
    st.title("📊 Dashboard Tổng Quan Tất Cả Quỹ")

    try:
        df = read_df("Tổng Quan")
    except Exception as e:
        st.error(f"Lỗi đọc sheet: {e}")
        st.stop()

    if df.empty:
        st.info("Chưa có dữ liệu Tổng Quan.")
    else:
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        funds = sorted(df["fund_name"].dropna().unique())
        picked_fund = st.selectbox("Chọn quỹ để xem chi tiết", funds)
        fund_df = df[df["fund_name"] == picked_fund]

        st.dataframe(fund_df, use_container_width=True)

        if "hang_muc" in fund_df.columns:
            detail_df = fund_df[fund_df["hang_muc"].astype(str).str.lower() != "tổng"]

            if "tỷ_trọng" in detail_df.columns:
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

            if "lợi_suất" in detail_df.columns:
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

            if {"cơ_cấu_vốn_mục_tiêu","cơ_cấu_vốn_thực_tế"}.issubset(detail_df.columns):
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
        df_nav = read_df("Giá trị tài sản ròng")
        if not df_nav.empty:
            df_nav["date"] = pd.to_datetime(df_nav["date"], errors="coerce").dt.date
            pick = st.selectbox("Chọn quỹ để xem NAV", sorted(df_nav["fund_name"].unique()), key="admin_nav_select")
            nav_sel = df_nav[df_nav["fund_name"] == pick]
            st.line_chart(nav_sel.set_index("date")["nav_per_unit"])
            st.dataframe(nav_sel.tail(10), use_container_width=True)
        else:
            st.info("Chưa có dữ liệu NAV.")
    except Exception as e:
        st.error(f"Lỗi đọc NAV: {e}")

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
    st.title("🧾 Duyệt yêu cầu mua CCQ")
    df = read_df("YCGD")

    if df.empty:
        st.info("Không có yêu cầu.")
    else:
        df = df.fillna("")
        df.reset_index(inplace=True)
        pending_df = df[df["status"].astype(str).str.strip().str.lower().isin(["pending", "chờ thanh toán"])]

        for i, r in pending_df.iterrows():
            with st.expander(f"{r['investor_name']} - {r['fund_name']} ({r['status']})"):
                st.write(f"Số tiền: {r['amount_vnd']}")
                st.write(f"Thời gian: {r['timestamp']}")
                status = r["status"].strip().lower()

                # --- B1: DUYỆT ---
                if status == "pending":
                    c1, c2 = st.columns(2)
                    if c1.button("✅ Duyệt", key=f"approve_{i}"):
                        update_cell("YCGD", r["index"] + 2, 5, "Chờ thanh toán")
                        update_cell("YCGD", r["index"] + 2, 6, "Đã duyệt")
                        st.success(f"Đã duyệt yêu cầu của {r['investor_name']}")
                        st.rerun()

                    if c2.button("❌ Từ chối", key=f"reject_{i}"):
                        note = st.text_input("Lý do từ chối", key=f"note_{i}")
                        if note:
                            update_cell("YCGD", r["index"] + 2, 5, "Không thành công")
                            update_cell("YCGD", r["index"] + 2, 6, f"Từ chối: {note}")
                            st.warning(f"Đã từ chối yêu cầu của {r['investor_name']}")
                            st.rerun()

                # --- B2: XÁC NHẬN THANH TOÁN ---
                elif status == "chờ thanh toán":
                    if st.button("💰 Đã thanh toán", key=f"paid_{i}"):
                        update_cell("YCGD", r["index"] + 2, 5, "Thành công")
                        update_cell("YCGD", r["index"] + 2, 6, "Giao dịch hoàn tất")
                        append_row("Giao dịch chứng chỉ quỹ", [
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            r["investor_name"],
                            r["fund_name"],
                            r["amount_vnd"],
                            "MUA",
                            "Thành công"
                        ])
                        st.success(f"Đã xác nhận thanh toán cho {r['investor_name']}")
                        st.rerun()

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

# ================== PAGE: ADMIN - LỊCH SỬ GIAO DỊCH CỦA KHÁCH HÀNG ================== #
elif role == "admin" and section == "Lịch sử giao dịch":
    st.title("📜 Lịch sử giao dịch tất cả nhà đầu tư")
    df_txn = read_df("YCGD")

    if df_txn.empty:
        st.info("Chưa có dữ liệu.")
    else:
        df_txn["timestamp"] = pd.to_datetime(df_txn["timestamp"], errors="coerce")

        # --- Bộ lọc ---
        col1, col2, col3 = st.columns(3)
        name_filter = col1.text_input("🔎 Lọc theo nhà đầu tư:")
        status_filter = col2.selectbox("📊 Lọc trạng thái", ["Tất cả", "Pending", "Chờ thanh toán", "Thành công", "Không thành công"])
        sort_order = col3.radio("📅 Sắp xếp", ["Mới nhất", "Cũ nhất"], horizontal=True)

        if name_filter:
            df_txn = df_txn[df_txn["investor_name"].str.contains(name_filter, case=False, na=False)]
        if status_filter != "Tất cả":
            df_txn = df_txn[df_txn["status"].str.lower() == status_filter.lower()]

        df_txn = df_txn.sort_values("timestamp", ascending=(sort_order == "Cũ nhất"))
        st.dataframe(df_txn, use_container_width=True)

# ================== PAGE: ADMIN - QUẢN TRỊ NỘI DUNG ================== #
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
# ================== NHÀ ĐẦU TƯ - TRANG CHỦ ================== #
elif role == "investor" and section == "Trang chủ":
    st.title("📊 Dashboard Quản Lý Quỹ")

    try:
        df = read_df("Tổng Quan")
        if df.empty:
            st.info("⚠️ Chưa có dữ liệu trong 'Tổng Quan'.")
        else:
            # Chuẩn hóa cột
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            # Tìm tên cột quỹ (có thể là 'fund_name' hoặc 'tên_quỹ')
            fund_col = None
            for col in df.columns:
                if "fund" in col or "quỹ" in col:
                    fund_col = col
                    break

            if not fund_col:
                st.error("❌ Không tìm thấy cột tên quỹ (fund_name / tên_quỹ).")
            else:
                funds = sorted(df[fund_col].dropna().unique().tolist())
                picked_fund = st.selectbox("Chọn quỹ", funds, key="fund_pick_investor")

                fund_df = df[df[fund_col] == picked_fund].copy()
                st.dataframe(fund_df, use_container_width=True)

                # --- Biểu đồ cơ cấu tỷ trọng ---
                if "hang_muc" in fund_df.columns and "tỷ_trọng" in fund_df.columns:
                    st.subheader("🥧 Cơ cấu tỷ trọng")
                    pie = (
                        alt.Chart(fund_df)
                        .mark_arc()
                        .encode(
                            theta="tỷ_trọng:Q",
                            color="hang_muc:N",
                            tooltip=["hang_muc", alt.Tooltip("tỷ_trọng:Q", format=".1%")],
                        )
                    )
                    st.altair_chart(pie, use_container_width=True)

                # --- Biểu đồ lợi suất ---
                if "lợi_suất" in fund_df.columns:
                    st.subheader("📈 Biểu đồ lợi suất")
                    line = (
                        alt.Chart(fund_df)
                        .mark_line(point=True)
                        .encode(
                            x="hang_muc:N",
                            y=alt.Y("lợi_suất:Q", axis=alt.Axis(format="%")),
                            tooltip=["hang_muc", alt.Tooltip("lợi_suất:Q", format=".2%")],
                        )
                    )
                    st.altair_chart(line, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi đọc dữ liệu: {e}")

    st.divider()
    st.subheader("📌 NAV gần đây")
    try:
        df_nav = read_df("Giá trị tài sản ròng")
        if not df_nav.empty:
            funds_nav = sorted(df_nav["fund_name"].astype(str).unique())
            pick = st.selectbox("Chọn quỹ để xem NAV", funds_nav, key="nav_fund_select_investor")
            nav_sel = df_nav[df_nav["fund_name"] == pick].copy()
            nav_sel["date"] = pd.to_datetime(nav_sel["date"], errors="coerce").dt.date
            nav_sel = nav_sel.sort_values("date")
            st.line_chart(nav_sel.set_index("date")["nav_per_unit"])
            st.dataframe(nav_sel.tail(10), use_container_width=True)
        else:
            st.info("Chưa có dữ liệu NAV.")
    except Exception as e:
        st.error(f"Lỗi đọc NAV: {e}")
# ================== NHÀ ĐẦU TƯ - GIỚI THIỆU ================== #
elif section == "Giới thiệu":
    st.title("ℹ️ Giới thiệu")
    df_cfg = read_df("Config")
    if not df_cfg.empty and "content" in df_cfg.columns:
        st.write(df_cfg[df_cfg["section"] == "intro"]["content"].iloc[0])
# ================== NHÀ ĐẦU TƯ - THÔNG BÁO ================== #
elif role == "investor" and section == "Thông báo":
    st.title("🔔 Thông báo giao dịch CCQ")
    try:
        df_notify = read_df("YCGD")
        username = st.session_state["username"].strip().lower()

        df_notify = df_notify[df_notify["investor_name"].astype(str).str.lower() == username]

        if df_notify.empty:
            st.info("Hiện chưa có thông báo nào.")
        else:
            for i, row in df_notify.iterrows():
                status = row["status"].strip().lower()
                fund = row["fund_name"]
                amount = row["amount_vnd"]
                ts = row["timestamp"]

                if status == "chờ thanh toán":
                    st.warning(f"💳 [{ts}] Giao dịch mua CCQ {fund} trị giá {amount} đang chờ thanh toán.")
                    if st.button(f"➡️ Xem hướng dẫn thanh toán ({fund})", key=f"pay_{i}"):
                        st.session_state["section"] = "Giao dịch"
                        st.rerun()

                elif status == "không thành công":
                    note = row.get("note", "Không có ghi chú.")
                    st.error(f"❌ [{ts}] Giao dịch {fund} không thành công. Lý do: {note}")

                elif status == "thành công":
                    st.success(f"✅ [{ts}] Giao dịch {fund} của bạn đã hoàn tất!")
    except Exception as e:
        st.error(f"Lỗi tải thông báo: {e}")
# ================== NHÀ ĐẦU TƯ - LIÊN HỆ ================== #
elif section == "Liên hệ":
    st.title("📮 Liên hệ")
    with st.form("contact_form"):
        email = st.text_input("Email")
        msg = st.text_area("Nội dung")
        ok = st.form_submit_button("Gửi")
    if ok:
        append_row("Liên hệ", [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), email, msg])
        st.success("✅ Đã gửi liên hệ thành công.")
# ================== NHÀ ĐẦU TƯ - GIAO DỊCH ================== #
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
    st.subheader("📘 Lịch sử yêu cầu giao dịch")
    df_user = read_df("YCGD")
    username = st.session_state["username"].strip().lower()
    df_user = df_user[df_user["investor_name"].astype(str).str.lower() == username]

    if df_user.empty:
        st.info("Chưa có yêu cầu nào.")
    else:
        df_user["timestamp"] = pd.to_datetime(df_user["timestamp"], errors="coerce")
        col1, col2, col3 = st.columns(3)
        status_filter = col1.selectbox("📊 Lọc theo trạng thái", ["Tất cả", "Pending", "Chờ thanh toán", "Thành công", "Không thành công"])
        sort_order = col2.radio("📅 Sắp xếp", ["Mới nhất", "Cũ nhất"], horizontal=True)

        if status_filter != "Tất cả":
            df_user = df_user[df_user["status"].str.lower() == status_filter.lower()]

        df_user = df_user.sort_values("timestamp", ascending=(sort_order == "Cũ nhất"))
        st.dataframe(df_user, use_container_width=True)

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
# ================== NHÀ ĐẦU TƯ - THÔNG TIN CÁ NHÂN ================== #
elif role == "investor" and section == "Thông tin cá nhân":
    if not st.session_state.get("auth"):
        st.warning("Vui lòng đăng nhập để xem thông tin cá nhân.")
        st.stop()

    username = st.session_state.get("username", "")
    prof = get_user_profile(username)
    st.title("👤 Thông tin cá nhân")

    initials = (prof.get("display_name") or prof.get("username") or "U")[:1].upper()
    role_badge = (prof.get("role") or "").upper()

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
        st.subheader("🪪 Định danh")
        st.write(f"**CCCD/MST:** {prof.get('cccd_mst','—')}")
        st.write(f"**Ngày sinh/Ngày ĐK:** {prof.get('dob','—')}")
        st.subheader("🏷️ Khác")
        st.write(f"**Vai trò:** {prof.get('role','—')}")
        if prof.get("fund"):
            st.write(f"**Thuộc quỹ:** {prof.get('fund')}")

# ================== NHÀ ĐẦU TƯ - LỊCH SỬ GIAO DỊCH ================== #
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







