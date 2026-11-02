# Gambar runtime ramping: ffmpeg sudah termasuk agar fitur stiker dan
# penggabungan video/audio YouTube langsung jalan.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg wajib untuk stiker dan merge video+audio; curl untuk healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Folder data harus writable oleh user non-root (SQLite menulis di sini).
RUN useradd --create-home --uid 10001 bot \
    && mkdir -p /app/data \
    && chown -R bot:bot /app
USER bot

# Bot berjalan dengan long polling, jadi tidak ada port yang dibuka.
HEALTHCHECK --interval=60s --timeout=10s --start-period=20s --retries=3 \
    CMD pgrep -f "main.py" > /dev/null || exit 1

CMD ["python", "main.py"]
