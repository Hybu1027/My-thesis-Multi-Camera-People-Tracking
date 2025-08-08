import qrcode
import requests
import matplotlib.pyplot as plt

def get_ngrok_url():
    try:
        res = requests.get("http://127.0.0.1:4040/api/tunnels")
        tunnels = res.json()["tunnels"]
        for t in tunnels:
            if t["proto"] == "https":
                return t["public_url"]
        return "Không tìm thấy URL công khai"
    except:
        return "Không kết nối được với ngrok"

# Bước 1: Lấy URL từ ngrok
url = get_ngrok_url()
print(f"🔗 Public URL: {url}")

# Bước 2: Tạo mã QR từ URL
qr_img = qrcode.make(url)

# Bước 3: Hiển thị mã QR bằng matplotlib
plt.figure(figsize=(6, 6))
plt.imshow(qr_img, cmap="gray")
plt.title("Quét mã QR để truy cập hệ thống", fontsize=14)
plt.axis("off")
plt.tight_layout()
plt.show()
