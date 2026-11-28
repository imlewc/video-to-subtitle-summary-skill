#!/usr/bin/env python3
"""Submit and poll cloud video analysis (summary, transcript, Douyin comment insights) via AI Douyin API."""

from __future__ import annotations

import argparse
import json
import sys
import time
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


def build_submit_endpoint(api_base: str) -> str:
    return build_v1_endpoint(api_base, "/analysis")


def build_result_endpoint(api_base: str, analysis_id: int | str) -> str:
    return build_v1_endpoint(api_base, f"/analysis/{analysis_id}")


def submit_analysis(
    api_base: str,
    api_key: str,
    url: str,
    *,
    force_reanalyze: bool = False,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 90,
) -> dict[str, Any]:
    endpoint = build_submit_endpoint(api_base)
    return request_json(
        endpoint,
        api_key,
        method="POST",
        payload={"url": url, "force_reanalyze": bool(force_reanalyze)},
        api_base=api_base,
        action="AI Douyin cloud analysis submit",
        opener=opener,
        timeout=timeout,
    )


def get_analysis(
    api_base: str,
    api_key: str,
    analysis_id: int | str,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 30,
) -> dict[str, Any]:
    endpoint = build_result_endpoint(api_base, analysis_id)
    return request_json(
        endpoint,
        api_key,
        method="GET",
        api_base=api_base,
        action="AI Douyin cloud analysis poll",
        opener=opener,
        timeout=timeout,
    )


def _extract_analysis_record(submit_response: dict[str, Any]) -> dict[str, Any]:
    nested = submit_response.get("analysis")
    if isinstance(nested, dict):
        return nested
    return submit_response


def wait_for_analysis(
    api_base: str,
    api_key: str,
    analysis_id: int | str,
    *,
    initial_analysis: dict[str, Any] | None = None,
    poll_interval: float = 5.0,
    max_wait: float = 600.0,
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 30,
    sleeper: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    current = initial_analysis or get_analysis(
        api_base,
        api_key,
        analysis_id,
        opener=opener,
        timeout=timeout,
    )
    deadline = clock() + max_wait

    while True:
        status = str(current.get("status") or "").lower()
        if status == "completed":
            return current
        if status == "failed":
            reason = current.get("error_message") or "analysis failed on server"
            raise RuntimeError(f"AI Douyin analysis {analysis_id} failed: {reason}")
        if clock() >= deadline:
            raise RuntimeError(
                f"AI Douyin analysis {analysis_id} timed out after {int(max_wait)}s "
                f"(last status={status or 'unknown'}, stage={current.get('progress_stage') or 'unknown'}). "
                "Do not re-submit immediately; inspect task history or poll this analysis ID later."
            )
        sleeper(poll_interval)
        current = get_analysis(
            api_base,
            api_key,
            analysis_id,
            opener=opener,
            timeout=timeout,
        )


def parse_keywords(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        try:
            decoded = json.loads(text)
            if isinstance(decoded, list):
                return [str(item).strip() for item in decoded if str(item).strip()]
        except Exception:
            pass
        return [part.strip() for part in text.split(",") if part.strip()]
    return []


def render_markdown(analysis: dict[str, Any], *, reused: bool = False) -> str:
    analysis_id = analysis.get("id", "-")
    task_id = analysis.get("task_id") or "-"
    title = analysis.get("title") or "-"
    author = analysis.get("author") or "-"
    status = analysis.get("status") or "-"
    url = analysis.get("url") or "-"
    keywords = parse_keywords(analysis.get("keywords"))
    summary = str(analysis.get("summary") or "").strip()
    transcript = str(analysis.get("transcription_text") or "").strip()

    lines = [
        "## 云端视频分析结果",
        "",
        "| 字段 | 内容 |",
        "| --- | --- |",
        f"| 分析 ID | {analysis_id} |",
        f"| 任务 ID | {task_id} |",
        f"| 状态 | {status}{'（复用已有结果）' if reused else ''} |",
        f"| 标题 | {title} |",
        f"| 作者 | {author} |",
        f"| 原链接 | {url} |",
    ]
    if keywords:
        lines.append(f"| 关键词 | {', '.join(keywords)} |")
    lines.append("")

    if summary:
        lines.extend(["### AI 总结与洞察", "", summary, ""])
    if transcript:
        lines.extend(["### 完整字幕 / 转录文本", "", transcript, ""])
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(
    analysis: dict[str, Any],
    output_dir: Path,
    *,
    reused: bool = False,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}

    summary_path = output_dir / "summary.md"
    summary_path.write_text(render_markdown(analysis, reused=reused), encoding="utf-8")
    written["summary_md"] = str(summary_path)

    transcript = str(analysis.get("transcription_text") or "").strip()
    if transcript:
        text_path = output_dir / "text.txt"
        text_path.write_text(transcript + "\n", encoding="utf-8")
        written["text_txt"] = str(text_path)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Video URL or share text (Douyin/Xiaohongshu/Bilibili/X).")
    parser.add_argument("--force-reanalyze", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--max-wait", type=float, default=600.0)
    parser.add_argument("--no-wait", action="store_true", help="Return right after submission.")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--api-base", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--env-file", type=Path, default=default_env_file())
    parser.add_argument("--timeout", type=int, default=90)
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
        submit_resp = submit_analysis(
            api_base,
            api_key,
            args.url,
            force_reanalyze=args.force_reanalyze,
            timeout=args.timeout,
        )
        initial = _extract_analysis_record(submit_resp)
        reused = bool(submit_resp.get("reused"))
        analysis_id = initial.get("id")
        if not analysis_id:
            raise RuntimeError("AI Douyin analysis response missing analysis id")

        if args.no_wait:
            final_analysis = initial
        else:
            final_analysis = wait_for_analysis(
                api_base,
                api_key,
                analysis_id,
                initial_analysis=initial,
                poll_interval=args.poll_interval,
                max_wait=args.max_wait,
                timeout=min(args.timeout, 30),
            )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    written = {}
    if args.output_dir is not None and str(final_analysis.get("status") or "").lower() == "completed":
        written = write_outputs(final_analysis, args.output_dir, reused=reused)

    if args.json:
        output_payload: dict[str, Any] = {
            "reused": reused,
            "analysis": final_analysis,
        }
        if written:
            output_payload["files"] = written
        print(json.dumps(output_payload, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(final_analysis, reused=reused))
        if written:
            print("Saved files:")
            for label, path in written.items():
                print(f"- {label}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
