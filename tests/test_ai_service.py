"""Uji lapisan service AI tanpa jaringan.

Yang dikunci: pemetaan error gateway, parsing JSON yang kadang bercampur
sisa SSE, normalisasi konten, dan alur tool calling.
"""

import unittest
from unittest import mock

import config
from bot.services import ai


class NormalisasiKontenTest(unittest.TestCase):
    def test_string_dikembalikan_apa_adanya(self):
        self.assertEqual(ai._normalisasi_konten("halo"), "halo")

    def test_list_part_digabung(self):
        parts = [{"type": "text", "text": "a"}, {"text": "b"}]
        self.assertEqual(ai._normalisasi_konten(parts), "ab")

    def test_list_campuran(self):
        self.assertEqual(ai._normalisasi_konten(["x", {"text": "y"}]), "xy")

    def test_none_menghasilkan_kosong(self):
        self.assertEqual(ai._normalisasi_konten(None), "")


class MuatJsonTest(unittest.TestCase):
    def test_json_biasa(self):
        self.assertEqual(ai._muat_json('{"a": 1}'), {"a": 1})

    def test_sisa_sse_di_belakang_diabaikan(self):
        """Gateway menempelkan sisa SSE setelah JSON; json.loads akan gagal."""
        teks = '{"a": 1}\n\ndata: [DONE]'
        self.assertEqual(ai._muat_json(teks), {"a": 1})

    def test_body_bukan_json_melempar(self):
        with self.assertRaises(ValueError):
            ai._muat_json("<html>502 Bad Gateway</html>")

    def test_kosong_melempar(self):
        with self.assertRaises(ValueError):
            ai._muat_json("")


class PesanErrorTest(unittest.TestCase):
    def test_model_tidak_diizinkan_walau_403(self):
        body = '{"error": {"code": "insufficient_quota", "message": "not allowed to use model x"}}'
        pesan = ai._pesan_error(403, body)
        self.assertIn("tidak tersedia untuk API key", pesan)

    def test_model_tidak_ditemukan(self):
        body = '{"error": {"code": "unknown", "message": "model not found"}}'
        self.assertIn("tidak tersedia", ai._pesan_error(404, body))

    def test_api_key_invalid(self):
        self.assertIn("API key", ai._pesan_error(401, "{}"))

    def test_rate_limit(self):
        self.assertIn("Terlalu banyak", ai._pesan_error(429, "{}"))

    def test_saldo_habis(self):
        self.assertIn("Saldo", ai._pesan_error(402, "{}"))

    def test_endpoint_salah(self):
        body = '{"error": {"code": "not_found", "message": "endpoint not found"}}'
        self.assertIn("Endpoint AI tidak ditemukan", ai._pesan_error(404, body))

    def test_server_error_5xx(self):
        self.assertIn("bermasalah", ai._pesan_error(503, "{}"))

    def test_body_rusak_tetap_memberi_pesan(self):
        self.assertIn("HTTP 418", ai._pesan_error(418, "bukan json"))


class DetailErrorTest(unittest.TestCase):
    def test_membaca_code_dan_message(self):
        body = '{"error": {"code": "x", "message": "y"}}'
        self.assertEqual(ai._detail_error(body), ("x", "y"))

    def test_body_rusak_menghasilkan_kosong(self):
        self.assertEqual(ai._detail_error("bukan json"), ("", ""))

    def test_error_bukan_dict(self):
        self.assertEqual(ai._detail_error('{"error": "teks"}'), ("", ""))


class PostTest(unittest.TestCase):
    def setUp(self):
        self.asli = (config.AI_ENABLED, config.AI_API_KEY)
        config.AI_ENABLED = True
        config.AI_API_KEY = "kunci-uji"

    def tearDown(self):
        config.AI_ENABLED, config.AI_API_KEY = self.asli

    def _respons(self, status=200, teks="{}"):
        return mock.Mock(status_code=status, text=teks)

    def test_sukses(self):
        with mock.patch.object(ai.requests, "post", return_value=self._respons(200, '{"a":1}')):
            self.assertEqual(ai._post({"x": 1}), {"a": 1})

    def test_status_bukan_200_jadi_ai_error(self):
        with mock.patch.object(ai.requests, "post", return_value=self._respons(401, "{}")):
            with self.assertRaises(ai.AIError) as ctx:
                ai._post({})
        self.assertIn("API key", str(ctx.exception))

    def test_timeout_diterjemahkan(self):
        with mock.patch.object(
            ai.requests, "post", side_effect=ai.requests.exceptions.Timeout
        ):
            with self.assertRaises(ai.AIError) as ctx:
                ai._post({})
        self.assertIn("120 detik", str(ctx.exception))

    def test_koneksi_gagal_diterjemahkan(self):
        with mock.patch.object(
            ai.requests, "post", side_effect=ai.requests.exceptions.ConnectionError
        ):
            with self.assertRaises(ai.AIError) as ctx:
                ai._post({})
        self.assertIn("Gagal terhubung", str(ctx.exception))

    def test_json_rusak_diterjemahkan(self):
        with mock.patch.object(ai.requests, "post", return_value=self._respons(200, "<html>")):
            with self.assertRaises(ai.AIError) as ctx:
                ai._post({})
        self.assertIn("bukan JSON", str(ctx.exception))


class RapikanToolCallsTest(unittest.TestCase):
    def test_id_duplikat_diganti_unik(self):
        calls = [
            {"id": "sama", "function": {"name": "web_search", "arguments": "{}"}},
            {"id": "sama", "function": {"name": "baca_halaman", "arguments": "{}"}},
        ]
        hasil = ai._rapikan_tool_calls(calls)
        self.assertEqual([c["id"] for c in hasil], ["call_0", "call_1"])

    def test_field_hilang_diisi_default(self):
        hasil = ai._rapikan_tool_calls([{}])
        self.assertEqual(hasil[0]["function"]["name"], "")
        self.assertEqual(hasil[0]["function"]["arguments"], "{}")


