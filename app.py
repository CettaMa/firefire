"""
API server untuk TransTrack Yawn Detection.

Membungkus YawnDetector (model.py) jadi HTTP API, jadi bisa di-hit dari
backend TransTrack (atau device lain) tanpa perlu jalanin script CLI manual.

Endpoints:
    GET  /health            -> cek server hidup + device (cpu/cuda) + model yang sudah ke-load
    POST /predict            -> body JSON: {id, imei, time, alarm, dms_video_url, model (opsional)}
                                 balikin hasil deteksi (label, confidence, timing)
    POST /warmup              -> opsional: preload salah satu/semua varian model dari awal
                                 (biar request pertama gak kena cold-start loading model)

Jalanin lokal (tanpa docker) buat testing:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""
import os
import tempfile
import time
import traceback
from typing import Optional

import requests
import urllib3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from model import MODEL_VARIANTS, DEFAULT_MODEL_VARIANT, DEVICE, get_detector

# Disable warning SSL untuk server MDVR dengan sertifikat self-signed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI(title="TransTrack Yawn Detection API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



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
# Helper
# ---------------------------------------------------------------------------
def download_video(url: str, dest_path: str, timeout: int = 45) -> int:
    """Download video dari URL ke dest_path dengan toleransi SSL. Return waktu download (ms)."""
    t0 = time.perf_counter()
    headers = {"User-Agent": "TransTrack-YawnAPI/1.0"}
    try:
        resp = requests.get(url, stream=True, timeout=timeout, verify=False, headers=headers)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"[ERROR] Download video gagal: {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"Gagal download video dari URL: {e}")

    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
            
    if os.path.getsize(dest_path) == 0:
        raise HTTPException(status_code=400, detail="Video file hasil download berukuran 0 byte / kosong.")
        
    return int((time.perf_counter() - t0) * 1000)



# ---------------------------------------------------------------------------
# Startup: preload model default biar request pertama gak lambat
# ---------------------------------------------------------------------------
@app.on_event("startup")
def preload_default_model():
    print(f"[startup] Preloading model default '{DEFAULT_MODEL_VARIANT}' (device={DEVICE}) ...")
    try:
        get_detector(DEFAULT_MODEL_VARIANT)
        print("[startup] Model default siap.")
    except Exception as e:
        # Jangan crash server kalau gagal load di startup — biar bisa keliatan
        # errornya lewat log dan endpoint /health, daripada container langsung mati.
        print(f"[startup] GAGAL load model default: {e}")


# ---------------------------------------------------------------------------
# Endpoints
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
def warmup(model: Optional[str] = None):
    """Preload satu varian model tertentu (atau semua) ke cache tanpa jalanin inference."""
    variants = [model] if model else list(MODEL_VARIANTS.keys())
    loaded = []
    for v in variants:
        if v not in MODEL_VARIANTS:
            raise HTTPException(status_code=400, detail=f"model_variant tidak dikenal: '{v}'")
        get_detector(v)
        loaded.append(v)
    return {"status": "ok", "loaded": loaded}


@app.post("/predict")
def predict(req: PredictRequest):
    model_variant = req.model or DEFAULT_MODEL_VARIANT
    if model_variant not in MODEL_VARIANTS:
        raise HTTPException(
            status_code=400,
            detail=f"model_variant tidak dikenal: '{model_variant}'. Pilihan: {list(MODEL_VARIANTS.keys())}",
        )

    try:
        detector = get_detector(model_variant)
    except Exception as e:
        print(f"[ERROR] Gagal load model '{model_variant}': {e}", flush=True)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Gagal load model '{model_variant}': {e}")

    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = os.path.join(tmp_dir, f"{req.id}.mp4")
        dl_ms = download_video(req.dms_video_url, video_path)
        file_size_kb = int(os.path.getsize(video_path) / 1000)

        try:
            result = detector.predict(video_path)
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
        "other": {
            "download_time": f"{dl_ms} ms",
            "file_size": f"{file_size_kb} kB",
            "extract_faces_ms": result["timing"]["extract_faces_ms"],
            "inference_ms": result["timing"]["inference_ms"],
        },
    }
