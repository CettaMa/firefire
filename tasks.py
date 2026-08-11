import os
import time
import tempfile
import traceback
import requests
from fastapi import HTTPException
from pydantic import BaseModel
from model import get_detector

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

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
        raise ValueError(f"Gagal download video dari URL: {e}")

    downloaded_size = 0
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            downloaded_size += len(chunk)
            if downloaded_size > MAX_FILE_SIZE:
                raise ValueError("Ukuran video melebihi batas maksimal (50MB)")
            f.write(chunk)
            
    if os.path.getsize(dest_path) == 0:
        raise ValueError("Video file hasil download berukuran 0 byte / kosong.")
        
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

def process_and_notify(req_dict: dict, model_variant: str):
    """
    Background task yang akan dieksekusi oleh RQ Worker.
    Menerima dict (karena RQ serialize arguments), mendownload video, inferensi, lalu post webhook.
    """
    webhook_url = req_dict.get("webhook_url")
    if not webhook_url:
        print("[ERROR] Task dibatalkan karena tidak ada webhook_url.")
        return

    result_payload = {
        "status": "failed",
        "id": req_dict.get("id"),
        "imei": req_dict.get("imei"),
        "time": req_dict.get("time"),
        "alarm": req_dict.get("alarm"),
        "dms_video_url": req_dict.get("dms_video_url"),
        "model_variant": model_variant,
    }

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, f"{req_dict['id']}.mp4")
            
            # 1. Download
            dl_ms = download_video(req_dict["dms_video_url"], video_path)
            
            # 2. Check
            if not check_video_download(video_path):
                raise ValueError("Video gagal diunduh dengan sempurna atau file video corrupt.")
                
            file_size_kb = round(os.path.getsize(video_path) / 1024.0, 2)
            
            # 3. Inference
            detector = get_detector(model_variant)
            inf_result = detector.predict(video_path)
            
            # 4. Construct Success Payload
            result_payload.update({
                "status": "success",
                "confidence_level": f"{inf_result['confidence'] * 100:.0f}",
                "review_result": inf_result["label"],
                "process_duration": inf_result["timing"]["inference_ms"],
                "total_time": inf_result["timing"]["total_inference_ms"],
                "other": {
                    "download_time": f"{dl_ms} ms",
                    "file_size": f"{file_size_kb} kB",
                    "extract_faces_ms": inf_result["timing"]["extract_faces_ms"],
                    "inference_ms": inf_result["timing"]["inference_ms"],
                    "total_inference_ms": inf_result["timing"]["total_inference_ms"],
                }
            })
            
    except Exception as e:
        print(f"[ERROR] Task {req_dict['id']} failed: {e}", flush=True)
        traceback.print_exc()
        result_payload["error_message"] = str(e)
    
    # 5. POST to Webhook
    print(f"[TASK] Mengirim hasil POST ke webhook: {webhook_url}")
    try:
        resp = requests.post(webhook_url, json=result_payload, timeout=10)
        resp.raise_for_status()
        print(f"[TASK] Sukses POST webhook (Status: {resp.status_code})")
    except requests.RequestException as e:
        print(f"[ERROR] Gagal POST ke webhook: {e}")
