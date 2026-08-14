import os
import sys
import json
import time
import uuid
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer

# ==========================================
# Konfigurasi
# ==========================================
API_URL = "http://localhost:8000/predict"
API_KEY = "trans_track_secret_123"
NUM_REQUESTS = 10

# Kita pakai host.docker.internal agar container worker bisa mengirim POST 
# kembali ke komputer host (laptop Anda) tempat script ini berjalan.
WEBHOOK_PORT = 9090
WEBHOOK_URL = f"http://host.docker.internal:{WEBHOOK_PORT}/webhook"

# Dummy video URL (pastikan URL ini valid & bisa didownload cepat untuk testing)
TEST_VIDEO_URL = "https://raw.githubusercontent.com/intel-iot-devkit/sample-videos/master/head-pose-face-detection-female-and-male.mp4"

# Global state untuk melacak selesainya program
completed_tasks = 0
tasks_lock = threading.Lock()
all_done_event = threading.Event()

# ==========================================
# 1. Mini Webhook Server
# ==========================================
class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        global completed_tasks
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            data = json.loads(post_data.decode('utf-8'))
            print(f"\n[WEBHOOK DITERIMA] Job ID: {data.get('id')}")
            # Cetak seluruh isi JSON agar kelihatan rapi
            print(json.dumps(data, indent=2))
        except Exception as e:
            print(f"\n[WEBHOOK ERROR] Gagal parsing JSON: {e}")

        # Beri respon OK ke worker
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
        
        # Tambah counter
        with tasks_lock:
            completed_tasks += 1
            if completed_tasks >= NUM_REQUESTS:
                all_done_event.set()
        
    def log_message(self, format, *args):
        # Matikan log default HTTP server agar rapi
        pass

def run_webhook_server():
    server = HTTPServer(('0.0.0.0', WEBHOOK_PORT), WebhookHandler)
    print(f"[*] Webhook Server berjalan di port {WEBHOOK_PORT}...")
    server.serve_forever()

# ==========================================
# 2. Main Logic: Tembak API Secara Paralel
# ==========================================
def main():
    # Jalankan webhook server di thread terpisah (background)
    webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
    webhook_thread.start()
    
    # Tunggu sebentar agar server siap
    time.sleep(1)
    
    print(f"[*] Akan mengirim {NUM_REQUESTS} request ke API secara beruntun...")
    
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }
    
    start_time = time.perf_counter()
    
    for i in range(NUM_REQUESTS):
        req_id = f"test-job-{uuid.uuid4().hex[:6]}"
        payload = {
            "id": req_id,
            "imei": f"IMEI-TEST-{i+1}",
            "time": "2023-10-10 10:00:00",
            "alarm": "yawn_detected",
            "dms_video_url": TEST_VIDEO_URL,
            "webhook_url": WEBHOOK_URL,
            "model": "vj"
        }
        
        try:
            resp = requests.post(API_URL, json=payload, headers=headers)
            if resp.status_code == 200:
                print(f"[API] Sukses mengirim {req_id} -> {resp.json().get('message')} (Antrean: {resp.json().get('queue_position')})")
            else:
                print(f"[API] Gagal mengirim {req_id}: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"[API] Error koneksi: {e}")
            
    api_time = time.perf_counter() - start_time
    print(f"\n[*] Selesai mengirim {NUM_REQUESTS} request dalam {api_time:.2f} detik.")
    print("[*] Sekarang tinggal menunggu hasil webhook dari Worker...")
    
    # Tunggu sampai event ditandai selesai (maksimal tunggu sekian detik/menit jika perlu)
    try:
        # Tunggu sampai selesai (tidak batas waktu)
        finished = all_done_event.wait(timeout=600)  
        if finished:
            print("\n[*] Semua webhook telah berhasil diterima! Program akan keluar otomatis.")
        else:
            print("\n[*] Timeout menunggu webhook.")
    except KeyboardInterrupt:
        print("\n[*] Dibatalkan secara manual (Ctrl+C).")
    finally:
        # Karena daemon=True, thread server akan otomatis mati saat exit
        os._exit(0)

if __name__ == "__main__":
    main()
