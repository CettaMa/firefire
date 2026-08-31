"""
Model definition + inference logic untuk TransTrack Yawn/Fatigue Detection.

Diadaptasi untuk format model TFLite (ai-edge-litert / tflite-runtime):
- Mendukung 10 varian model (alphabet variants va - vj):
    - va, vb, vc, vd, ve, vf, vg, vh, vi, vj
- Mendukung dynamic scanning folder model_weights untuk auto-register model baru
  (hanya varian va - vj yang terdaftar).
- Logic face-extraction (DNN face detector -> crop -> resize 224x224) dipertahankan.
- Dibungkus jadi class YawnDetector yang di-cache lewat get_detector() per-varian model.
"""
import os
import threading
import time
from typing import Optional

import cv2
import numpy as np

# Defensive import untuk interpreter TFLite
try:
    from ai_edge_litert.interpreter import Interpreter
except ImportError:
    try:
        from tflite_runtime.interpreter import Interpreter
    except ImportError:
        try:
            import tensorflow as tf
            Interpreter = tf.lite.Interpreter
        except ImportError:
            Interpreter = None

# ---------------------------------------------------------------------------
# Config & Path Helper (bisa di-override lewat environment variable)
# ---------------------------------------------------------------------------
DEVICE = "cpu"


def _resolve_path(rel_or_abs_path: str) -> str:
    """Membantu resolve path baik saat dijalankan dari root direktori maupun direktori lain."""
    if os.path.exists(rel_or_abs_path):
        return rel_or_abs_path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    alt_path = os.path.join(base_dir, rel_or_abs_path)
    if os.path.exists(alt_path):
        return alt_path
    return rel_or_abs_path


# ---------------------------------------------------------------------------
# Definisi Varian Model TFLite
# ---------------------------------------------------------------------------
STATIC_MODEL_VARIANTS = {
    # Alphabet variants (va - vj)
    "va": "model_weights/best_loss_combined_balanced_va.tflite",
    "vb": "model_weights/best_loss_combined_balanced_vb.tflite",
    "vc": "model_weights/best_loss_combined_balanced_vc.tflite",
    "vd": "model_weights/best_loss_combined_balanced_vd.tflite",
    "ve": "model_weights/best_loss_combined_balanced_ve.tflite",
    "vf": "model_weights/best_loss_combined_balanced_vf.tflite",
    "vg": "model_weights/best_loss_combined_balanced_vg.tflite",
    "vh": "model_weights/best_loss_combined_balanced_vh.tflite",
    "vi": "model_weights/best_loss_combined_balanced_vi.tflite",
    "vj": "model_weights/best_loss_combined_balanced_vj.tflite",
}


def discover_model_variants(weights_dir: str = "model_weights") -> dict[str, str]:
    """
    Memindai folder model_weights secara dinamis untuk mendeteksi semua file .tflite.
    Mendukung model berformat best_loss_combined_balanced_<name>.tflite ataupun <name>.tflite.
    """
    variants = {}
    target_dir = _resolve_path(weights_dir)
    if os.path.exists(target_dir) and os.path.isdir(target_dir):
        for fname in sorted(os.listdir(target_dir)):
            if fname.endswith(".tflite"):
                fpath = os.path.join(weights_dir, fname).replace("\\", "/")
                stem = fname[:-7]
                if stem.startswith("best_loss_combined_balanced_"):
                    short_key = stem[len("best_loss_combined_balanced_"):]
                    variants[short_key] = fpath
                else:
                    variants[stem] = fpath
    return variants


# Varian yang diizinkan: hanya alphabet variants (va - vj)
SUPPORTED_VARIANTS = {f"v{l}" for l in "abcdefghij"}


# Dictionary varian model aktif (gabungan static list dan dynamic scan folder,
# difilter hanya menyertakan varian va - vj)
MODEL_VARIANTS: dict[str, str] = {
    key: path for key, path in STATIC_MODEL_VARIANTS.items() if key in SUPPORTED_VARIANTS
}
_discovered = discover_model_variants()
if _discovered:
    for key, path in _discovered.items():
        if key in SUPPORTED_VARIANTS:
            MODEL_VARIANTS[key] = path

DEFAULT_MODEL_VARIANT = os.getenv("MODEL_VARIANT", "vj")


def resolve_model_variant(name: Optional[str]) -> str:
    """
    Menormalkan input varian model dan mencocokkan alias ke key MODEL_VARIANTS yang valid.
    Contoh:
      - 'vj' -> 'vj'
      - 'best_loss_combined_balanced_va' -> 'va'
      - 'best_loss_combined_balanced_va.tflite' -> 'va'
      - None / '' -> DEFAULT_MODEL_VARIANT
    """
    if not name:
        return DEFAULT_MODEL_VARIANT
    name_str = str(name).strip()
    if name_str in MODEL_VARIANTS:
        return name_str

    lowered = os.path.basename(name_str.lower())
    if lowered.endswith(".tflite"):
        lowered = lowered[:-7]
    if lowered.startswith("best_loss_combined_balanced_"):
        lowered = lowered[len("best_loss_combined_balanced_"):]

    if lowered in MODEL_VARIANTS:
        return lowered
    if name_str.lower() in MODEL_VARIANTS:
        return name_str.lower()

    return name_str


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

