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
                    if not detail_df.empty and "tỷ_trọng" in detail_df.columns:
                        st.subheader("🥧 Cơ cấu tỷ trọng")


                        # đảm bảo tỷ_trọng là số (0..1)
                        detail_df = detail_df.copy()
                        detail_df["tỷ_trọng"] = pd.to_numeric(detail_df["tỷ_trọng"], errors="coerce")
                        # drop nan / filter tiny slices nếu muốn
                        detail_df = detail_df.dropna(subset=["tỷ_trọng"])
                        detail_df = detail_df.sort_values("tỷ_trọng", ascending=False)


                        pie = alt.Chart(detail_df).transform_calculate(
                            pct="datum['tỷ_trọng']"  # giữ nguyên tên cột (đã là 0..1)
                        ).transform_window(
                            cumulative='sum(pct)',
                            sort=[alt.SortField("tỷ_trọng", order="descending")]
                        ).transform_calculate(
                            label="format(datum.pct, '.1%')"
                        )


                        arc = pie.mark_arc(innerRadius=40).encode(
                            theta=alt.Theta(field="tỷ_trọng", type="quantitative"),
                            color=alt.Color("hang_muc:N", legend=alt.Legend(title="Hạng mục")),
                            tooltip=[
                                alt.Tooltip("hang_muc:N", title="Hạng mục"),
                                alt.Tooltip("tỷ_trọng:Q", title="Tỷ trọng", format='.2%')
                            ]
                        ).properties(width=480, height=360)


                        # label ngoài bánh (đóng gói bằng mark_text với offset)
                        labels = pie.mark_text(radiusOffset=10).encode(
                            theta=alt.Theta(field="tỷ_trọng", type="quantitative"),
                            text=alt.Text('label:N'),
                        )


                        st.altair_chart((arc + labels).configure_legend(
                            orient='right'
                        ), use_container_width=True)


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


    # ---- Danh mục đầu tư (lọc theo fund_name) ----
        st.subheader(f"Danh mục đầu tư")
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
                # Chuẩn hoá để tránh lỗi khoảng trắng/hoa thường
                df_quan["fund_name"] = (
                    df_quan["fund_name"]
                    .astype(str)
                    .str.strip()
                )


                funds = sorted(df_quan["fund_name"].dropna().unique().tolist())
                picked_fund = st.selectbox("Chọn quỹ", funds, key="fund_pick_danh_muc")
                df_filtered = df_quan[df_quan["fund_name"] == picked_fund].copy()
                st.dataframe(df_filtered, use_container_width=True)
    # ❌ Đừng đọc lại và st.dataframe(df_quan) lần nữa kẻo hiển thị toàn bộ bảng

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
