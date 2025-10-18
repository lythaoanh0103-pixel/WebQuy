import streamlit as st
import pandas as pd
from datetime import datetime, date

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ============ CẤU HÌNH CƠ BẢN ============
st.set_page_config(page_title="Quản Lý Quỹ", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
# ============ HÀM TIỆN ÍCH ============
TONG_QUAN_WS     = "Tổng Quan"               # chứa thông tin quỹ (vd: fund_name, units_outstanding, ...)
DANH_MUC_WS      = "Danh mục đầu tư"         # dùng để ghi LỆNH CK (mua/bán) trong MVP này
DONG_TIEN_WS     = "Dòng tiền quỹ"           # (để sau) ghi inflow/outflow tiền mặt
GIAO_DICH_CCQ_WS = "Giao dịch chứng chỉ quỹ" # nơi nhận yêu cầu mua CCQ của NĐT (subscription)
CHI_PHI_NO_WS    = "Chi phí & nợ"            # (để sau) chi phí, nợ
NAV_WS           = "Giá trị tài sản ròng"    # lịch sử NAV/CCQ
KHACH_HANG_WS    = "Thông tin khách hàng"    # (để sau) danh bạ khách hàng

def gs_client():
    """Kết nối Google Sheets bằng credentials.json"""
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=30)
def read_df(ws_name: str) -> pd.DataFrame:
    """Đọc toàn bộ dữ liệu của worksheet vào DataFrame"""
    sh = gs_client().open_by_key(st.secrets["SHEET_ID"])
    ws = sh.worksheet(ws_name)
    data = ws.get_all_records()
    return pd.DataFrame(data)

def append_row(ws_name: str, values: list):
    """Ghi thêm 1 dòng vào worksheet"""
    sh = gs_client().open_by_key(st.secrets["SHEET_ID"])
    ws = sh.worksheet(ws_name)
    ws.append_row(values)

def ensure_headers(ws_name: str, headers: list):
    """Nếu worksheet đang trống, tạo dòng tiêu đề."""
    sh = gs_client().open_by_key(st.secrets["SHEET_ID"])
    ws = sh.worksheet(ws_name)
    if not ws.get_all_values():
        ws.append_row(headers)

# ============ GIAO DIỆN ============
st.title("📊 Quản Lý Quỹ")
vai_tro = st.sidebar.radio("Chọn vai trò:", ["Quỹ", "Nhà đầu tư"])

# Bảo đảm các sheet có header (chỉ tạo nếu đang trống)
for ws_name, headers in [
    # LỆNH CK: ghi ở "Danh mục đầu tư"
    ("Danh mục đầu tư",        ["timestamp","fund_name","ticker","side","qty","price","fee"]),
    # THÔNG TIN QUỸ: "Tổng Quan" cần tối thiểu units_outstanding để tính NAV/CCQ
    ("Tổng Quan",              ["fund_name","units_outstanding"]),
    # DÒNG TIỀN: inflow/outflow
    ("Dòng tiền quỹ",          ["timestamp","fund_name","amount_vnd","note"]),
    # SUBSCRIPTIONS: yêu cầu mua CCQ của NĐT
    ("Giao dịch chứng chỉ quỹ",["timestamp","investor_name","fund_name","amount_vnd","status"]),
    # CHI PHÍ & NỢ
    ("Chi phí & nợ",           ["timestamp","fund_name","type","amount_vnd","note"]),
    # LỊCH SỬ NAV
    ("Giá trị tài sản ròng",   ["date","fund_name","nav_per_unit"]),
    # KHÁCH HÀNG (tuỳ chọn cột)
    ("Thông tin khách hàng",   ["investor_name","phone","email"]),
]:
    try:
        ensure_headers(ws_name, headers)
    except Exception as e:
        st.warning(f"Chưa thể đảm bảo header cho sheet {ws_name}: {e}")