def numpy_tfms(faces):
    """Pengganti torchvision.transforms menggunakan numpy murni."""
    # Convert list of images to array, normalize to [0, 1]
    faces_np = np.stack(faces).astype(np.float32) / 255.0
    # Ubah format channel-last (H, W, C) menjadi channel-first (C, H, W)
    faces_np = np.transpose(faces_np, (0, 3, 1, 2))
    
    # Normalize ImageNet
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)
    
    return (faces_np - mean) / std

def softmax(x):
    e_x = np.exp(x - np.max(x, axis=1, keepdims=True))
    return e_x / e_x.sum(axis=1, keepdims=True)


# ---------------------------------------------------------------------------
# Face detection (OpenCV DNN). Thread-local supaya aman dipakai FastAPI
# yang bisa handle request paralel di beberapa thread.
# ---------------------------------------------------------------------------
_thread_local = threading.local()


def _get_face_net():
    if not hasattr(_thread_local, "net"):
        proto = _resolve_path(FACE_PROTOTXT)
        caffe = _resolve_path(FACE_MODEL)
        _thread_local.net = cv2.dnn.readNetFromCaffe(proto, caffe)
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
        resolved_variant = resolve_model_variant(model_variant)
        if resolved_variant not in MODEL_VARIANTS:
            raise ValueError(
                f"model_variant tidak dikenal: '{model_variant}'. "
                f"Pilihan yang valid ({len(MODEL_VARIANTS)} varian): {list(MODEL_VARIANTS.keys())}"
            )
        self.model_variant = resolved_variant
        weights_path = _resolve_path(MODEL_VARIANTS[resolved_variant])

        if not os.path.exists(weights_path):
            raise FileNotFoundError(f"File model '{weights_path}' tidak ditemukan di disk.")

        if Interpreter is None:
            raise ImportError(
                "TFLite Interpreter tidak ditemukan. Pastikan package 'ai-edge-litert' atau 'tflite-runtime' sudah terpasang."
            )

        self.device = DEVICE
        print(f"[YawnDetector] Loading TFLite model from {weights_path}...")
        self.interpreter = Interpreter(
            model_path=weights_path,
            num_threads=int(os.getenv("OMP_NUM_THREADS", "2"))
        )
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        print(f"[YawnDetector] Loaded '{resolved_variant}' ({weights_path}) successfully.")

    def predict(self, video_path: str) -> dict:
        t0 = time.perf_counter()
        faces = extract_faces(video_path)
        extract_ms = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        # Numpy transformations (No PyTorch needed)
        video_tensor = numpy_tfms(faces)
        # Expand dims to simulate Batch=1 -> [1, 20, 3, 224, 224]
        video_tensor = np.expand_dims(video_tensor, axis=0)
        transform_ms = int((time.perf_counter() - t0) * 1000)

        t0 = time.perf_counter()
        self.interpreter.set_tensor(self.input_details[0]['index'], video_tensor)
        self.interpreter.invoke()
        logits = self.interpreter.get_tensor(self.output_details[0]['index'])

        probs = softmax(logits)
        pred = np.argmax(probs, axis=1)[0]
        conf = probs[0, pred]
        inference_ms = int((time.perf_counter() - t0) * 1000)

        label = id2label[int(pred.item())]

        # Map LOOK_DOWN and LOOK_AROUND to NORMAL
        if label in ["LOOK_DOWN", "LOOK_AROUND"]:
            label = "NORMAL"

        confidence = round(float(conf.item()), 4)

        return {
            "label": label,
            "confidence": confidence,
            "timing": {
                "extract_faces_ms": extract_ms,
                "transform_ms": transform_ms,
                "inference_ms": inference_ms,
                "total_inference_ms": extract_ms + transform_ms + inference_ms,
            },
        }


# Cache 1 instance per varian model, di-load lazy lewat get_detector().
# Jadi kalau gonta-ganti model_variant antar pemanggilan, model yang PERNAH
# dipakai tidak perlu di-load ulang dari disk (cukup sekali per varian).
_detector_cache: dict[str, "YawnDetector"] = {}


def get_detector(model_variant: str = DEFAULT_MODEL_VARIANT) -> "YawnDetector":
    resolved_variant = resolve_model_variant(model_variant)
    if resolved_variant not in _detector_cache:
        _detector_cache[resolved_variant] = YawnDetector(resolved_variant)
    return _detector_cache[resolved_variant]
