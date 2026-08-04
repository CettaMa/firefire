"""
Model definition + inference logic untuk TransTrack Yawn/Fatigue Detection.

Diadaptasi dari script inference dosen (inference_vid_final_combined.py):
- Arsitektur YawNetCombined (MobileNetV2 backbone + GRU) dipertahankan PERSIS
  supaya load_state_dict() dari file .pth (vj/vc/vh) cocok.
- Logic face-extraction (DNN face detector -> crop -> resize 224x224) dipertahankan.
- Dibungkus jadi class YawnDetector yang bisa di-load per-varian model
  (vj/vc/vh, lihat MODEL_VARIANTS) dan di-cache lewat get_detector(), supaya
  tidak reload dari disk tiap kali dipanggil dengan varian yang sama.
- Input berupa link video (dms_video_url), bukan lagi path video lokal —
  urusan download video ada di run_inference.py, file ini murni model +
  inference logic saja.
"""
import os
import threading
import time

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms

# ---------------------------------------------------------------------------
# Config (bisa di-override lewat environment variable)
# ---------------------------------------------------------------------------
_requested_device = os.getenv("DEVICE", "cuda" if torch.cuda.is_available() else "cpu").lower()
if _requested_device == "cuda" and not torch.cuda.is_available():
    print("[WARNING] DEVICE=cuda diatur, tetapi PyTorch/Docker tidak mendeteksi GPU/NVIDIA Driver. Auto-fallback ke 'cpu'.")
    DEVICE = "cpu"
else:
    DEVICE = _requested_device

if DEVICE == "cpu":
    threads = int(os.getenv("OMP_NUM_THREADS", "2"))
    torch.set_num_threads(threads)
    print(f"[Config] PyTorch running on CPU (threads={threads})")


# Ada 3 varian bobot model (vj, vc, vh). Default "vj" kalau tidak dipilih.
# Kalau nanti nama file bobotnya beda, cukup ubah path di dict ini saja.
MODEL_VARIANTS = {
    "vj": "model_weights/best_loss_combined_balanced_vj.pth",
    "vc": "model_weights/best_loss_combined_balanced_vc.pth",
    "vh": "model_weights/best_loss_combined_balanced_vh.pth",
}
DEFAULT_MODEL_VARIANT = os.getenv("MODEL_VARIANT", "vj")

FACE_PROTOTXT = os.getenv(
    "FACE_PROTOTXT", "model_weights/face_detector/deploy.prototxt"
)
FACE_MODEL = os.getenv(
    "FACE_MODEL",
    "model_weights/face_detector/res10_300x300_ssd_iter_140000.caffemodel",
)
FACE_CONF_THRESHOLD = float(os.getenv("FACE_CONF_THRESHOLD", "0.2"))
TAKEN_FRAMES = int(os.getenv("TAKEN_FRAMES", "20"))

id2label = {
    0: "NORMAL",
    1: "YAWNING",
    2: "EYES_CLOSED",
    3: "LOOK_DOWN",
    4: "LOOK_AROUND",
}
label2id = {v: k for k, v in id2label.items()}

