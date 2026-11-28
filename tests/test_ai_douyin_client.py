import importlib.util
import io
import sys
import unittest
import urllib.error
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "ai_douyin_client.py"


def load_module():
    spec = importlib.util.spec_from_file_location("ai_douyin_client", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class AIDouyinClientTests(unittest.TestCase):
    def test_normalize_web_base_and_v1_endpoints(self):
        module = load_module()

        self.assertEqual(module.normalize_web_base("https://top9.cc"), "https://top9.cc")
        self.assertEqual(module.normalize_web_base("https://top9.cc/api/"), "https://top9.cc")
        self.assertEqual(module.normalize_web_base("https://top9.cc/api/v1"), "https://top9.cc")

        self.assertEqual(
            module.build_v1_endpoint("https://top9.cc", "/analysis"),
            "https://top9.cc/api/v1/analysis",
        )
        self.assertEqual(
            module.build_v1_endpoint("https://top9.cc/api", "douyin/user-post-videos"),
            "https://top9.cc/api/v1/douyin/user-post-videos",
        )
        self.assertEqual(
            module.build_v1_endpoint("https://top9.cc/api/v1", "/tasks"),
            "https://top9.cc/api/v1/tasks",
        )

    def test_build_recharge_url_contains_utm_params(self):
        module = load_module()
        url = module.build_recharge_url("https://top9.cc/api/v1")

        self.assertTrue(url.startswith("https://top9.cc/recharge?"))
        self.assertIn("utm_source=skill", url)
        self.assertIn("utm_medium=402_prompt", url)
        self.assertIn("utm_campaign=video-to-subtitle-summary", url)

    def test_format_http_error_402_includes_balance_pricing_and_utm_link(self):
        module = load_module()
        msg = module.format_http_error(
            402,
            '{"error":"insufficient balance","available_points":5,"required_points":10}',
            api_base="https://top9.cc/api/v1",
            action="Cloud analysis",
        )

        self.assertIn("HTTP 402", msg)
        self.assertIn("可用 5 积分", msg)
        self.assertIn("需要 10 积分", msg)
        self.assertIn("https://top9.cc/recharge?", msg)
        self.assertIn("utm_medium=402_prompt", msg)
        self.assertNotIn("tikhub", msg.lower())

    def test_format_http_error_402_works_with_non_json_body(self):
        module = load_module()
        msg = module.format_http_error(402, "insufficient balance")

        self.assertIn("HTTP 402", msg)
        self.assertIn("https://top9.cc/recharge?", msg)

    def test_format_http_error_401_and_redacts_api_key_in_request_json(self):
        module = load_module()
        secret_key = "sk_secret_do_not_leak"

        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                io.BytesIO(b'{"error":"invalid api key"}'),
            )

        with self.assertRaises(RuntimeError) as ctx:
            module.request_json(
                "https://top9.cc/api/v1/tasks",
                secret_key,
                opener=opener,
            )

        error_text = str(ctx.exception)
        self.assertIn("HTTP 401", error_text)
        self.assertIn("https://top9.cc/api-keys?", error_text)
        self.assertNotIn(secret_key, error_text)

    def test_format_http_error_500_passes_body(self):
        module = load_module()
        msg = module.format_http_error(500, '{"error":"upstream failed"}', action="Test")
        self.assertEqual(msg, 'Test failed: HTTP 500 {"error":"upstream failed"}')


if __name__ == "__main__":
    unittest.main()
