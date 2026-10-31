import html
import re

BATAS_TELEGRAM = 3800

# Tag yang dipertahankan saat memotong pesan panjang
_TAG_BALANCE = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "code", "pre", "blockquote", "a",
}

_TAG_RE = re.compile(r"<(/?)([a-zA-Z]+)([^>]*)>")


def format_angka_rupiah(nilai, desimal=False):
    if nilai is None:
        return "-"

    if desimal:
        angka = f"{float(nilai):,.2f}"
    else:
        angka = f"{int(float(nilai)):,}"

    return angka.replace(",", "X").replace(".", ",").replace("X", ".")


def escape_html(teks):
    """Amankan teks eksternal agar tidak merusak parse_mode HTML."""
    return (
        str(teks or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def potong_teks(teks: str, batas: int = BATAS_TELEGRAM) -> list[str]:
    """Pecah teks polos jadi beberapa bagian, mengutamakan batas paragraf."""
    teks = (teks or "").strip()
    if not teks:
        return []
    if len(teks) <= batas:
        return [teks]

    bagian = []
    sisa = teks
    while len(sisa) > batas:
        potong = sisa.rfind("\n\n", 0, batas)
        if potong < batas // 2:
            potong = sisa.rfind("\n", 0, batas)
        if potong < batas // 2:
            potong = sisa.rfind(" ", 0, batas)
        if potong < batas // 4:
            potong = batas
        bagian.append(sisa[:potong].rstrip())
        sisa = sisa[potong:].lstrip()

    if sisa:
        bagian.append(sisa)
    return bagian


def _tag_terbuka(teks: str) -> list[str]:
    """Kembalikan daftar tag pembuka yang belum ditutup."""
    tumpukan = []
    for tutup, nama, _attrs in _TAG_RE.findall(teks):
        nama = nama.lower()
        if nama not in _TAG_BALANCE:
            continue
        if tutup:
            if nama in tumpukan:
                while tumpukan and tumpukan.pop() != nama:
                    pass
        else:
            tumpukan.append(nama)
    return tumpukan


def potong_html(teks: str, batas: int = BATAS_TELEGRAM) -> list[str]:
    """Pecah teks berisi HTML tanpa memotong tag, sambil menutup/membuka tag per bagian."""
    teks = (teks or "").strip()
    if not teks:
        return []
    if len(teks) <= batas:
        return [teks]

    bagian = []
    sisa = teks

    while len(sisa) > batas:
        jendela = sisa[:batas]
        potong = max(
            jendela.rfind("\n\n"),
            jendela.rfind("\n"),
            jendela.rfind(" "),
        )
        if potong < batas // 3:
            potong = batas

        potongan = sisa[:potong].rstrip()

        # Jangan biarkan potongan berakhir di tengah tag
        tag_awal = potongan.rfind("<")
        if tag_awal > potongan.rfind(">"):
            potongan = potongan[:tag_awal].rstrip()

        if not potongan:
            potongan = sisa[:batas]

        terbuka = _tag_terbuka(potongan)
        penutup = "".join(f"</{nama}>" for nama in reversed(terbuka))

        bagian.append(potongan + penutup)
        sisa = "".join(f"<{nama}>" for nama in terbuka) + sisa[len(potongan):].lstrip()

    if sisa.strip():
        bagian.append(sisa)

    return bagian


def ke_telegram_html(teks: str) -> str:
    """Konversi markdown ringan dari model ke HTML yang didukung Telegram."""
    aman = escape_html(teks)

    aman = re.sub(
        r"```(?:[a-zA-Z0-9_+-]+)?\n?(.*?)```",
        lambda m: "<pre>" + m.group(1).strip() + "</pre>",
        aman,
        flags=re.S,
    )
    aman = re.sub(r"`([^`\n]+)`", r"<code>\1</code>", aman)
    aman = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", aman)
    aman = re.sub(r"__([^_\n]+)__", r"<b>\1</b>", aman)
    aman = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", aman)
    aman = re.sub(r"^#{1,6}\s*(.+)$", r"<b>\1</b>", aman, flags=re.M)
    aman = re.sub(r"^\s*[-*+]\s+", "• ", aman, flags=re.M)
    aman = re.sub(r"^\s*(\d+)[.)]\s+", r"\1. ", aman, flags=re.M)
    return aman.strip()


def strip_html(teks: str) -> str:
    """Buang tag HTML setelah di-unescape, untuk fallback plain text."""
    return html.unescape(re.sub(r"<[^>]+>", "", teks or ""))
