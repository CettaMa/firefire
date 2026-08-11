FROM python:3.11-slim

WORKDIR /app

# Non-buffered python output untuk log langsung terlihat di `docker logs`
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEVICE=cpu \
    MODEL_VARIANT=vj

# System dependencies untuk OpenCV & video processing (ffmpeg) + curl untuk healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependensi aplikasi
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy kode aplikasi
COPY app.py model.py tasks.py index.html ./

EXPOSE 8000

# Healthcheck untuk memastikan container siap melayani request
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
