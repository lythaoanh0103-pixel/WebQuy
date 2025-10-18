import streamlit_authenticator as stauth

# Danh sách mật khẩu gốc — bạn có thể đổi tuỳ ý
passwords = ["adminpass123", "investorpass123"]

# Hàm tạo chuỗi băm (hash) để bảo mật
hashed = stauth.Hasher(passwords).generate()

print("✅ Mã băm tạo thành công:")
for i, h in enumerate(hashed, start=1):
    print(f"User {i}: {h}")