# ======================= VAI TRÒ: QUỸ =======================
if vai_tro == "Quỹ":
    st.header("Quỹ – Nhập liệu & Quản trị")

    # 1) NHẬP LỆNH CK -> 'Danh mục đầu tư'
    with st.expander("1) Nhập lệnh MUA/BÁN chứng khoán (ghi vào 'Danh mục đầu tư')", expanded=True):
        c1, c2, c3, c4 = st.columns([1,1,1,1])
        with c1:
            fund_name = st.text_input("Tên quỹ", placeholder="VD: Alpha Fund")
        with c2:
            ticker = st.text_input("Mã CK", placeholder="VD: VNM, FPT").upper().strip()
        with c3:
            side = st.selectbox("Loại lệnh", ["BUY","SELL"])
        with c4:
            qty = st.number_input("Số lượng", min_value=0.0, step=100.0)

        c5, c6 = st.columns([1,1])
        with c5:
            price = st.number_input("Giá (VND/cp)", min_value=0.0, step=100.0)
        with c6:
            fee = st.number_input("Phí (VND)", min_value=0.0, step=1000.0)

        if st.button("Ghi vào 'Danh mục đầu tư'", type="primary", disabled=not(fund_name and ticker and qty>0)):
            try:
                ensure_headers("Danh mục đầu tư", ["timestamp","fund_name","ticker","side","qty","price","fee"])
                append_row("Danh mục đầu tư", [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    fund_name, ticker, side, float(qty), float(price), float(fee)
                ])
                st.success("✅ Đã ghi lệnh vào 'Danh mục đầu tư'.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Lỗi ghi lệnh: {e}")

        st.caption("Lưu ý: Đây là MVP – dùng sheet này như bảng giao dịch CK khớp cuối cùng.")

    # 2) DÒNG TIỀN QUỸ
    with st.expander("2) Ghi dòng tiền quỹ (ghi vào 'Dòng tiền quỹ')"):
        c1, c2 = st.columns([1,2])
        with c1:
            fund_cf = st.text_input("Tên quỹ (cashflow)")
            amount_cf = st.number_input("Số tiền (+ thu / - chi)", value=0.0, step=1_000_000.0, format="%.0f")
        with c2:
            note_cf = st.text_input("Ghi chú (ví dụ: nộp tiền, rút tiền, cổ tức tiền...)")

        if st.button("Ghi dòng tiền"):
            try:
                ensure_headers("Dòng tiền quỹ", ["timestamp","fund_name","amount_vnd","note"])
                append_row("Dòng tiền quỹ", [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    fund_cf, float(amount_cf), note_cf
                ])
                st.success("✅ Đã ghi vào 'Dòng tiền quỹ'.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Lỗi ghi dòng tiền: {e}")

    # 3) CHI PHÍ & NỢ
    with st.expander("3) Ghi chi phí & nợ (ghi vào 'Chi phí & nợ')"):
        c1, c2, c3 = st.columns([1,1,2])
        with c1:
            fund_cp = st.text_input("Tên quỹ (chi phí)")
        with c2:
            amount_cp = st.number_input("Số tiền (VND)", value=0.0, step=500_000.0, format="%.0f")
        with c3:
            type_cp = st.selectbox("Loại", ["Phí quản lý", "Phí lưu ký", "Phí giao dịch", "Nợ khác", "Khác"])
        note_cp = st.text_input("Ghi chú")

        if st.button("Ghi chi phí & nợ"):
            try:
                ensure_headers("Chi phí & nợ", ["timestamp","fund_name","type","amount_vnd","note"])
                append_row("Chi phí & nợ", [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    fund_cp, type_cp, float(amount_cp), note_cp
                ])
                st.success("✅ Đã ghi vào 'Chi phí & nợ'.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Lỗi ghi chi phí & nợ: {e}")

    st.divider()

    # 4) TÍNH & LƯU NAV/CCQ (đơn giản hoá)
    st.subheader("4) Tính & lưu NAV/CCQ (ghi vào 'Giá trị tài sản ròng')")
    nav_fund = st.text_input("Quỹ cần tính NAV")
    nav_date = st.date_input("Ngày NAV", value=date.today())
    if st.button("Tính & Lưu NAV"):
        try:
            # Lấy lệnh CK
            df_orders = read_df("Danh mục đầu tư")
            # Lấy units_outstanding
            df_info = read_df("Tổng Quan")
            # (Tuỳ chọn) Dòng tiền, chi phí
            df_cash = read_df("Dòng tiền quỹ")
            df_cost = read_df("Chi phí & nợ")

            if df_info.empty:
                st.warning("Sheet 'Tổng Quan' trống hoặc thiếu 'units_outstanding'.")
            elif df_orders.empty and df_cash.empty and df_cost.empty:
                st.warning("Chưa có dữ liệu để tính NAV.")
            else:
                # Vị thế CK từ orders (demo dùng giá cuối cùng trong sheet)
                port_val = 0.0
                cash_net = 0.0

                if not df_orders.empty:
                    dff = df_orders[df_orders["fund_name"]==nav_fund].copy()
                    if not dff.empty:
                        dff["side"] = dff["side"].astype(str).str.upper()
                        dff["signed_qty"] = np.where(dff["side"]=="BUY", dff["qty"], -dff["qty"])
                        dff["cash_flow"] = np.where(dff["side"]=="BUY",
                                                    -(dff["qty"]*dff["price"] + dff["fee"]),
                                                    (dff["qty"]*dff["price"] - dff["fee"]))
                        cash_net += dff["cash_flow"].sum()
                        last_price = dff.sort_values("timestamp").groupby("ticker")["price"].last().reset_index()
                        pos = dff.groupby("ticker", as_index=False)["signed_qty"].sum()
                        port = pos.merge(last_price, on="ticker", how="left").fillna(0)
                        port["position_value"] = port["signed_qty"] * port["price"]
                        port_val += float(port["position_value"].sum())

                # Dòng tiền khác (nạp/rút)
                if not df_cash.empty:
                    cash_sel = df_cash[df_cash["fund_name"]==nav_fund]
                    cash_net += float(cash_sel["amount_vnd"].sum()) if not cash_sel.empty else 0.0

                # Chi phí & nợ (coi như dòng tiền âm)
                if not df_cost.empty:
                    cost_sel = df_cost[df_cost["fund_name"]==nav_fund]
                    cash_net -= float(cost_sel["amount_vnd"].sum()) if not cost_sel.empty else 0.0

                # NAV tổng = giá trị danh mục + tiền mặt ròng
                nav_total = port_val + cash_net

                row = df_info[df_info["fund_name"]==nav_fund]
                if row.empty:
                    st.warning("Không tìm thấy quỹ trong 'Tổng Quan'.")
                else:
                    try:
                        uo = float(row.iloc[0]["units_outstanding"])
                    except Exception:
                        st.warning("Cột 'units_outstanding' cần là số.")
                        st.stop()
                    if uo <= 0:
                        st.warning("units_outstanding phải > 0.")
                    else:
                        nav_per_unit = nav_total / uo
                        ensure_headers("Giá trị tài sản ròng", ["date","fund_name","nav_per_unit"])
                        append_row("Giá trị tài sản ròng", [str(nav_date), nav_fund, float(nav_per_unit)])
                        st.success(f"✅ Lưu NAV/CCQ cho {nav_fund} ngày {nav_date}: {nav_per_unit:,.2f} VND/CCQ")
                        st.caption(f"(Danh mục: {port_val:,.0f} — Tiền ròng: {cash_net:,.0f} — Tổng NAV: {nav_total:,.0f})")
                        st.cache_data.clear()
        except Exception as e:
            st.error(f"Lỗi tính NAV: {e}")

    st.divider()
    st.subheader("5) Xem nhanh dữ liệu các sheet")
    for tab in ["Tổng Quan","Danh mục đầu tư","Dòng tiền quỹ","Chi phí & nợ","Giá trị tài sản ròng","Giao dịch chứng chỉ quỹ","Thông tin khách hàng"]:
        try:
            df = read_df(tab)
            st.markdown(f"**{tab}**")
            if df.empty: st.info(f"{tab}: chưa có dữ liệu.")
            else: st.dataframe(df, use_container_width=True)
        except Exception as e:
            st.warning(f"Lỗi đọc {tab}: {e}")

