#!/usr/bin/env python3
"""Transcribe a local audio file with Atlas Cloud and emit SRT/text outputs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_API_BASE = "https://api.atlascloud.ai/api/v1"
DEFAULT_MODEL = "bytedance/seed-asr-2.0"
TERMINAL_SUCCESS = {"completed", "succeeded"}
TERMINAL_FAILURE = {"failed", "timeout", "canceled", "cancelled"}


@dataclass(frozen=True)
class Segment:
    start: float
    end: float
    text: str


@dataclass(frozen=True)
class OutputPaths:
    srt_path: Path
    text_path: Path


def env_or_default(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    cleaned = value.strip()
    return cleaned if cleaned else default


def load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Atlas Cloud speech-to-text and write subtitle files.",
    )
    parser.add_argument("audio_path", help="Path to the input audio file.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where subtitle.srt and text.txt are written.",
    )
    parser.add_argument(
        "--model",
        default=env_or_default("ATLASCLOUD_ASR_MODEL", DEFAULT_MODEL),
        help="Atlas Cloud ASR model ID.",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Optional language code. Defaults to automatic detection.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Initial prediction polling interval in seconds.",
    )
    parser.add_argument(
        "--max-polls",
        type=int,
        default=120,
        help="Maximum number of prediction status checks.",
    )
    return parser.parse_args(argv)


def normalize_text(text: object) -> str:
    return " ".join(str(text or "").split())


def ms_to_srt_timestamp(milliseconds: int) -> str:
    total_ms = max(0, int(milliseconds))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def seconds_to_srt_timestamp(seconds: float) -> str:
    return ms_to_srt_timestamp(round(seconds * 1000))


def unwrap_data(payload: dict[str, object]) -> dict[str, object]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def response_error(payload: dict[str, object]) -> str:
    data = unwrap_data(payload)
    return normalize_text(
        data.get("error")
        or payload.get("message")
        or data.get("message")
        or "Atlas Cloud request failed"
    )


def request_json(request: Request, timeout: float = 60.0) -> dict[str, object]:
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Atlas Cloud HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Atlas Cloud request failed: {exc.reason}") from exc

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Atlas Cloud returned an invalid JSON response") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("Atlas Cloud returned an unexpected response")
    code = payload.get("code")
    if isinstance(code, int) and code not in {0, 200}:
        raise RuntimeError(response_error(payload))
    return payload


def upload_media(
    audio_path: Path,
    api_key: str,
    api_base: str,
) -> str:
    boundary = f"----atlascloud-{uuid.uuid4().hex}"
    mime_type = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
    prefix = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{audio_path.name}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode("utf-8")
    suffix = f"\r\n--{boundary}--\r\n".encode("ascii")
    body = prefix + audio_path.read_bytes() + suffix
    request = Request(
        f"{api_base.rstrip('/')}/model/uploadMedia",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    data = unwrap_data(request_json(request))
    download_url = data.get("download_url")
    if not isinstance(download_url, str) or not download_url:
        raise RuntimeError("Atlas Cloud upload response is missing download_url")
    return download_url


def audio_format(audio_path: Path) -> str:
    suffix = audio_path.suffix.lower().lstrip(".")
    if suffix not in {"mp3", "wav", "ogg", "raw"}:
        raise ValueError("Atlas Cloud Seed ASR supports mp3, wav, ogg, or raw audio")
    return suffix


def submit_prediction(
    audio_url: str,
    audio_path: Path,
    api_key: str,
    api_base: str,
    model: str,
    language: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "model": model,
        "audio_url": audio_url,
        "format": audio_format(audio_path),
        "enable_itn": True,
        "enable_punc": True,
        "show_utterances": True,
    }
    if language:
        payload["language"] = language
    request = Request(
        f"{api_base.rstrip('/')}/model/generateAudio",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    data = unwrap_data(request_json(request))
    prediction_id = data.get("id")
    if not isinstance(prediction_id, str) or not prediction_id:
        raise RuntimeError("Atlas Cloud submission response is missing prediction id")
    return prediction_id


def poll_prediction(
    prediction_id: str,
    api_key: str,
    api_base: str,
    poll_interval: float,
    max_polls: int,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, object]:
    if poll_interval < 0:
        raise ValueError("poll_interval must be non-negative")
    if max_polls < 1:
        raise ValueError("max_polls must be at least 1")

    delay = poll_interval
    for attempt in range(max_polls):
        if attempt:
            sleep(delay)
            delay = min(max(delay * 1.5, poll_interval), 10.0)
        request = Request(
            f"{api_base.rstrip('/')}/model/prediction/{prediction_id}",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        payload = request_json(request, timeout=30.0)
        data = unwrap_data(payload)
        status = normalize_text(data.get("status")).lower()
        if status in TERMINAL_SUCCESS:
            return data
        if status in TERMINAL_FAILURE:
            raise RuntimeError(response_error(payload))

    raise TimeoutError(
        f"Atlas Cloud prediction did not finish after {max_polls} checks"
    )


def timed_segments(result: dict[str, object]) -> list[Segment]:
    words = result.get("words")
    if not isinstance(words, list):
        return []

    entries = [item for item in words if isinstance(item, dict)]
    utterances = [item for item in entries if item.get("type") == "utterance"]
    if utterances:
        return segments_from_entries(utterances)
    return group_word_entries(entries)


def segments_from_entries(entries: Iterable[dict[str, object]]) -> list[Segment]:
    segments: list[Segment] = []
    for item in entries:
        text = normalize_text(item.get("text"))
        start = item.get("start")
        end = item.get("end")
        if (
            not text
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
        ):
            continue
        segments.append(Segment(float(start), max(float(start), float(end)), text))
    return segments


def join_word_tokens(tokens: Sequence[str]) -> str:
    text = ""
    for token in tokens:
        cleaned = normalize_text(token)
        if not cleaned:
            continue
        needs_space = (
            text
            and text[-1].isascii()
            and text[-1].isalnum()
            and cleaned[0].isascii()
            and cleaned[0].isalnum()
        )
        text += (" " if needs_space else "") + cleaned
    return text


def group_word_entries(entries: Sequence[dict[str, object]]) -> list[Segment]:
    segments: list[Segment] = []
    current: list[dict[str, object]] = []
    sentence_endings = (".", "!", "?", "。", "！", "？")

    def flush() -> None:
        if not current:
            return
        start = current[0].get("start")
        end = current[-1].get("end")
        text = join_word_tokens([str(item.get("text") or "") for item in current])
        if text and isinstance(start, (int, float)) and isinstance(end, (int, float)):
            segments.append(Segment(float(start), max(float(start), float(end)), text))
        current.clear()

    for item in entries:
        start = item.get("start")
        end = item.get("end")
        text = normalize_text(item.get("text"))
        if (
            not text
            or not isinstance(start, (int, float))
            or not isinstance(end, (int, float))
        ):
            continue
        if current and item.get("speaker_id") != current[-1].get("speaker_id"):
            flush()
        current.append(item)
        segment_text = join_word_tokens(
            [str(part.get("text") or "") for part in current]
        )
        segment_start = current[0].get("start")
        duration = (
            float(end) - float(segment_start)
            if isinstance(segment_start, (int, float))
            else 0
        )
        if (
            duration >= 6.0
            or len(segment_text) >= 48
            or segment_text.endswith(sentence_endings)
        ):
            flush()
    flush()
    return segments


def extract_transcription(prediction: dict[str, object]) -> tuple[str, list[Segment]]:
    result = prediction.get("stt_result")
    stt_result = result if isinstance(result, dict) else {}
    text = normalize_text(stt_result.get("text"))
    if not text:
        outputs = prediction.get("outputs")
        if isinstance(outputs, list) and outputs:
            text = normalize_text(outputs[0])

    segments = timed_segments(stt_result)
    if not segments and text:
        duration = stt_result.get("duration")
        end = float(duration) if isinstance(duration, (int, float)) else 0.0
        segments = [Segment(0.0, max(0.0, end), text)]
    if not text:
        text = " ".join(segment.text for segment in segments)
    if not text:
        raise RuntimeError("Atlas Cloud prediction did not contain transcription text")
    return text, segments


def write_outputs(
    text: str,
    segments: Iterable[Segment],
    output_dir: Path,
) -> OutputPaths:
    output_dir.mkdir(parents=True, exist_ok=True)
    srt_path = output_dir / "subtitle.srt"
    text_path = output_dir / "text.txt"
    normalized_segments = [
        Segment(segment.start, segment.end, normalize_text(segment.text))
        for segment in segments
        if normalize_text(segment.text)
    ]
    srt_content = "".join(
        f"{index}\n{seconds_to_srt_timestamp(segment.start)} --> "
        f"{seconds_to_srt_timestamp(segment.end)}\n{segment.text}\n\n"
        for index, segment in enumerate(normalized_segments, 1)
    )
    normalized_text = normalize_text(text)
    text_content = f"{normalized_text}\n" if normalized_text else ""
    srt_path.write_text(srt_content, encoding="utf-8")
    text_path.write_text(text_content, encoding="utf-8")
    return OutputPaths(srt_path=srt_path, text_path=text_path)


def transcribe_audio(
    audio_path: Path,
    output_dir: Path,
    api_key: str,
    api_base: str,
    model: str,
    language: str | None,
    poll_interval: float,
    max_polls: int,
) -> dict[str, object]:
    audio_format(audio_path)
    audio_url = upload_media(audio_path, api_key, api_base)
    prediction_id = submit_prediction(
        audio_url,
        audio_path,
        api_key,
        api_base,
        model,
        language,
    )
    prediction = poll_prediction(
        prediction_id,
        api_key,
        api_base,
        poll_interval,
        max_polls,
    )
    text, segments = extract_transcription(prediction)
    output_paths = write_outputs(text, segments, output_dir)
    return {
        "model": model,
        "prediction_id": prediction_id,
        "segment_count": len(segments),
        "audio_path": str(audio_path),
        "output_dir": str(output_dir),
        "srt_path": str(output_paths.srt_path),
        "text_path": str(output_paths.text_path),
    }


def main(argv: Sequence[str] | None = None) -> int:
    load_env_file(Path(__file__).resolve().parents[1] / ".env")
    args = parse_args(argv)
    audio_path = Path(args.audio_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    api_key = env_or_default("ATLASCLOUD_API_KEY")
    api_base = (
        env_or_default("ATLASCLOUD_API_BASE", DEFAULT_API_BASE) or DEFAULT_API_BASE
    )

    if not audio_path.is_file():
        print(f"ERROR: Audio file not found: {audio_path}", file=sys.stderr)
        return 1
    if not api_key:
        print("ERROR: ATLASCLOUD_API_KEY is required", file=sys.stderr)
        return 1

    try:
        result = transcribe_audio(
            audio_path=audio_path,
            output_dir=output_dir,
            api_key=api_key,
            api_base=api_base,
            model=args.model,
            language=args.language,
            poll_interval=args.poll_interval,
            max_polls=args.max_polls,
        )
    except Exception as exc:  # pragma: no cover - CLI error handling
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
