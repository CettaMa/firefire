# TransTrack Yawn Detection API

API Server berbasis FastAPI dan PyTorch (MobileNetV2 + GRU) untuk deteksi kantuk/menguap pada pengemudi berdasarkan URL video DMS.

## 🚀 Fitur Utama
- **Ringan & Cepat**: Image Docker sudah dioptimasi khusus CPU (`~650 MB`).
- **Multi-Model Variant**: Mendukung varian bobot model `vj`, `vc`, dan `vh`.
- **Preload & Cache**: Model di-cache di memori agar pemanggilan inferensi cepat.
- **Toleran SSL/MDVR**: Dapat mengunduh video dari server MDVR dengan sertifikat tersuai (custom/self-signed).

---

## 🛠️ Cara Deploy via GitHub ke VPS

### 1. Push ke GitHub (Dari PC Lokal)
```bash
git add .
git commit -m "feat: setup Docker CPU deployment & GitHub ready"
git branch -M main
git remote add origin https://github.com/username-anda/transtrackapi.git
git push -u origin main
```

### 2. Clone & Run di VPS
Masuk ke terminal VPS Anda lewat SSH:
```bash
# Clone repository
git clone https://github.com/username-anda/transtrackapi.git /opt/transtrackapi
cd /opt/transtrackapi

# Build & jalankan Docker container
sudo docker compose up --build -d
```

### 3. Cek Status Container
```bash
# Cek apakah container berjalan & healthy
sudo docker ps

# Cek log aplikasi
sudo docker logs -f transtrack-yawn-api
```

---

## 📌 Endpoints API

| Method | Endpoint | Deskripsi |
| :--- | :--- | :--- |
| `GET` | `/` | Informasi status layanan |
| `GET` | `/health` / `/api/status` | Health check layanan & model ter-load |
| `GET` | `/docs` | Interactive Swagger UI API Docs |
| `POST` | `/predict` | Menjalankan deteksi kantuk dari JSON request |
| `POST` | `/warmup` | Preload model ke cache memori |

### Contoh Request Body (`POST /predict`):
```json
{
  "id": "VID_20260804_001",
  "imei": "862345061234567",
  "time": "2026-08-04T22:00:00Z",
  "alarm": "yawn_alert",
  "dms_video_url": "https://example.com/sample_video.mp4",
  "model": "vj"
}
```
