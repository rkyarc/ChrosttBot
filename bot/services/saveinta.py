import os
import re
import sys
import json
import logging
import html as _html
import urllib.parse
import requests

log = logging.getLogger("chrosttbot.saveinta")


class SaveInta:
    BASE_URL = "https://saveinta.com/en"
    API_URL  = "https://saveinta.com/api/ajaxSearch"
    CHARSET  = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "*/*",
            "accept-language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "origin": "https://saveinta.com",
            "referer": "https://saveinta.com/en",
            "sec-ch-ua": '"Not=A?Brand";v="99", "Google Chrome";v="151", "Chromium";v="151"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"iOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_6 like Mac OS X) "
                           "AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/151.0.0.0 "
                           "Mobile/15E148 Safari/604.1"),
            "x-requested-with": "XMLHttpRequest",
        })
        self.k_exp = None
        self.k_token = None

    # ---------- 0) HELPER DECRYPT OBFUSCATION ----------
    @classmethod
    def _base_convert(cls, value_str, from_base, to_base):
        if not value_str:
            return ""
        val = 0
        for ch in value_str:
            idx = cls.CHARSET.find(ch)
            if idx == -1 or idx >= from_base:
                raise ValueError(f"Invalid char '{ch}' untuk base {from_base}")
            val = val * from_base + idx
        target = cls.CHARSET[:to_base]
        if val == 0:
            return target[0]
        out = ""
        while val > 0:
            out = target[val % to_base] + out
            val //= to_base
        return out

    @classmethod
    def decode_saveinta(cls, encrypted_str):
        pattern = re.compile(
            r'\}\s*\(\s*"(.*?)"\s*,\s*(\d+)\s*,\s*"(.*?)"\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)',
            re.DOTALL,
        )
        m = pattern.search(encrypted_str)
        if not m:
            pattern2 = re.compile(
                r"\}\s*\(\s*'(.*?)'\s*,\s*(\d+)\s*,\s*'(.*?)'\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)",
                re.DOTALL,
            )
            m = pattern2.search(encrypted_str)
        if not m:
            raise ValueError("Argumen eval tidak ketemu. Pastikan pakai response JSON LENGKAP.")

        h = m.group(1).encode().decode("unicode_escape")
        n = m.group(3).encode().decode("unicode_escape")
        t = int(m.group(4))
        e = int(m.group(5))
        delimiter = n[e]

        result_chars = []
        i = 0
        while i < len(h):
            s = ""
            while i < len(h) and h[i] != delimiter:
                s += h[i]
                i += 1
            i += 1
            for j, c in enumerate(n):
                s = s.replace(c, str(j))
            num = int(cls._base_convert(s, e, 10)) - t
            result_chars.append(chr(num))

        return urllib.parse.unquote("".join(result_chars))

    # ---------- 1) SCRAPE k_exp & k_token ----------
    def refresh_tokens(self):
        r = self.session.get(self.BASE_URL, timeout=30)
        r.raise_for_status()
        m_exp = re.search(r'k_exp\s*=\s*"(\d+)"', r.text)
        m_tok = re.search(r'k_token\s*=\s*"([0-9a-fA-F]{32,})"', r.text)
        if not m_exp or not m_tok:
            raise RuntimeError("k_exp/k_token tidak ketemu (kemungkinan kena challenge Cloudflare).")
        self.k_exp, self.k_token = m_exp.group(1), m_tok.group(1)

    # ---------- 2) PANGGIL API ajaxSearch ----------
    def search(self, ig_url):
        if not (self.k_exp and self.k_token):
            self.refresh_tokens()
        payload = {
            "k_exp": self.k_exp,
            "k_token": self.k_token,
            "q": ig_url,
            "t": "media",
            "lang": "en",
            "v": "v2",
            "cftoken": "",
        }
        r = self.session.post(self.API_URL, data=payload, timeout=60)
        r.raise_for_status()
        resp = r.json()
        if not resp.get("data") and resp.get("status") != "ok":
            self.refresh_tokens()
            payload["k_exp"], payload["k_token"] = self.k_exp, self.k_token
            resp = self.session.post(self.API_URL, data=payload, timeout=60).json()
        return resp

    def extract_media(self, ig_url):
        """Ambil dan parse media Instagram dari sebuah URL."""
        return self.parse_media(self.search(ig_url))

    # ---------- 3) PARSER BERBASIS STRUKTUR KARTU (<li>) ----------
    @staticmethod
    def _split_cards(html_text):
        """1 <li> = 1 media. Kalau nggak ada <li>, fallback ke blok thumb."""
        cards = re.findall(r'<li\b.*?</li>', html_text, re.S)
        if not cards:
            cards = re.findall(
                r'<div[^>]*download-items__thumb.*?(?=<div[^>]*download-items__thumb|$)',
                html_text, re.S)
        return cards

    @staticmethod
    def _classify(u):
        """Klasifikasi URL ke VIDEO atau FOTO berdasarkan domain/ekstensi."""
        if "/photo" in u or re.search(r'\.(jpe?g|png|webp)([?#]|$)|/t51\.2885', u):
            return "FOTO"
        if re.search(r'\.mp4([?#]|$)|/t50\.2886|/video', u):
            return "VIDEO"
        if "snapcdn" in u:
            return "VIDEO"
        if re.search(r'cdninstagram|fbcdn|scontent', u):
            return "FOTO"
        return None

    @staticmethod
    def _parse_card(card):
        """Parse SATU kartu -> (jenis, url). Ambil 1 URL terbaik per kartu."""
        # Cek indikasi icon / tag yang biasanya lebih akurat daripada isi URL mentah.
        is_video_icon = any(x in card for x in ["icon-dlvideo", "icon-video", "fa-video", "fa-film", "play-icon", "video-icon"])
        is_image_icon = any(x in card for x in ["icon-dlimage", "icon-image", "fa-image", "fa-picture", "image-icon"])
        has_video_tag = "<video" in card.lower()
        has_image_tag = "<img" in card.lower()
        plain_text = re.sub(r"<[^>]+>", " ", card)
        plain_text = re.sub(r"\s+", " ", plain_text).strip().lower()
        has_video_hint = "download video" in plain_text or "video" in plain_text
        has_image_hint = "download image" in plain_text or "image" in plain_text
        has_audio_hint = any(keyword in plain_text for keyword in ["audio", "music", "sound", "song", "mp3", "m4a", "voice"])

        # semua <option value="..."> (daftar resolusi)
        options = []
        for attrs, _label in re.findall(r'<option\b([^>]*)>(.*?)</option>', card, re.S):
            mv = re.search(r'value=["\']([^"\']+)["\']', attrs)
            if mv:
                options.append((attrs, mv.group(1)))

        # semua <a href="...">
        anchors = re.findall(r'<a\b([^>]*)href=["\']([^"\']+)["\']([^>]*)>(.*?)</a>', card, re.S)

        video_href, image_href = None, None
        for attrs, href, _tail, text in anchors:
            low = text.lower()
            if "video" in attrs or "download video" in low:
                video_href = video_href or href
            elif "download image" in low or "download" in low:
                image_href = image_href or href

        # === FALLBACK PENTING: Ekstrak semua URL di kartu dan klasifikasikan ===
        all_urls = []
        for u in re.findall(r"""https?://[^\s"'<>\\]+""", card):
            if "saveinta.com" in u: continue
            u = u.rstrip('";,')
            all_urls.append(u)
            
        video_urls = [u for u in all_urls if SaveInta._classify(u) == "VIDEO"]
        image_urls = [u for u in all_urls if SaveInta._classify(u) == "FOTO"]

        # Kartu audio-only dari Instagram tidak dianggap sebagai media yang dikirim.
        if has_audio_hint and not (is_video_icon or has_video_tag or video_href or video_urls or has_image_tag or image_href or image_urls):
            return "AUDIO", None

        # Kalau kartu menampilkan penanda video yang jelas, utamakan video.
        if is_video_icon or video_href or has_video_tag or has_video_hint:
            url = video_href or (video_urls[0] if video_urls else None) or (anchors[0][1] if anchors else None)
            return "VIDEO", url

        # Kalau kartu menampilkan penanda foto yang jelas, utamakan foto.
        if is_image_icon or image_href or has_image_tag or has_image_hint or image_urls:
            url = None
            for attrs, val in options:
                if "selected" in attrs:
                    url = val
                    break
            url = url or (options[0][1] if options else None) or image_href or (image_urls[0] if image_urls else None)
            return "FOTO", url

        # --- FOTO ---
        if is_image_icon or options or image_href or image_urls:
            url = None
            for attrs, val in options:
                if "selected" in attrs:
                    url = val
                    break
            url = url or (options[0][1] if options else None) or image_href or (image_urls[0] if image_urls else None)
            return "FOTO", url

        return None, None

    def parse_media(self, resp):
        videos, images, items = [], [], []
        data_field = resp.get("data", "")
        is_obfuscated = isinstance(data_field, str) and data_field.lstrip().startswith("var _0x")

        if is_obfuscated:
            log.debug("[*] Data ter-obfuscate, decrypting ...")
            html_text = _html.unescape(self.decode_saveinta(data_field))
            log.debug(f"[+] Decrypt sukses, panjang: {len(html_text)} karakter")
        else:
            log.debug("[*] Data plaintext, parsing langsung ...")
            html_text = _html.unescape(data_field if isinstance(data_field, str) else "")

        cards = self._split_cards(html_text)
        log.debug(f"[+] Ditemukan {len(cards)} kartu media")

        if cards:
            for card in cards:
                kind, url = self._parse_card(card)
                if kind == "VIDEO" and url and url not in videos:
                    videos.append(url)
                    items.append(("VIDEO", url))
                elif kind == "FOTO" and url and url not in images:
                    images.append(url)
                    items.append(("FOTO", url))
                elif kind is None:
                    # Debug log kalau kartu gagal di-parse
                    log.debug(f"[!] Gagal parse kartu. Potongan isi kartu: {card[:150].strip()}...")
                elif kind == "AUDIO":
                    log.debug(f"[!] Skip kartu audio-only. Potongan isi kartu: {card[:150].strip()}...")
        else:
            # fallback terakhir: sapu semua URL (jarang kepake)
            for u in re.findall(r"""https?://[^\s"'<>\\]+""", html_text):
                if "saveinta.com" in u or u in videos or u in images: continue
                kind = self._classify(u)
                if kind == "FOTO":
                    images.append(u)
                    items.append(("FOTO", u))
                elif kind == "VIDEO":
                    videos.append(u)
                    items.append(("VIDEO", u))

        return {"videos": videos, "images": images, "items": items}

    # ---------- 4) SIMPAN FILE ----------
    @staticmethod
    def save_file(url, folder="downloads", name=None, default_ext=".mp4"):
        os.makedirs(folder, exist_ok=True)
        r = requests.get(url, stream=True, timeout=120, headers={
            "user-agent": "Mozilla/5.0", "referer": "https://www.instagram.com/"})
        r.raise_for_status()

        ctype = r.headers.get("content-type", "").split(";")[0].strip()
        ext_map = {"video/mp4": ".mp4", "video/webm": ".webm",
                   "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        if ctype in ext_map:
            ext = ext_map[ctype]
        elif ctype.startswith("video"):
            ext = ".mp4"
        elif ctype.startswith("image"):
            ext = ".jpg"
        else:
            ext = default_ext

        if name is None:
            base = re.sub(r'[^\w.-]', '_', url.split("?")[0].rstrip("/").split("/")[-1]) or "media"
            name = base if os.path.splitext(base)[1] else base + ext
        elif not os.path.splitext(name)[1]:
            name += ext

        path = os.path.join(folder, name)
        with open(path, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)
        log.debug(f"    (content-type: {ctype or 'unknown'} -> {ext})")
        return path

    @staticmethod
    def unduh_media(url, timeout=120):
        """Download media Instagram sebagai bytes."""
        r = requests.get(
            url,
            stream=True,
            timeout=timeout,
            headers={
                "user-agent": "Mozilla/5.0",
                "referer": "https://www.instagram.com/",
            },
        )
        r.raise_for_status()
        return r.content


def main():
    link = sys.argv[1] if len(sys.argv) > 1 else input("Link Instagram: ").strip()
    bot = SaveInta()

    log.debug("[*] scraping k_exp & k_token dari saveinta.com/en ...")
    bot.refresh_tokens()
    log.debug("[+] k_exp & k_token ditemukan (isi disembunyikan)")

    log.debug("[*] request ajaxSearch ...")
    resp = bot.search(link)

    media = bot.parse_media(resp)
    if not media["videos"] and not media["images"]:
        log.debug("[!] Media tidak ketemu. Raw response buat debug:")
        log.debug(json.dumps(resp, indent=2)[:3000])
        return

    all_media = media.get("items") or [("VIDEO", u) for u in media["videos"]] + [("FOTO", u) for u in media["images"]]
    for i, (t, u) in enumerate(all_media, 1):
        log.debug(f"[{i}] {t}: {u[:120]}")

    for i, (t, u) in enumerate(all_media, 1):
        log.debug(f"[*] download {t} #{i} ...")
        path = bot.save_file(u, name=f"{i:02d}_{t.lower()}",
                             default_ext=".mp4" if t == "VIDEO" else ".jpg")
        log.debug(f"[+] tersimpan: {path}")


if __name__ == "__main__":
    main()