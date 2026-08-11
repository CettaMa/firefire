"""
API server untuk TransTrack Yawn Detection.

Membungkus YawnDetector (model.py) jadi HTTP API menggunakan arsitektur Asynchronous dengan RQ (Redis Queue).

Endpoints:
    GET  /health            -> cek server hidup + device + koneksi redis
    POST /predict           -> memasukkan tugas pemrosesan ke antrean (non-blocking)
    POST /warmup            -> opsional: preload varian model
    GET  /tester            -> halaman landing page UI
"""
import os
import traceback
from typing import Optional

import urllib3
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from redis import Redis
from rq import Queue
from model import MODEL_VARIANTS, DEFAULT_MODEL_VARIANT, DEVICE, get_detector
from tasks import process_and_notify

# Disable warning SSL untuk server MDVR dengan sertifikat self-signed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="TransTrack Yawn Detection API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Keamanan & Antrean (RQ)
# ---------------------------------------------------------------------------
API_KEY = os.getenv("API_KEY", "trans_track_secret_123")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Akses ditolak: API Key tidak valid atau tidak diberikan.")
    return api_key

# Setup Redis Queue
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
task_queue = Queue("yawn_tasks", connection=redis_conn)

# ---------------------------------------------------------------------------
# Schema request/response
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    id: str
    imei: str
    time: str
    alarm: str
    dms_video_url: str
    webhook_url: str = Field(..., description="URL yang akan di-POST setelah pemrosesan selesai.")
    model: Optional[str] = Field(
        default=None,
        description=f"Varian model: {list(MODEL_VARIANTS.keys())}. Default: {DEFAULT_MODEL_VARIANT}",
    )


# ---------------------------------------------------------------------------
# Startup Event
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    print(f"[startup] Terhubung ke Redis: {REDIS_URL}")
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
    try:
        redis_conn.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"
        
    return {
        "status": "ok",
        "device": DEVICE,
        "redis_status": redis_status,
        "queue_length": len(task_queue),
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
# Endpoint Inti (Inference Asinkron)
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
        # Masukkan tugas ke antrean RQ
        job = task_queue.enqueue(
            process_and_notify,
            req.dict(), 
            model_variant,
            job_timeout='5m', # Maksimal waktu pemrosesan 5 menit
            result_ttl=86400  # Simpan ID job selama 1 hari
        )
        
        return {
            "status": "queued",
            "job_id": job.get_id(),
            "message": "Video telah masuk ke antrean pemrosesan. Hasil akan di-POST ke webhook_url.",
            "queue_position": len(task_queue)
        }
        
    except Exception as e:
        print(f"[ERROR] Gagal memasukkan tugas ke queue: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal enqueue task: {e}")
