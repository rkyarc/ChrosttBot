import os
import subprocess
import sys
import time
from pathlib import Path

from watchfiles import PythonFilter, watch


process = None
ROOT = Path(__file__).resolve().parent

# Folder yang tidak perlu memicu restart
DIABAIKAN = {".git", ".venv", "venv", "__pycache__", "downloads", ".pytest_cache", ".ruff_cache"}


def _abaikan(path: str) -> bool:
    bagian = Path(path).parts
    return any(nama in bagian for nama in DIABAIKAN)


def start_bot():
    """Jalankan main.py dengan interpreter yang sama (venv aktif)."""
    global process
    print("[DEV] Starting bot...")
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

    process = subprocess.Popen(
        [sys.executable, str(ROOT / "main.py")],
        cwd=str(ROOT),
        creationflags=creationflags,
    )


def stop_bot():
    """Matikan proses bot secara bersih (terminate -> kill kalau bandel)."""
    global process
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
            else:
                process.kill()
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
        for changes in watch(
            ROOT,
            watch_filter=PythonFilter(),
            ignore_permission_denied=True,
        ):
            if changes and all(_abaikan(path) for _, path in changes):
                continue

            nama_file = ", ".join(sorted({os.path.basename(path) for _, path in changes}))
            print(f"\n[DEV] Perubahan terdeteksi: {nama_file} -> restarting...")
            stop_bot()
            time.sleep(2)  # jeda biar sesi Telegram sempat terlepas
            start_bot()
    except KeyboardInterrupt:
        print("\n[DEV] Stopped.")

    stop_bot()
