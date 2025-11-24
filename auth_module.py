# auth_module.py  — phiên bản đã sửa: header khớp, login gate đúng nhánh, có return & rerun
import streamlit as st
import pandas as pd
from datetime import date
import bcrypt
from gsheets_core import ensure_headers, read_df, append_row

USERS_WS = "Users"
# Thứ tự cột TRÙNG KHỚP với dữ liệu sẽ ghi
USERS_HEADERS = [
    "username","display_name","email",
    "CCCD/MST","DOB","SĐT","ADDRESS","STK",
    "pw_hash","role","fund"   # ✅ thêm "fund" để đủ 11 cột
]

# ================== KHỞI TẠO TÀI KHOẢN ADMIN (CHỈ QUỸ THẤY) ================== #
def init_admin_account():
    """
    Đảm bảo luôn có 1 tài khoản admin trong Users sheet.
    Nếu chưa có -> tự thêm 1 dòng admin với pw_hash cố định.
    """
    # 1. Đảm bảo header đúng
    ensure_headers(USERS_WS, USERS_HEADERS)

    # 2. Đọc dữ liệu hiện có
    df = read_df(USERS_WS)

    has_admin = False
    if (df is not None) and (not df.empty):
        if "username" in df.columns:
            if "role" in df.columns:
                has_admin = ((df["username"] == "admin") & (df["role"] == "admin")).any()
            else:
                has_admin = (df["username"] == "admin").any()

    if has_admin:
        return  # đã có admin rồi thì thôi

    # 3. Nếu chưa có admin -> thêm 1 dòng mới
    admin_row = [
        "admin",                         # username
        "Gold Snake Fund",                      # display_name
        "ksjdjjio@gmail.com",             # email
        "913917238",                     # CCCD/MST
        "1999-01-01",                    # DOB (chuỗi yyyy-mm-dd)
        "187396",                    # SĐT
        "Hà Nội",                        # ADDRESS
        "123",                           # STK
        # pw_hash (bcrypt) cho mật khẩu 1aA@#$234
        "$2b$12$sGJTxZQIfk8VRKzfyo4Vo.HIfaJ4ZI06YWqHWBWyv8agxCfPtwZwG",
        "admin",                         # role
        "ALL",                           # fund
    ]

    append_row(USERS_WS, admin_row)

def init_users_sheet_once():
    ensure_headers(USERS_WS, USERS_HEADERS)


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt(12)).decode("utf-8")

def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

def _normalize_phone(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def signup_view():
    st.header("Đăng ký tài khoản")
    with st.form("signup_form"):
        display_name = st.text_input("Họ tên *")
        email        = st.text_input("Email")
        username     = st.text_input("Username *")
        pw1          = st.text_input("Mật khẩu *", type="password")
        pw2          = st.text_input("Nhập lại *", type="password")

        role_label   = st.selectbox("Vai trò", ["Nhà đầu tư cá nhân", "Tổ chức", "Quỹ"])
        fund_name    = ""
        if role_label == "Quỹ":
            fund_name = st.text_input("Tên quỹ *", placeholder="VD: Alpha Fund")

        cccd_mst     = st.text_input("CCCD/MST *")
        dob_value    = st.date_input("DOB (Ngày sinh/Ngày ĐK) *", value=date(1990,1,1))
        phone_raw    = st.text_input("SĐT *", placeholder="VD: 0901234567")
        address      = st.text_area("ADDRESS", placeholder="Số nhà, đường, phường/xã, quận/huyện, tỉnh/thành")
        bank_acct    = st.text_input("STK (Số tài khoản ngân hàng)")
        agree        = st.checkbox("Tôi đồng ý điều khoản")
        submit       = st.form_submit_button("Đăng ký")

    if not submit:
        return

    # --- Kiểm tra ---
    if not (display_name and username and pw1 and pw2 and pw1 == pw2 and len(pw1) >= 8):
        st.error("Thiếu thông tin hoặc mật khẩu không hợp lệ (>= 8 ký tự)."); return
    if role_label == "Quỹ" and not fund_name.strip():
        st.error("Vui lòng nhập Tên quỹ."); return
    if not (cccd_mst and phone_raw and dob_value):
        st.error("Vui lòng điền đủ CCCD/MST, SĐT và DOB."); return
    if not agree:
        st.error("Bạn cần đồng ý điều khoản."); return

    # Tránh trùng username
    df = read_df(USERS_WS)
    if not df.empty and "username" in df.columns:
        if username in df["username"].astype(str).values:
            st.error("Username đã tồn tại."); return

    role_value = (
        "investor" if role_label == "Nhà đầu tư cá nhân"
        else "org" if role_label == "Tổ chức"
        else "fund"
    )
    phone = _normalize_phone(phone_raw)

    # ✅ Ghi đúng THỨ TỰ 11 cột như USERS_HEADERS
    row = [
        username,                  # username
        display_name,              # display_name
        email,                     # email
        cccd_mst.strip(),          # CCCD/MST
        dob_value.isoformat(),     # DOB
        phone,                     # SĐT
        address.strip(),           # ADDRESS
        bank_acct.strip(),         # STK
        hash_pw(pw1),              # pw_hash
        role_value,                # role
        fund_name.strip(),         # fund
    ]
    append_row(USERS_WS, row)
    st.success("Đăng ký thành công. Bạn có thể đăng nhập ngay.")
    try: st.cache_data.clear()
    except: pass

def login_view():
    st.header("Đăng nhập")
    with st.form("login_form"):
        username = st.text_input("Username")
        pw       = st.text_input("Mật khẩu", type="password")
        ok       = st.form_submit_button("Đăng nhập")

    if not ok:
        return

    df = read_df(USERS_WS)
    if df.empty or "username" not in df.columns:
        st.error("Chưa có tài khoản."); return

    m = df["username"].astype(str) == username
    if not m.any():
        st.error("Sai username."); return

    row = df[m].iloc[0]

    if not verify_pw(pw, str(row.get("pw_hash",""))):
        st.error("Sai mật khẩu."); return   # ✅ PHẢI return ở đây

    # ---- Đăng nhập thành công ----
    st.session_state.update({
        "auth": True,                                 # ✅ set ngay trong nhánh thành công
        "username": username,
        "display_name": row.get("display_name", ""),
        "email": row.get("email", ""),
        "role": row.get("role", "investor"),
        "fund": row.get("fund", ""),
    })
    st.success(f"Xin chào {st.session_state['display_name'] or username}!")
    st.rerun()  # ✅ rerun để login gate ẩn form