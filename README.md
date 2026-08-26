# TransTrack Yawn Detection API

API Server berbasis FastAPI dan TensorFlow Lite (ai-edge-litert) untuk deteksi kantuk/menguap pada pengemudi berdasarkan URL video DMS.

## 🚀 Fitur Utama
- **Ringan & Cepat**: Menggunakan runtime TensorFlow Lite / ai-edge-litert yang dioptimasi khusus CPU.
- **19 Multi-Model Variants**: Mendukung 19 varian bobot model:
  - **Model Huruf (10 varian)**: `va`, `vb`, `vc`, `vd`, `ve`, `vf`, `vg`, `vh`, `vi`, `vj` (default: `vj`).
  - **Model Angka (9 varian)**: `v1`, `v2`, `v3`, `v4`, `v5`, `v6`, `v7`, `v8`, `v9`.
- **Dynamic Model Discovery**: Otomatis mendeteksi dan mendaftarkan file `.tflite` baru di folder `model_weights/`.
- **Dual Processing Modes**:
  - **Mode Sinkron**: Mengembalikan hasil inferensi langsung (ideal untuk pengujian via UI `/tester`).
  - **Mode Asinkron (Redis Queue)**: Mengantrekan pekerjaan dan mengirimkan notifikasi hasil via `webhook_url`.
- **Preload & Cache**: Model di-cache di memori agar pemanggilan inferensi cepat.
- **Toleran SSL/MDVR**: Dapat mengunduh video dari server MDVR dengan sertifikat tersuai (custom/self-signed).
- **Interactive Web Tester**: Dilengkapi antarmuka web modern di `/tester`.

---

## 🛠️ Cara Deploy via GitHub ke VPS

### 1. Push ke GitHub (Dari PC Lokal)
```bash
git add .
git commit -m "feat: integrate 19 model variants and dynamic UI"
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
| `GET` | `/` | Informasi status layanan & daftar rute |
| `GET` | `/health` / `/api/status` | Health check layanan, device, Redis & daftar model |
| `GET` | `/models` | Daftar lengkap seluruh 19 varian model terintegrasi |
| `GET` | `/tester` | Web UI Testing Platform untuk uji coba model |
| `GET` | `/docs` | Interactive Swagger UI API Docs |
| `POST` | `/predict` | Menjalankan deteksi kantuk (Sinkron / Asinkron via `webhook_url`) |
| `POST` | `/warmup` | Preload model tertentu ke cache memori |

### Contoh Request Body (`POST /predict`):

**Mode 1: Sinkron (Hasil Langsung)**
```json
{
  "id": "VID_20260804_001",
  "imei": "862345061234567",
  "time": "2026-08-04T22:00:00Z",
  "alarm": "EYES_CLOSED",
  "dms_video_url": "https://example.com/sample_video.mp4",
  "model": "vj"
}
```

**Mode 2: Asinkron (Notifikasi Webhook)**
```json
{
  "id": "VID_20260804_001",
  "imei": "862345061234567",
  "time": "2026-08-04T22:00:00Z",
  "alarm": "EYES_CLOSED",
  "dms_video_url": "https://example.com/sample_video.mp4",
  "webhook_url": "https://your-server.com/api/webhook",
  "model": "v1"
}
```