# ===================== VAI TRÒ: NHÀ ĐẦU TƯ ====================
else:
    st.header("Nhà đầu tư – Xem thông tin & Gửi yêu cầu mua CCQ")

    # 1) Thông tin quỹ
    try:
        df_quan = read_df("Tổng Quan")
        st.subheader("1) Thông tin quỹ (Tổng Quan)")
        if df_quan.empty: st.info("Chưa có dữ liệu trong 'Tổng Quan'.")
        else: st.dataframe(df_quan, use_container_width=True)
    except Exception as e:
        st.error(f"Lỗi đọc 'Tổng Quan': {e}")

    # 2) NAV gần đây
    st.subheader("2) NAV gần đây (Giá trị tài sản ròng)")
    try:
        df_nav = read_df("Giá trị tài sản ròng")
        if df_nav.empty:
            st.info("Chưa có dữ liệu NAV.")
        else:
            # chọn quỹ để xem NAV
            funds = sorted(df_nav["fund_name"].astype(str).unique())
            pick = st.selectbox("Chọn quỹ để xem NAV", funds)
            nav_sel = df_nav[df_nav["fund_name"]==pick].copy()
            nav_sel["date"] = pd.to_datetime(nav_sel["date"]).dt.date
            nav_sel = nav_sel.sort_values("date")
            st.line_chart(nav_sel.set_index("date")["nav_per_unit"])
            st.dataframe(nav_sel.tail(10), use_container_width=True)
    except Exception as e:
        st.error(f"Lỗi đọc NAV: {e}")

    # 3) Gửi yêu cầu mua CCQ -> 'Giao dịch chứng chỉ quỹ'
    st.subheader("3) Gửi yêu cầu mua CCQ (ghi vào 'Giao dịch chứng chỉ quỹ')")
    with st.form("sub_form"):
        investor_name = st.text_input("Tên nhà đầu tư")
        fund_pick = st.text_input("Quỹ muốn mua", placeholder="VD: Alpha Fund")
        amount_vnd = st.number_input("Số tiền (VND)", min_value=0.0, step=1_000_000.0, format="%.0f")
        submit = st.form_submit_button("Gửi yêu cầu")
    if submit:
        if not (investor_name and fund_pick and amount_vnd>0):
            st.error("Vui lòng điền đủ thông tin.")
        else:
            try:
                ensure_headers("Giao dịch chứng chỉ quỹ", ["timestamp","investor_name","fund_name","amount_vnd","status"])
                append_row("Giao dịch chứng chỉ quỹ", [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    investor_name, fund_pick, float(amount_vnd), "PENDING"
                ])
                st.success("✅ Đã gửi yêu cầu. Chờ quỹ duyệt.")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Lỗi gửi yêu cầu: {e}")

    st.divider()
    # 4) (Tuỳ chọn) Thông tin khách hàng
    st.subheader("4) Thông tin khách hàng (nếu có)")
    try:
        df_kh = read_df("Thông tin khách hàng")
        if df_kh.empty: st.info("Chưa có dữ liệu khách hàng.")
        else: st.dataframe(df_kh, use_container_width=True)
    except Exception as e:
        st.warning(f"Lỗi đọc 'Thông tin khách hàng': {e}")