_tfms = transforms.Compose(
    [
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


# ---------------------------------------------------------------------------
# Arsitektur model — HARUS identik dengan waktu training, kalau tidak
# load_state_dict() akan error "size mismatch" / "missing keys".
# ---------------------------------------------------------------------------
class YawNetCombined(nn.Module):
    def __init__(self, num_classes=5, emb_dim=128, gru_hidden=64):
        super().__init__()
        base = models.mobilenet_v2(weights=None)
        base.classifier = nn.Identity()
        self.backbone = base

        self.compressor = nn.Sequential(
            nn.Linear(1280, emb_dim), nn.ReLU(), nn.Dropout(0.2)
        )
        self.gru = nn.GRU(
            input_size=emb_dim,
            hidden_size=gru_hidden,
            num_layers=1,
            batch_first=True,
        )
        self.classifier = nn.Linear(gru_hidden, num_classes)

    def forward(self, video):
        # video: [B, T, C, H, W]  contoh: [1, 20, 3, 224, 224]
        B, T, C, H, W = video.shape
        x = video.view(B * T, C, H, W)
        x = self.backbone(x)
        x = x.flatten(1)
        x = self.compressor(x)
        x = x.view(B, T, -1)
        gru_out, _ = self.gru(x)
        last_out = gru_out[:, -1, :]
        return self.classifier(last_out)


# ---------------------------------------------------------------------------
# Face detection (OpenCV DNN). Thread-local supaya aman dipakai FastAPI
# yang bisa handle request paralel di beberapa thread.
# ---------------------------------------------------------------------------
_thread_local = threading.local()


def _get_face_net():
    if not hasattr(_thread_local, "net"):
        _thread_local.net = cv2.dnn.readNetFromCaffe(FACE_PROTOTXT, FACE_MODEL)
    return _thread_local.net


def _detect_faces(frame, conf_threshold):
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
    net = _get_face_net()
    net.setInput(blob)
    detections = net.forward()

    boxes = []
    for i in range(detections.shape[2]):
        conf = detections[0, 0, i, 2]
        if conf > conf_threshold:
            box = detections[0, 0, i, 3:7] * [w, h, w, h]
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if (x2 - x1) > 50 and (y2 - y1) > 50:
                boxes.append((x1, y1, x2, y2, conf))
    return boxes


def _select_main_face(boxes):
    if not boxes:
        return None
    return max(boxes, key=lambda b: (b[2] - b[0]) * (b[3] - b[1]))


def _crop_face(frame, box, padding=0.3):
    x1, y1, x2, y2, _ = box
    h, w = frame.shape[:2]
    bw, bh = x2 - x1, y2 - y1
    pad_w, pad_h = int(bw * padding), int(bh * padding)
    x1 = max(0, x1 - pad_w)
    y1 = max(0, y1 - pad_h)
    x2 = min(w, x2 + pad_w)
    y2 = min(h, y2 + pad_h)
    return frame[y1:y2, x1:x2]


def extract_faces(video_path, conf_threshold=None, taken_frm=None):
    """Ambil ~taken_frm crop wajah (224x224) tersebar sepanjang video."""
    conf_threshold = FACE_CONF_THRESHOLD if conf_threshold is None else conf_threshold
    taken_frm = TAKEN_FRAMES if taken_frm is None else taken_frm

    cap = cv2.VideoCapture(str(video_path))
    fps = int(cap.get(cv2.CAP_PROP_FPS)) or 1
    fps = max(1, int(fps / 2))

    frame_id = 0
    saved_id = 0
    frame_mod = 0

    frames = []
    last_face = np.zeros((224, 224, 3), dtype="uint8")

    while cap.grab():
        if saved_id == taken_frm:
            break
        frame_id += 1
        if frame_id % fps != frame_mod:
            continue

        ret, frame = cap.retrieve()
        if not ret:
            continue

        boxes = _detect_faces(frame, conf_threshold)
        main_face = _select_main_face(boxes)

        if main_face is None:
            frames.append(last_face)
        else:
            face = _crop_face(frame, main_face)
            face_resize = cv2.resize(face, (224, 224))
            last_face = face_resize
            frames.append(face_resize)
        saved_id += 1

    while saved_id < taken_frm:
        frames.append(last_face)
        saved_id += 1

    cap.release()

    if not frames:
        raise ValueError(f"Tidak ada frame yang bisa dibaca dari video: {video_path}")

    return frames


# ---------------------------------------------------------------------------
# Wrapper publik — model di-load SEKALI, dipakai berulang lintas request
# ---------------------------------------------------------------------------
class YawnDetector:
    def __init__(self, model_variant: str = DEFAULT_MODEL_VARIANT):
        if model_variant not in MODEL_VARIANTS:
            raise ValueError(
                f"model_variant tidak dikenal: '{model_variant}'. "
                f"Pilihan yang valid: {list(MODEL_VARIANTS.keys())}"
            )
        self.model_variant = model_variant
        weights_path = MODEL_VARIANTS[model_variant]

        self.device = DEVICE
        self.model = YawNetCombined(num_classes=len(id2label)).to(self.device)
        state_dict = torch.load(weights_path, map_location=torch.device(self.device))
        self.model.load_state_dict(state_dict)
        self.model.eval()
        print(f"[YawnDetector] Loaded '{model_variant}' ({weights_path}) on device={self.device}")

    def predict(self, video_path: str) -> dict:
        t0 = time.perf_counter()
        faces = extract_faces(video_path)
        extract_ms = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        video_tensor = torch.stack([_tfms(f) for f in faces])
        transform_ms = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(video_tensor.unsqueeze(0).to(self.device))
            probs = F.softmax(logits, dim=1)
            conf, pred = probs.max(dim=1)
        inference_ms = int((time.perf_counter() - t0) * 1000)

        label = id2label[int(pred.item())]
        confidence = round(float(conf.item()), 4)

        return {
            "label": label,
            "confidence": confidence,
            "timing": {
                "extract_faces_ms": extract_ms,
                "transform_ms": transform_ms,
                "inference_ms": inference_ms,
            },
        }


# Cache 1 instance per varian model, di-load lazy lewat get_detector().
# Jadi kalau gonta-ganti model_variant antar pemanggilan, model yang PERNAH
# dipakai tidak perlu di-load ulang dari disk (cukup sekali per varian).
_detector_cache: dict[str, "YawnDetector"] = {}


def get_detector(model_variant: str = DEFAULT_MODEL_VARIANT) -> "YawnDetector":
    if model_variant not in _detector_cache:
        _detector_cache[model_variant] = YawnDetector(model_variant)
    return _detector_cache[model_variant]
