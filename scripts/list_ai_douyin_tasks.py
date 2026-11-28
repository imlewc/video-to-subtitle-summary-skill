#!/usr/bin/env python3
"""List the authenticated AI Douyin user's historical tasks."""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ai_douyin_client import (  # noqa: E402
    DEFAULT_API_BASE,
    build_api_keys_url,
    build_v1_endpoint,
    default_env_file,
    format_http_error,
    load_env_file,
    read_config,
)


def build_tasks_endpoint(api_base: str) -> str:
    return build_v1_endpoint(api_base, "/tasks")


def fetch_tasks(
    endpoint: str,
    api_key: str,
    *,
    page: int,
    page_size: int,
    status: str = "",
    search: str = "",
    api_base: str = DEFAULT_API_BASE,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 30,
) -> dict[str, Any]:
    query: dict[str, str] = {
        "page": str(page),
        "pageSize": str(page_size),
    }
    if status:
        query["status"] = status
    if search:
        query["search"] = search

    url = endpoint + "?" + urllib.parse.urlencode(query)
    request = urllib.request.Request(url, headers={"X-API-Key": api_key})

    try:
        with opener(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            format_http_error(
                exc.code,
                body,
                api_base=api_base,
                action="AI Douyin tasks request",
            )
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"AI Douyin tasks request failed: {exc}") from exc

    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError("AI Douyin tasks response is not a JSON object")
    return parsed


def short_text(value: Any, limit: int = 48) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "..."


def render_markdown(response: dict[str, Any]) -> str:
    tasks = response.get("tasks") or []
    total = response.get("total", 0)
    page = response.get("page", 1)
    page_size = response.get("pageSize", len(tasks))
    total_pages = response.get("totalPages", 1)

    lines = [
        f"AI Douyin task history: total={total}, page={page}/{total_pages}, pageSize={page_size}",
        "",
    ]
    if not tasks:
        lines.append("No tasks found.")
        return "\n".join(lines)

    lines.extend(
        [
            "| Created At | Status | Task ID | Title | URL |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for task in tasks:
        lines.append(
            "| {created} | {status} | {task_id} | {title} | {url} |".format(
                created=short_text(task.get("createdAt"), 24),
                status=short_text(task.get("status"), 16),
                task_id=short_text(task.get("taskId"), 24),
                title=short_text(task.get("title"), 40),
                url=short_text(task.get("url"), 48),
            )
        )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--env-file", type=Path, default=default_env_file())
    parser.add_argument("--page", type=int, default=1)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--status", choices=["", "pending", "processing", "completed", "failed"], default="")
    parser.add_argument("--search", default="")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a markdown table.")
    args = parser.parse_args()

    api_base = args.api_base or read_config("AI_DOUYIN_API_BASE", args.env_file) or DEFAULT_API_BASE
    api_key = args.api_key or read_config("AI_DOUYIN_API_KEY", args.env_file)
    if not api_key:
        print(
            f"ERROR: missing AI_DOUYIN_API_KEY. 请前往获取：{build_api_keys_url(api_base)}",
            file=sys.stderr,
        )
        return 1

    try:
        response = fetch_tasks(
            build_tasks_endpoint(api_base),
            api_key,
            page=args.page,
            page_size=args.page_size,
            status=args.status,
            search=args.search,
            api_base=api_base,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(response, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(response))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
