import importlib.util
import io
import json
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "analyze_video_cloud.py"


def load_module():
    spec = importlib.util.spec_from_file_location("analyze_video_cloud", MODULE_PATH)
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


class AnalyzeVideoCloudTests(unittest.TestCase):
    def test_submit_and_wait_for_analysis_polls_until_completed(self):
        module = load_module()
        calls = []
        sleeps = []
        now = [0.0]

        def clock():
            return now[0]

        def sleeper(seconds):
            sleeps.append(seconds)
            now[0] += seconds

        responses = [
            {
                "message": "Analysis started",
                "reused": False,
                "analysis": {"id": 42, "status": "pending", "progress_stage": "queued"},
            },
            {"id": 42, "status": "processing", "progress_stage": "transcribing"},
            {
                "id": 42,
                "task_id": "task_42",
                "status": "completed",
                "title": "测试爆款视频",
                "author": "拆解君",
                "url": "https://v.douyin.com/demo/",
                "keywords": '["钩子","口播"]',
                "summary": "### 摘要\n核心观点。\n\n### 抖音评论洞察\n评论区最关心价格。",
                "transcription_text": "大家好，今天聊聊...",
            },
        ]

        def opener(request, timeout):
            calls.append((request.get_method(), request.full_url, timeout))
            payload = responses.pop(0)
            return FakeResponse(json.dumps(payload).encode("utf-8"))

        submit_resp = module.submit_analysis(
            "https://top9.cc",
            "sk-cloud",
            "https://v.douyin.com/demo/",
            opener=opener,
            timeout=90,
        )
        final = module.wait_for_analysis(
            "https://top9.cc",
            "sk-cloud",
            submit_resp["analysis"]["id"],
            initial_analysis=submit_resp["analysis"],
            poll_interval=2.0,
            max_wait=30.0,
            opener=opener,
            sleeper=sleeper,
            clock=clock,
        )

        self.assertEqual(calls[0][0], "POST")
        self.assertEqual(calls[0][1], "https://top9.cc/api/v1/analysis")
        self.assertEqual(calls[1][0], "GET")
        self.assertEqual(calls[1][1], "https://top9.cc/api/v1/analysis/42")
        self.assertEqual(sleeps, [2.0, 2.0])
        self.assertEqual(final["status"], "completed")

        md = module.render_markdown(final, reused=False)
        self.assertIn("测试爆款视频", md)
        self.assertIn("钩子, 口播", md)
        self.assertIn("抖音评论洞察", md)
        self.assertIn("大家好，今天聊聊...", md)

        with tempfile.TemporaryDirectory() as tmpdir:
            written = module.write_outputs(final, Path(tmpdir))
            self.assertTrue(Path(written["summary_md"]).exists())
            self.assertEqual(
                Path(written["text_txt"]).read_text(encoding="utf-8"),
                "大家好，今天聊聊...\n",
            )

    def test_wait_for_analysis_returns_immediately_when_reused_completed(self):
        module = load_module()
        sleeps = []

        def fail_opener(request, timeout):
            raise AssertionError("should not poll when already completed")

        final = module.wait_for_analysis(
            "https://top9.cc",
            "sk-cloud",
            99,
            initial_analysis={"id": 99, "status": "completed", "summary": "done"},
            opener=fail_opener,
            sleeper=sleeps.append,
        )
        self.assertEqual(final["id"], 99)
        self.assertEqual(sleeps, [])

    def test_wait_for_analysis_raises_on_failed_and_timeout(self):
        module = load_module()

        with self.assertRaises(RuntimeError) as failed_ctx:
            module.wait_for_analysis(
                "https://top9.cc",
                "sk-cloud",
                12,
                initial_analysis={
                    "id": 12,
                    "status": "failed",
                    "error_message": "video unavailable",
                },
            )
        self.assertIn("video unavailable", str(failed_ctx.exception))

        now = [0.0]

        def opener(request, timeout):
            return FakeResponse(
                b'{"id": 13, "status": "processing", "progress_stage": "transcribing"}'
            )

        with self.assertRaises(RuntimeError) as timeout_ctx:
            module.wait_for_analysis(
                "https://top9.cc",
                "sk-cloud",
                13,
                initial_analysis={"id": 13, "status": "pending", "progress_stage": "queued"},
                poll_interval=5.0,
                max_wait=5.0,
                opener=opener,
                sleeper=lambda s: now.__setitem__(0, now[0] + s),
                clock=lambda: now[0],
            )
        self.assertIn("13", str(timeout_ctx.exception))
        self.assertIn("Do not re-submit immediately", str(timeout_ctx.exception))

    def test_submit_analysis_formats_402_with_utm_recharge_url(self):
        module = load_module()

        def opener(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                402,
                "Payment Required",
                {},
                io.BytesIO(
                    b'{"code":"insufficient_balance","available_points":20,"required_points":100}'
                ),
            )

        with self.assertRaises(RuntimeError) as ctx:
            module.submit_analysis(
                "https://top9.cc",
                "sk-cloud",
                "https://v.douyin.com/demo/",
                opener=opener,
            )

        msg = str(ctx.exception)
        self.assertIn("可用 20 积分", msg)
        self.assertIn("需要 100 积分", msg)
        self.assertIn("https://top9.cc/recharge?", msg)
        self.assertIn("utm_medium=402_prompt", msg)


if __name__ == "__main__":
    unittest.main()
