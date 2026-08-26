"""
Script untuk menjalankan YawNetCombined dari input "request" (bukan lagi
path video lokal), sesuai skema yang dipakai backend TransTrack:

    id, imei, time, alarm, dms_video_url

Video akan didownload dulu dari dms_video_url, baru diproses.
Kamu juga bisa pilih mau pakai model varian yang mana: vj, vc, atau vh
(lihat MODEL_VARIANTS di model.py).

Cara pakai PALING GAMPANG — cukup jalankan tanpa argumen apa pun,
nanti akan ditanya satu-satu di terminal:
    python run_inference.py

Cara pakai lewat argumen CLI (kalau mau otomatisasi / skip tanya-tanya):
    python run_inference.py \
        --id VID123 \
        --imei 862345061234567 \
        --time "2026-08-04T10:00:00Z" \
        --alarm "yawn_alert" \
        --url "https://contoh.com/video/1770249621660000030867395078090442.mp4" \
        --model vj

Atau lewat file JSON (isinya persis field2 di atas):
    python run_inference.py --json contoh_request.json --model vc

Kalau --model tidak diisi (baik mode CLI maupun interaktif kosong Enter),
default-nya "vj".

Kalau mau pakai GPU:
    $env:DEVICE="cuda"        # PowerShell
    python run_inference.py ...

Prasyarat: environment python sudah install semua isi requirements.txt
(lihat file itu untuk cara setup env-nya).
"""
import argparse
import json
import os
import sys
import tempfile
import time

import requests

from model import (
    MODEL_VARIANTS,
    DEFAULT_MODEL_VARIANT,
    get_detector,
    resolve_model_variant,
)


def download_video(url: str, dest_path: str, timeout: int = 30) -> int:
    """Download video dari URL ke dest_path. Return waktu download (ms)."""
    t0 = time.perf_counter()
    resp = requests.get(url, stream=True, timeout=timeout)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(8192):
            f.write(chunk)
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


def prompt_request_interactively() -> tuple[dict, str]:
    """Tanya id/imei/time/alarm/url/model satu-satu di terminal."""
    print("=== Isi data request (Enter kosong = pakai nilai default) ===")
    video_id = input("id            : ").strip() or "unknown_id"
    imei = input("imei          : ").strip() or "unknown_imei"
    req_time = input("time          : ").strip() or "unknown_time"
    alarm = input("alarm         : ").strip() or "unknown_alarm"

    url = ""
    while not url:
        url = input("dms_video_url : ").strip()
        if not url:
            print("  -> dms_video_url wajib diisi, tidak boleh kosong.")

    model_variant = ""
    while not model_variant:
        print(f"\nPilihan varian model ({len(MODEL_VARIANTS)} varian):")
        print("  - Huruf : va, vb, vc, vd, ve, vf, vg, vh, vi, vj")
        print("  - Angka : v1, v2, v3, v4, v5, v6, v7, v8, v9")
        raw = input(f"model (default: {DEFAULT_MODEL_VARIANT}): ").strip()
        chosen = resolve_model_variant(raw) if raw else DEFAULT_MODEL_VARIANT
        if chosen in MODEL_VARIANTS:
            model_variant = chosen
        else:
            print(f"  -> pilihan '{raw}' tidak dikenal, pilih salah satu dari daftar.")

    request_data = {
        "id": video_id,
        "imei": imei,
        "time": req_time,
        "alarm": alarm,
        "dms_video_url": url,
    }
    return request_data, model_variant


def build_request_from_args(args) -> dict:
    if args.json:
        with open(args.json, "r", encoding="utf-8") as f:
            data = json.load(f)
        required = ["id", "imei", "time", "alarm", "dms_video_url"]
        missing = [k for k in required if k not in data]
        if missing:
            print(f"Field wajib hilang di JSON: {missing}")
            sys.exit(1)
        return data

    return {
        "id": args.id or "unknown_id",
        "imei": args.imei or "unknown_imei",
        "time": args.time or "unknown_time",
        "alarm": args.alarm or "unknown_alarm",
        "dms_video_url": args.url,
    }


def main():
    parser = argparse.ArgumentParser(description="Jalankan inference yawn detection dari request video URL.")
    parser.add_argument("--id", help="id video/job")
    parser.add_argument("--imei", help="IMEI device")
    parser.add_argument("--time", help="timestamp kejadian")
    parser.add_argument("--alarm", help="jenis alarm dari device")
    parser.add_argument("--url", dest="url", help="dms_video_url (link video yang mau diproses)")
    parser.add_argument("--json", help="path ke file JSON berisi id/imei/time/alarm/dms_video_url (alternatif dari isi satu-satu lewat argumen)")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL_VARIANT,
        help=f"varian model yang dipakai: {list(MODEL_VARIANTS.keys())} (default: {DEFAULT_MODEL_VARIANT})",
    )
    args = parser.parse_args()

    if args.json or args.url:
        # Mode CLI: semua data sudah diisi lewat argumen.
        request_data = build_request_from_args(args)
        model_variant = resolve_model_variant(args.model)
        if model_variant not in MODEL_VARIANTS:
            print(f"Error: Model '{args.model}' tidak dikenal. Pilihan: {list(MODEL_VARIANTS.keys())}")
            sys.exit(1)
    else:
        # Mode interaktif: tidak ada --url/--json sama sekali -> tanya di terminal.
        request_data, model_variant = prompt_request_interactively()

    print(f"\n[1/3] Loading model '{model_variant}' (device={os.getenv('DEVICE', 'cpu')}) ...")
    t0 = time.perf_counter()
    detector = get_detector(model_variant)
    print(f"      Model loaded dalam {time.perf_counter() - t0:.2f} detik")

    print(f"[2/3] Download video dari: {request_data['dms_video_url']}")
    with tempfile.TemporaryDirectory() as tmp_dir:
        video_path = os.path.join(tmp_dir, f"{request_data['id']}.mp4")
        try:
            dl_ms = download_video(request_data["dms_video_url"], video_path)
        except Exception as e:
            print(f"Gagal download video: {e}")
            sys.exit(1)
            
        if not check_video_download(video_path):
            print("Gagal download video: Video corrupt atau kosong.")
            sys.exit(1)
            
        file_size_kb = round(os.path.getsize(video_path) / 1024.0, 2)
        print(f"      Selesai dalam {dl_ms} ms ({file_size_kb} kB)")

        print("[3/3] Menjalankan inference ...")
        result = detector.predict(video_path)

    output = {
        "status": "success",
        "id": request_data["id"],
        "imei": request_data["imei"],
        "time": request_data["time"],
        "alarm": request_data["alarm"],
        "dms_video_url": request_data["dms_video_url"],
        "model_variant": model_variant,
        "confidence_level": f"{result['confidence'] * 100:.0f}",
        "review_result": result["label"],
        "process_duration": result["timing"]["inference_ms"],
        "other": {
            "download_time": f"{dl_ms} ms",
            "file_size": f"{file_size_kb} kB",
            "extract_faces_ms": result["timing"]["extract_faces_ms"],
            "transform_ms": result["timing"]["transform_ms"],
        },
    }

    print("\n================ HASIL ================")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print("=========================================")


if __name__ == "__main__":
    main()