class DaftarToolTest(unittest.TestCase):
    def setUp(self):
        self.asli = (config.AI_ENABLED, config.AI_WEB_SEARCH)
        config.AI_ENABLED = True
        config.AI_WEB_SEARCH = True

    def tearDown(self):
        config.AI_ENABLED, config.AI_WEB_SEARCH = self.asli

    def test_pengguna_biasa_tanpa_tool_admin(self):
        nama = [t["function"]["name"] for t in ai.daftar_tool(admin=False)]
        self.assertIn("web_search", nama)
        self.assertIn("baca_halaman", nama)
        self.assertNotIn("status_bot", nama)

    def test_admin_dapat_status_bot(self):
        nama = [t["function"]["name"] for t in ai.daftar_tool(admin=True)]
        self.assertIn("status_bot", nama)

    def test_web_search_bisa_dimatikan(self):
        config.AI_WEB_SEARCH = False
        nama = [t["function"]["name"] for t in ai.daftar_tool(admin=False)]
        self.assertNotIn("web_search", nama)


class TanyaTest(unittest.TestCase):
    def setUp(self):
        self.asli = (config.AI_ENABLED, config.AI_API_KEY, config.AI_WEB_SEARCH)
        config.AI_ENABLED = True
        config.AI_API_KEY = "kunci-uji"
        config.AI_WEB_SEARCH = False
        ai._last_request.clear()

    def tearDown(self):
        config.AI_ENABLED, config.AI_API_KEY, config.AI_WEB_SEARCH = self.asli
        ai._last_request.clear()

    def _jawaban(self, teks="halo", tool_calls=None):
        message = {"content": teks}
        if tool_calls:
            message["tool_calls"] = tool_calls
        return {"choices": [{"message": message}], "usage": {"total_tokens": 10}}

    def test_jawaban_tanpa_tool(self):
        with mock.patch.object(ai, "_post", return_value=self._jawaban("jawaban")):
            hasil = ai.tanya(1, [{"role": "user", "content": "hai"}])
        self.assertEqual(hasil["teks"], "jawaban")
        self.assertEqual(hasil["total_tokens"], 10)
        self.assertEqual(hasil["sumber"], [])

    def test_ai_tidak_aktif_menolak(self):
        config.AI_ENABLED = False
        with self.assertRaises(ai.AIError) as ctx:
            ai.tanya(1, [])
        self.assertIn("belum aktif", str(ctx.exception))

    def test_choices_kosong_jadi_error(self):
        with mock.patch.object(ai, "_post", return_value={"choices": []}):
            with self.assertRaises(ai.AIError) as ctx:
                ai.tanya(1, [])
        self.assertIn("tidak mengembalikan jawaban", str(ctx.exception))

    def test_jawaban_kosong_jadi_error(self):
        with mock.patch.object(ai, "_post", return_value=self._jawaban("")):
            with self.assertRaises(ai.AIError) as ctx:
                ai.tanya(1, [])
        self.assertIn("kosong", str(ctx.exception))

    def test_tool_dijalankan_lalu_jawaban_final(self):
        panggilan = {"n": 0}

        def post(_payload):
            panggilan["n"] += 1
            if panggilan["n"] == 1:
                return self._jawaban(
                    "",
                    [
                        {
                            "id": "c1",
                            "function": {
                                "name": "web_search",
                                "arguments": '{"query": "cuaca"}',
                            },
                        }
                    ],
                )
            return self._jawaban("final")

        with mock.patch.object(ai, "_post", side_effect=post), \
             mock.patch.object(ai, "_jalankan_tool_calls", return_value=["🔎 cuaca"]):
            hasil = ai.tanya(1, [{"role": "user", "content": "cuaca?"}])

        self.assertEqual(hasil["teks"], "final")
        self.assertEqual(hasil["sumber"], ["🔎 cuaca"])
        self.assertEqual(panggilan["n"], 2)

    def test_tool_call_tanpa_jawaban_tidak_menghasilkan_none(self):
        """Kalau model hanya memanggil tool terus, jawaban tidak boleh None."""
        with mock.patch.object(
            ai,
            "_post",
            return_value=self._jawaban(
                "",
                [{"id": "c1", "function": {"name": "web_search", "arguments": "{}"}}],
            ),
        ), mock.patch.object(ai, "_jalankan_tool_calls", return_value=[]):
            hasil = ai.tanya(1, [{"role": "user", "content": "x"}])
        self.assertTrue(hasil["teks"])


class BatasiRateTest(unittest.TestCase):
    def setUp(self):
        ai._last_request.clear()

    def tearDown(self):
        ai._last_request.clear()

    def test_request_pertama_tidak_menunggu(self):
        with mock.patch.object(ai.time, "sleep") as tidur:
            ai._batasi_rate(1)
        tidur.assert_not_called()

    def test_request_beruntun_menunggu(self):
        with mock.patch.object(ai.time, "sleep") as tidur:
            ai._batasi_rate(1)
            ai._batasi_rate(1)
        tidur.assert_called_once()

    def test_chat_berbeda_tidak_saling_menunggu(self):
        with mock.patch.object(ai.time, "sleep") as tidur:
            ai._batasi_rate(1)
            ai._batasi_rate(2)
        tidur.assert_not_called()


if __name__ == "__main__":
    unittest.main()
