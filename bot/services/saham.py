import yfinance as yf
from re import fullmatch


def ambil_data_saham(kode_emiten):
    return yf.Ticker(kode_emiten).history(period="1d")


def validasi_kode_emiten(kode_input):
    if not kode_input:
        return False

    kode = kode_input.upper().strip()
    if kode == "^JKSE":
        return True

    return bool(fullmatch(r"[A-Z0-9]{1,4}", kode))


def format_kode_emiten(kode_input):
    kode = kode_input.upper().strip()
    if kode == "^JKSE":
        return kode
    if kode.endswith(".JK"):
        return kode
    return f"{kode}.JK"
