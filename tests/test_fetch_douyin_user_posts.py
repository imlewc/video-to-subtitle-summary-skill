import importlib.util
import io
import json
import sys
import unittest
import urllib.error
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "fetch_douyin_user_posts.py"


def load_module():
    spec = importlib.util.spec_from_file_location("fetch_douyin_user_posts", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.body


class FetchDouyinUserPostsTests(unittest.TestCase):
    def test_build_request_payload_detects_url_vs_sec_user_id_and_clamps_count(self):
        module = load_module()

        url_payload = module.build_request_payload(
            "https://www.douyin.com/user/MS4wLjABAAAAdemo123456",
            count=50,
            sort_type=1,
            max_cursor=100,
        )
        self.assertEqual(
            url_payload,
            {
                "url": "https://www.douyin.com/user/MS4wLjABAAAAdemo123456",
                "max_cursor": 100,
                "count": 20,
                "sort_type": 1,
            },
        )

        sec_payload = module.build_request_payload(
            "MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE",
            count=0,
            sort_type=0,
            max_cursor=0,
        )
        self.assertEqual(
            sec_payload,
            {
                "sec_user_id": "MS4wLjABAAAANXSltcLCzDGmdNFI2Q_QixVTr67NiYzjKOIP5s03CAE",
                "max_cursor": 0,
                "count": 1,
                "sort_type": 0,
            },
        )

    def test_fetch_douyin_user_posts_sends_header_and_json_body(self):
        module = load_module()
        captured = []

        def opener(request, timeout):
            captured.append((request, timeout))
            return FakeResponse(
                json.dumps(
                    {
                        "sec_user_id": "MS4w_test",
                        "max_cursor": 1700000000,
                        "has_more": True,
                        "count": 1,
                        "sort_type": 1,
                        "cost": 5,
                        "videos": [
                            {
                                "aweme_id": "7456789",
                                "desc": "爆款开头拆解",
                                "duration": 65000,
                                "share_url": "https://www.douyin.com/video/7456789",
                                "author": {"nickname": "测试博主"},
                                "stats": {"digg_count": 1200, "comment_count": 88},
                            }
                        ],
                    }
                ).encode("utf-8")
            )

        res = module.fetch_douyin_user_posts(
            module.build_user_posts_endpoint("https://top9.cc"),
            "sk-test-posts",
            "https://v.douyin.com/userdemo/",
            count=10,
            sort_type=1,
            opener=opener,
            timeout=15,
        )

        request, timeout = captured[0]
        self.assertEqual(timeout, 15)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.headers["X-api-key"], "sk-test-posts")
        self.assertEqual(request.headers["Content-type"], "application/json")
        self.assertEqual(res["cost"], 5)

        rendered = module.render_markdown(res)
        self.assertIn("sec_user_id=MS4w_test", rendered)
        self.assertIn("cost=5 积分", rendered)
        self.assertIn("测试博主", rendered)
        self.assertIn("爆款开头拆解", rendered)
        self.assertIn("1:05", rendered)
        self.assertIn("https://www.douyin.com/video/7456789", rendered)

    def test_fetch_douyin_user_posts_formats_402_with_utm_recharge_url(self):
        module = load_module()

        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                402,
                "Payment Required",
                {},
                io.BytesIO(b'{"error":"insufficient balance","cost":5}'),
            )

        with self.assertRaises(RuntimeError) as ctx:
            module.fetch_douyin_user_posts(
                "https://top9.cc/api/v1/douyin/user-post-videos",
                "sk-test",
                "https://v.douyin.com/userdemo/",
                opener=opener,
            )

        self.assertIn("https://top9.cc/recharge?", str(ctx.exception))
        self.assertIn("utm_source=skill", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
