#!/usr/bin/env python3
"""Fetch Douyin creator homepage video posts via AI Douyin API."""

from __future__ import annotations

import argparse
import json
import re
import sys
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
    read_config,
    request_json,
)


SEC_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{16,}$")


def build_user_posts_endpoint(api_base: str) -> str:
    return build_v1_endpoint(api_base, "/douyin/user-post-videos")


def build_request_payload(
    target: str,
    *,
    count: int = 10,
    sort_type: int = 0,
    max_cursor: int = 0,
) -> dict[str, Any]:
    cleaned = target.strip()
    clamped_count = max(1, min(int(count), 20))
    payload: dict[str, Any] = {
        "max_cursor": int(max_cursor),
        "count": clamped_count,
        "sort_type": int(sort_type),
    }
    if "://" not in cleaned and SEC_USER_ID_RE.match(cleaned):
        payload["sec_user_id"] = cleaned
    else:
        payload["url"] = cleaned
    return payload


def fetch_douyin_user_posts(
    endpoint: str,
    api_key: str,
    target: str,
    *,
    count: int = 10,
    sort_type: int = 0,
    max_cursor: int = 0,
    api_base: str = DEFAULT_API_BASE,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 30,
) -> dict[str, Any]:
    payload = build_request_payload(
        target,
        count=count,
        sort_type=sort_type,
        max_cursor=max_cursor,
    )
    return request_json(
        endpoint,
        api_key,
        method="POST",
        payload=payload,
        api_base=api_base,
        action="AI Douyin user posts request",
        opener=opener,
        timeout=timeout,
    )


def _format_duration(seconds_or_ms: Any) -> str:
    try:
        raw = int(seconds_or_ms or 0)
    except (TypeError, ValueError):
        return "-"
    if raw <= 0:
        return "-"
    # Douyin API duration is usually in milliseconds when > 1000, or seconds otherwise.
    seconds = raw // 1000 if raw >= 1000 else raw
    minutes, rem = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{rem:02d}"
    return f"{minutes}:{rem:02d}"


def _short_cell(value: Any, limit: int = 44) -> str:
    text = str(value or "").replace("\n", " ").replace("|", "/").strip()
    if len(text) <= limit:
        return text or "-"
    return text[: limit - 1] + "..."


def render_markdown(response: dict[str, Any]) -> str:
    videos = response.get("videos") or []
    sec_user_id = response.get("sec_user_id") or "-"
    sort_label = "最热" if response.get("sort_type") == 1 else "最新"
    has_more = bool(response.get("has_more"))
    max_cursor = response.get("max_cursor", 0)
    cost = response.get("cost", 0)

    lines = [
        (
            f"Douyin user posts: sec_user_id={sec_user_id}, "
            f"count={len(videos)}, sort={sort_label}, has_more={has_more}, "
            f"max_cursor={max_cursor}, cost={cost} 积分"
        ),
        "",
    ]
    if not videos:
        lines.append("No videos found.")
        return "\n".join(lines)

    lines.extend(
        [
            "| # | Author | Title | Duration | Likes | Comments | Share URL |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for index, video in enumerate(videos, 1):
        author = video.get("author") or {}
        stats = video.get("stats") or {}
        aweme_id = video.get("aweme_id") or ""
        share_url = video.get("share_url") or (
            f"https://www.douyin.com/video/{aweme_id}" if aweme_id else "-"
        )
        lines.append(
            "| {idx} | {author} | {title} | {duration} | {likes} | {comments} | {url} |".format(
                idx=index,
                author=_short_cell(author.get("nickname"), 20),
                title=_short_cell(video.get("desc"), 44),
                duration=_format_duration(video.get("duration")),
                likes=stats.get("digg_count", 0),
                comments=stats.get("comment_count", 0),
                url=share_url,
            )
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        help="Douyin user homepage URL, share text, or sec_user_id.",
    )
    parser.add_argument("--count", type=int, default=10, help="Videos per page (1-20).")
    parser.add_argument(
        "--sort-type",
        type=int,
        choices=[0, 1],
        default=0,
        help="0 = latest (default), 1 = hottest.",
    )
    parser.add_argument("--max-cursor", type=int, default=0)
    parser.add_argument("--api-base", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--env-file", type=Path, default=default_env_file())
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--json", action="store_true", help="Print raw JSON output.")
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
        response = fetch_douyin_user_posts(
            build_user_posts_endpoint(api_base),
            api_key,
            args.target,
            count=args.count,
            sort_type=args.sort_type,
            max_cursor=args.max_cursor,
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
