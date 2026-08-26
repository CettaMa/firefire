"""
API server untuk TransTrack Yawn Detection.

Membungkus YawnDetector (model.py) jadi HTTP API menggunakan FastAPI:
- Mendukung 19 varian model TFLite (v1-v9, va-vj).
- Mendukung pemrosesan Sinkron (langsung respon hasil, cocok untuk UI Tester).
- Mendukung pemrosesan Asinkron dengan Redis Queue (RQ) saat webhook_url diberikan.

Endpoints:
    GET  /                  -> info status API
    GET  /health            -> cek server hidup + device + koneksi redis + daftar model
    GET  /models            -> info detail 19 model varian yang terintegrasi
    POST /predict           -> inferensi sinkron / antrean asinkron (jika ada webhook_url)
    POST /warmup            -> opsional: preload varian model ke memori
    GET  /tester            -> halaman landing page UI
"""
import os
import tempfile
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
from model import (
    MODEL_VARIANTS,
    DEFAULT_MODEL_VARIANT,
    DEVICE,
    get_detector,
    resolve_model_variant,
)
from tasks import process_and_notify, download_video, check_video_download

# Disable warning SSL untuk server MDVR dengan sertifikat self-signed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(
    title="TransTrack Yawn Detection API",
    version="2.2.0",
    description="API Deteksi Kantuk TransTrack dengan 19 Varian Model TFLite",
)

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
        raise HTTPException(
            status_code=403,
            detail="Akses ditolak: API Key tidak valid atau tidak diberikan.",
        )
    return api_key


# Setup Redis Queue
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
try:
    redis_conn = Redis.from_url(REDIS_URL)
    task_queue = Queue("yawn_tasks", connection=redis_conn)
except Exception:
    redis_conn = None
    task_queue = None


# ---------------------------------------------------------------------------
# Schema request/response
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    id: str
    imei: str
    time: str
    alarm: str
    dms_video_url: str
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL yang akan di-POST setelah pemrosesan selesai (opsional; jika diisi, task diproses asinkron via antrean).",
    )
    model: Optional[str] = Field(
        default=None,
        description=f"Varian model yang digunakan ({len(MODEL_VARIANTS)} varian: {list(MODEL_VARIANTS.keys())}). Default: {DEFAULT_MODEL_VARIANT}",
    )


# ---------------------------------------------------------------------------
# Startup Event
# ---------------------------------------------------------------------------
@app.on_event("startup")
def startup_event():
    print(f"[startup] Redis URL: {REDIS_URL}")
    print(f"[startup] Total model terdaftar: {len(MODEL_VARIANTS)} varian")
    print(f"[startup] Preloading model default '{DEFAULT_MODEL_VARIANT}' (device={DEVICE}) ...")
    try:
        get_detector(DEFAULT_MODEL_VARIANT)
        print("[startup] Model default siap.")
    except Exception as e:
        print(f"[startup] GAGAL load model default: {e}")


# ---------------------------------------------------------------------------
# Endpoints Umum & Manajemen Model
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "service": "TransTrack Yawn Detection API",
        "version": "2.2.0",
        "status": "ok",
        "total_models": len(MODEL_VARIANTS),
        "default_model": DEFAULT_MODEL_VARIANT,
        "endpoints": {
            "health_check": "/health",
            "models_list": "/models",
            "docs": "/docs",
            "tester_page": "/tester",
            "predict": "/predict",
        },
    }


@app.get("/tester")
def tester_page():
    """Melayani file index.html sebagai landing page testing API."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"error": "index.html tidak ditemukan di path: " + html_path}


@app.get("/health")
@app.get("/api/status")
def health():
    redis_status = "disconnected"
    queue_len = 0
    if redis_conn:
        try:
            redis_conn.ping()
            redis_status = "connected"
            queue_len = len(task_queue) if task_queue else 0
        except Exception:
            redis_status = "disconnected"

    return {
        "status": "ok",
        "device": DEVICE,
        "redis_status": redis_status,
        "queue_length": queue_len,
        "total_models": len(MODEL_VARIANTS),
        "available_model_variants": list(MODEL_VARIANTS.keys()),
        "default_model_variant": DEFAULT_MODEL_VARIANT,
    }


@app.get("/models")
def list_models():
    """Mengembalikan daftar lengkap seluruh 19 model varian yang terintegrasi."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    models_info = []
    for key, path in MODEL_VARIANTS.items():
        full_path = path if os.path.isabs(path) else os.path.join(base_dir, path)
        models_info.append({
            "id": key,
            "label": f"Variant {key.upper()}",
            "filename": os.path.basename(path),
            "is_default": (key == DEFAULT_MODEL_VARIANT),
            "available": os.path.exists(full_path),
        })
    return {
        "total": len(models_info),
        "default_model": DEFAULT_MODEL_VARIANT,
        "models": models_info,
    }


