import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "list_ai_douyin_tasks.py"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "list_ai_douyin_tasks",
        MODULE_PATH,
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self.body


class ListAIDouyinTasksTests(unittest.TestCase):
    def test_build_tasks_endpoint_accepts_root_api_and_api_v1_bases(self):
        module = load_module()

        self.assertEqual(
            module.build_tasks_endpoint("https://top9.cc"),
            "https://top9.cc/api/v1/tasks",
        )
        self.assertEqual(
            module.build_tasks_endpoint("https://top9.cc/api"),
            "https://top9.cc/api/v1/tasks",
        )
        self.assertEqual(
            module.build_tasks_endpoint("https://top9.cc/api/v1"),
            "https://top9.cc/api/v1/tasks",
        )

    def test_fetch_tasks_sends_api_key_and_query_parameters(self):
        module = load_module()
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return FakeResponse(
                b'{"tasks":[],"total":0,"page":2,"pageSize":5,"totalPages":0}'
            )

        response = module.fetch_tasks(
            "https://top9.cc/api/v1/tasks",
            "sk-test",
            page=2,
            page_size=5,
            status="completed",
            search="demo",
            opener=opener,
            timeout=9,
        )

        request, timeout = requests[0]
        self.assertEqual(timeout, 9)
        self.assertEqual(request.headers["X-api-key"], "sk-test")
        self.assertIn("page=2", request.full_url)
        self.assertIn("pageSize=5", request.full_url)
        self.assertIn("status=completed", request.full_url)
        self.assertIn("search=demo", request.full_url)
        self.assertEqual(response["page"], 2)

    def test_render_markdown_includes_task_summary_without_raw_json_noise(self):
        module = load_module()
        rendered = module.render_markdown(
            {
                "tasks": [
                    {
                        "createdAt": "2026-05-26T12:00:00Z",
                        "status": "completed",
                        "taskId": "task_123",
                        "title": "测试标题",
                        "url": "https://v.douyin.com/demo/",
                    }
                ],
                "total": 1,
                "page": 1,
                "pageSize": 20,
                "totalPages": 1,
            }
        )

        self.assertIn("AI Douyin task history: total=1", rendered)
        self.assertIn("| 2026-05-26T12:00:00Z | completed | task_123 | 测试标题 |", rendered)


if __name__ == "__main__":
    unittest.main()
