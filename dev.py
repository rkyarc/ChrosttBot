import os
import subprocess
import sys
import time

from watchfiles import watch, PythonFilter


process = None


def start_bot():
    """Jalankan main.py dengan python venv (sys.executable)."""
    global process
    print("[DEV] Starting bot...")
    process = subprocess.Popen([sys.executable, "main.py"])


def stop_bot():
    """Matikan proses bot secara bersih (terminate -> kill kalau bandel)."""
    global process
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    process = None


if __name__ == "__main__":
    print("[DEV] Mode auto-reload aktif. Edit file .py -> bot restart otomatis.")
    print("[DEV] Tekan Ctrl+C untuk berhenti.\n")

    start_bot()

    try:
        # watch() akan "bangun" setiap ada file .py yang berubah
        for changes in watch(".", watch_filter=PythonFilter()):
            nama_file = ", ".join(
                sorted({os.path.basename(path) for _, path in changes})
            )
            print(f"\n[DEV] Perubahan terdeteksi: {nama_file} -> restarting...")
            stop_bot()
            time.sleep(1)  # jeda biar sesi Telegram sempat terlepas
            start_bot()
    except KeyboardInterrupt:
        stop_bot()
        print("\n[DEV] Stopped.")