@app.post("/warmup")
def warmup(model: Optional[str] = None, api_key: str = Depends(verify_api_key)):
    """Preload satu varian model tertentu (atau semua) ke cache tanpa jalanin inference."""
    if model:
        resolved = resolve_model_variant(model)
        if resolved not in MODEL_VARIANTS:
            raise HTTPException(
                status_code=400,
                detail=f"model_variant tidak dikenal: '{model}'. Pilihan: {list(MODEL_VARIANTS.keys())}",
            )
        variants = [resolved]
    else:
        variants = list(MODEL_VARIANTS.keys())

    loaded = []
    for v in variants:
        get_detector(v)
        loaded.append(v)
    return {"status": "ok", "loaded": loaded}


# ---------------------------------------------------------------------------
# Endpoint Inti (Inference Sinkron & Asinkron)
# ---------------------------------------------------------------------------
@app.post("/predict")
async def predict(req: PredictRequest, api_key: str = Depends(verify_api_key)):
    model_variant = resolve_model_variant(req.model)
    if model_variant not in MODEL_VARIANTS:
        raise HTTPException(
            status_code=400,
            detail=f"model_variant tidak dikenal: '{req.model}'. Pilihan ({len(MODEL_VARIANTS)} model): {list(MODEL_VARIANTS.keys())}",
        )

    # 1. Mode Asinkron via Redis Queue (jika webhook_url disediakan)
    if req.webhook_url and req.webhook_url.strip():
        if not task_queue:
            raise HTTPException(
                status_code=503,
                detail="Layanan antrean Redis tidak aktif untuk mode asinkron.",
            )
        try:
            job = task_queue.enqueue(
                process_and_notify,
                req.model_dump() if hasattr(req, "model_dump") else req.dict(),
                model_variant,
                job_timeout="5m",
                result_ttl=86400,
            )
            return {
                "status": "queued",
                "job_id": job.get_id(),
                "model_variant": model_variant,
                "message": "Video telah masuk ke antrean pemrosesan. Hasil akan di-POST ke webhook_url.",
                "queue_position": len(task_queue),
            }
        except Exception as e:
            print(f"[ERROR] Gagal memasukkan tugas ke queue: {e}", flush=True)
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Gagal enqueue task: {e}")

    # 2. Mode Sinkron (langsung proses & kembalikan hasil JSON, cocok untuk UI Tester)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, f"{req.id}.mp4")

            dl_ms = download_video(req.dms_video_url, video_path)

            if not check_video_download(video_path):
                raise HTTPException(
                    status_code=400,
                    detail="Video gagal diunduh dengan sempurna atau file video kosong/corrupt.",
                )

            file_size_kb = round(os.path.getsize(video_path) / 1024.0, 2)

            detector = get_detector(model_variant)
            inf_result = detector.predict(video_path)

            return {
                "status": "success",
                "id": req.id,
                "imei": req.imei,
                "time": req.time,
                "alarm": req.alarm,
                "dms_video_url": req.dms_video_url,
                "model_variant": model_variant,
                "confidence_level": f"{inf_result['confidence'] * 100:.0f}",
                "review_result": inf_result["label"],
                "process_duration": inf_result["timing"]["inference_ms"],
                "total_time": inf_result["timing"]["total_inference_ms"],
                "other": {
                    "download_time": f"{dl_ms} ms",
                    "file_size": f"{file_size_kb} kB",
                    "extract_faces_ms": inf_result["timing"]["extract_faces_ms"],
                    "transform_ms": inf_result["timing"]["transform_ms"],
                    "inference_ms": inf_result["timing"]["inference_ms"],
                    "total_inference_ms": inf_result["timing"]["total_inference_ms"],
                },
            }
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] Gagal proses video sinkron: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal memproses video: {e}")