with st.expander("🔍 Kiểm tra kết nối Google Sheets (diagnostics)", expanded=False):
    # 1) In ra SHEET_ID và đọc client_email từ credentials.json
    st.write("SHEET_ID đang dùng:", st.secrets["SHEET_ID"])
    try:
        import json
        with open("credentials.json", "r", encoding="utf-8") as f:
            creds_obj = json.load(f)
        client_email = creds_obj.get("client_email", "(không thấy client_email)")
        st.write("Service Account email:", client_email)
    except Exception as e:
        st.error(f"Không đọc được credentials.json: {e}")

    # 2) List tên worksheet để đảm bảo truy cập OK
    try:
        gc = gs_client()
        sh = gc.open_by_key(st.secrets["SHEET_ID"])
        worksheets = [ws.title for ws in sh.worksheets()]
        st.write("Danh sách worksheet tìm thấy:", worksheets)
    except Exception as e:
        st.error(f"Không mở được file Sheet bằng SHEET_ID (thường do chưa share quyền Editor): {e}")

    # 3) Nút THỬ GHI vào 1 sheet bất kỳ
    test_sheet = st.selectbox("Chọn sheet để thử ghi", [
        "Danh mục đầu tư","Tổng Quan","Dòng tiền quỹ",
        "Giao dịch chứng chỉ quỹ","Chi phí & nợ","Giá trị tài sản ròng","Thông tin khách hàng"
    ])
    if st.button("➡️ Thử ghi 1 dòng test vào sheet đã chọn"):
        try:
            append_row(test_sheet, [datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "TEST_ROW"])
            st.success(f"✅ Ghi test thành công vào '{test_sheet}'. Mở Google Sheet kiểm tra nhé!")
            st.caption("Nếu ghi test OK nhưng form thật không ghi: kiểm tra lại tên cột (header) và giá trị bắt buộc.")
            st.cache_data.clear()
        except Exception as e:
            st.error(f"❌ Thử ghi thất bại: {e}")
            st.caption("Nguyên nhân hay gặp: chưa share Editor cho service account, sai SHEET_ID, hoặc tên sheet sai.")

import gspread, streamlit as st, os

@st.cache_resource
def get_gs():
    # Dùng secrets thay vì file
    return gspread.service_account_from_dict(st.secrets["gcp_service_account"])

@st.cache_resource
def get_sheet():
    return get_gs().open_by_key(st.secrets["SHEET_ID"])
