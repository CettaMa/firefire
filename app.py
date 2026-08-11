"""
API server untuk TransTrack Yawn Detection.

Membungkus YawnDetector (model.py) jadi HTTP API, jadi bisa di-hit dari
backend TransTrack (atau device lain) tanpa perlu jalanin script CLI manual.

Endpoints:
    GET  /health            -> cek server hidup + device (cpu/cuda) + model yang sudah ke-load
    POST /predict           -> memproses video dengan limitasi konkurensi, file size, dan API Key
    POST /warmup            -> opsional: preload varian model
    GET  /tester            -> halaman landing page UI

Jalanin lokal (tanpa docker) buat testing:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import tempfile
import time
import traceback
import asyncio
from typing import Optional

import requests
import urllib3
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from model import MODEL_VARIANTS, DEFAULT_MODEL_VARIANT, DEVICE, get_detector

# Disable warning SSL untuk server MDVR dengan sertifikat self-signed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="TransTrack Yawn Detection API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Keamanan (API Key) & Batasan (Limits)
# ---------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY", "trans_track_secret_123")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Akses ditolak: API Key tidak valid atau tidak diberikan.")
    return api_key

MAX_FILE_SIZE = 50 * 1024 * 1024  # Maksimal 50 MB
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "2"))
prediction_semaphore = None


# ---------------------------------------------------------------------------
# Schema request/response
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    id: str
    imei: str
    time: str
    alarm: str
    dms_video_url: str
    model: Optional[str] = Field(
        default=None,
        description=f"Varian model: {list(MODEL_VARIANTS.keys())}. Default: {DEFAULT_MODEL_VARIANT}",
    )


# ---------------------------------------------------------------------------
# Helper (Download & Inference)
# ---------------------------------------------------------------------------
def download_video(url: str, dest_path: str, timeout: int = 45) -> int:
    """Download video dari URL ke dest_path dengan batasan memori/ukuran file."""
    t0 = time.perf_counter()
    headers = {"User-Agent": "TransTrack-YawnAPI/2.0"}
    try:
        resp = requests.get(url, stream=True, timeout=timeout, verify=False, headers=headers)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Download video gagal: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Gagal download video dari URL: {e}")

    downloaded_size = 0
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            downloaded_size += len(chunk)
            if downloaded_size > MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="Ukuran video melebihi batas maksimal (50MB)")
            f.write(chunk)
            
    if os.path.getsize(dest_path) == 0:
        raise HTTPException(status_code=400, detail="Video file hasil download berukuran 0 byte / kosong.")
        
    return int((time.perf_counter() - t0) * 1000)

def check_video_download(video_path: str) -> bool:
    """Mengecek apakah file video berhasil diunduh, tidak kosong, dan valid/bisa dibaca."""
    if not os.path.exists(video_path):
        return False
    if os.path.getsize(video_path) == 0:
        return False
        
    import cv2
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return False
    
    # Cek apakah ada frame yang bisa dibaca
    ret, _ = cap.read()
    cap.release()
    return ret

def process_inference_task(req: PredictRequest, model_variant: str, tmp_dir: str):
    """Fungsi berat yang dijalankan di background thread agar tidak memblokir antrean server"""
    video_path = os.path.join(tmp_dir, f"{req.id}.mp4")
    dl_ms = download_video(req.dms_video_url, video_path)
    
    # Cek apakah video valid dan bisa dibaca
    if not check_video_download(video_path):
        raise HTTPException(status_code=400, detail="Video gagal diunduh dengan sempurna atau file video corrupt.")
        
    file_size_kb = round(os.path.getsize(video_path) / 1024.0, 2)

    detector = get_detector(model_variant)
    result = detector.predict(video_path)
    
    return dl_ms, file_size_kb, result



# ---------------------------------------------------------------------------
# Startup Event
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    global prediction_semaphore
    prediction_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    print(f"[startup] Menginisialisasi Semaphore dengan kapasitas maksimal {MAX_CONCURRENT_TASKS} request paralel.")
    
    print(f"[startup] Preloading model default '{DEFAULT_MODEL_VARIANT}' (device={DEVICE}) ...")
    try:
        get_detector(DEFAULT_MODEL_VARIANT)
        print("[startup] Model default siap.")
    except Exception as e:
        print(f"[startup] GAGAL load model default: {e}")


# ---------------------------------------------------------------------------
# Endpoints Umum
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "TransTrack Yawn Detection API",
        "status": "ok",
        "health_check": "/health",
        "docs": "/docs",
        "tester_page": "/tester"
    }

@app.get("/tester")
def tester_page():
    """Melayani file index.html sebagai landing page testing API."""
    import os
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"error": "index.html tidak ditemukan di path: " + html_path}

@app.get("/health")
@app.get("/api/status")
def health():
    return {
        "status": "ok",
        "device": DEVICE,
        "available_model_variants": list(MODEL_VARIANTS.keys()),
        "default_model_variant": DEFAULT_MODEL_VARIANT,
    }

@app.post("/warmup")
def warmup(model: Optional[str] = None, api_key: str = Depends(verify_api_key)):
    """Preload satu varian model tertentu (atau semua) ke cache tanpa jalanin inference."""
    variants = [model] if model else list(MODEL_VARIANTS.keys())
    loaded = []
    for v in variants:
        if v not in MODEL_VARIANTS:
            raise HTTPException(status_code=400, detail=f"model_variant tidak dikenal: '{v}'")
        get_detector(v)
        loaded.append(v)
    return {"status": "ok", "loaded": loaded}


# ---------------------------------------------------------------------------
# Endpoint Inti (Inference)
# ---------------------------------------------------------------------------
@app.post("/predict")
async def predict(req: PredictRequest, api_key: str = Depends(verify_api_key)):
    model_variant = req.model or DEFAULT_MODEL_VARIANT
    if model_variant not in MODEL_VARIANTS:
        raise HTTPException(
            status_code=400,
            detail=f"model_variant tidak dikenal: '{model_variant}'. Pilihan: {list(MODEL_VARIANTS.keys())}",
        )
        
    try:
        # Pastikan model sudah diload ke memory
        get_detector(model_variant)
    except Exception as e:
        print(f"[ERROR] Gagal load model '{model_variant}': {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal load model '{model_variant}': {e}")

    # Menggunakan semaphore agar memori & CPU tidak OOM/Hang saat ribuan request masuk bersamaan
    async with prediction_semaphore:
        with tempfile.TemporaryDirectory() as tmp_dir:
            try:
                # Jalankan fungsi sinkron berat (download & inference) di threadpool
                dl_ms, file_size_kb, result = await run_in_threadpool(
                    process_inference_task, req, model_variant, tmp_dir
                )
            except HTTPException:
                raise
            except Exception as e:
                print(f"[ERROR] Gagal menjalankan inference: {e}", flush=True)
                traceback.print_exc()
                raise HTTPException(status_code=500, detail=f"Gagal menjalankan inference: {e}")

    return {
        "status": "success",
        "id": req.id,
        "imei": req.imei,
        "time": req.time,
        "alarm": req.alarm,
        "dms_video_url": req.dms_video_url,
        "model_variant": model_variant,
        "confidence_level": f"{result['confidence'] * 100:.0f}",
        "review_result": result["label"],
        "process_duration": result["timing"]["inference_ms"],
        "total_time": result["timing"]["total_inference_ms"],
        "other": {
            "download_time": f"{dl_ms} ms",
            "file_size": f"{file_size_kb} kB",
            "extract_faces_ms": result["timing"]["extract_faces_ms"],
            "inference_ms": result["timing"]["inference_ms"],
            "total_inference_ms": result["timing"]["total_inference_ms"],
        },
    }
