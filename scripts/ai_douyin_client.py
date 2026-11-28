#!/usr/bin/env python3
"""Shared HTTP, configuration, and UTM error helpers for AI Douyin scripts."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


DEFAULT_API_BASE = "https://top9.cc"
UTM_CAMPAIGN = "video-to-subtitle-summary"


def default_env_file() -> Path:
    return Path(__file__).resolve().parents[1] / ".env"


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_config(key: str, env_file: Path | None = None) -> str:
    if env_file is not None:
        env_values = load_env_file(env_file)
        if env_values.get(key):
            return env_values[key]
    return os.environ.get(key, "")


def normalize_web_base(api_base: str) -> str:
    trimmed = (api_base or DEFAULT_API_BASE).strip().rstrip("/")
    for suffix in ("/api/v1", "/api"):
        if trimmed.endswith(suffix):
            trimmed = trimmed[: -len(suffix)]
            break
    return trimmed or DEFAULT_API_BASE


def build_v1_endpoint(api_base: str, resource_path: str) -> str:
    path = "/" + resource_path.lstrip("/")
    trimmed = (api_base or DEFAULT_API_BASE).strip().rstrip("/")
    if trimmed.endswith("/api/v1"):
        return trimmed + path
    if trimmed.endswith("/api"):
        return trimmed + "/v1" + path
    return trimmed + "/api/v1" + path


def build_utm_url(
    api_base: str,
    path: str = "/",
    *,
    source: str = "skill",
    medium: str = "cli",
    campaign: str = UTM_CAMPAIGN,
) -> str:
    web_base = normalize_web_base(api_base)
    clean_path = "/" + path.lstrip("/") if path and path != "/" else "/"
    query = urllib.parse.urlencode(
        {
            "utm_source": source,
            "utm_medium": medium,
            "utm_campaign": campaign,
        }
    )
    return f"{web_base}{clean_path}?{query}"


def build_recharge_url(
    api_base: str = DEFAULT_API_BASE,
    *,
    source: str = "skill",
    medium: str = "402_prompt",
) -> str:
    return build_utm_url(api_base, "/recharge", source=source, medium=medium)


def build_api_keys_url(
    api_base: str = DEFAULT_API_BASE,
    *,
    source: str = "skill",
    medium: str = "401_prompt",
) -> str:
    return build_utm_url(api_base, "/api-keys", source=source, medium=medium)


def _parse_error_json(body: str) -> dict[str, Any]:
    try:
        parsed = json.loads(body)
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def format_http_error(
    code: int,
    body: str,
    *,
    api_base: str = DEFAULT_API_BASE,
    action: str = "AI Douyin request",
) -> str:
    if code == 402:
        data = _parse_error_json(body)
        available = data.get("available_points")
        required = data.get("required_points", data.get("cost"))
        balance_detail = ""
        if available is not None and required is not None:
            balance_detail = f"（当前可用 {available} 积分，本次需要 {required} 积分）"
        elif required is not None:
            balance_detail = f"（本次需要 {required} 积分）"

        recharge_url = build_recharge_url(api_base, source="skill", medium="402_prompt")
        return (
            f"{action} failed: HTTP 402 insufficient balance — AI Douyin 积分不足{balance_detail}。\n"
            "计费参考：1 元 = 100 积分；直链解析 10 积分/次，抖音主页作品 5 积分/次，云端分析 10 积分/分钟，满 20/50/100 元再送 5%/7%/10%。\n"
            f"请前往充值：{recharge_url}"
        )

    if code == 401:
        api_keys_url = build_api_keys_url(api_base, source="skill", medium="401_prompt")
        return (
            f"{action} failed: HTTP 401 unauthorized — AI_DOUYIN_API_KEY 缺失、无效或已过期。\n"
            f"请前往获取或检查 API Key：{api_keys_url}"
        )

    return f"{action} failed: HTTP {code} {body}"


def request_json(
    url: str,
    api_key: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    api_base: str = DEFAULT_API_BASE,
    action: str = "AI Douyin request",
    opener: Callable[..., Any] = urllib.request.urlopen,
    timeout: int = 30,
) -> dict[str, Any]:
    headers = {"X-API-Key": api_key}
    data: bytes | None = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with opener(request, timeout=timeout) as response:
            raw_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            format_http_error(exc.code, body, api_base=api_base, action=action)
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"{action} failed: {exc}") from exc

    parsed = json.loads(raw_body)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"{action} response is not a JSON object")
    return parsed
