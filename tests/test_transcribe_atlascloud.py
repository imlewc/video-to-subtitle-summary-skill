import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "transcribe_atlascloud.py"


def load_module():
    spec = importlib.util.spec_from_file_location("transcribe_atlascloud", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class RequestTests(unittest.TestCase):
    def test_load_env_file_preserves_existing_environment(self):
        module = load_module()

        with TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "ATLASCLOUD_API_KEY=file-key\nATLASCLOUD_ASR_MODEL='custom/model'\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"ATLASCLOUD_API_KEY": "shell-key"}, clear=False):
                module.load_env_file(env_path)
                self.assertEqual(os.environ["ATLASCLOUD_API_KEY"], "shell-key")
                self.assertEqual(os.environ["ATLASCLOUD_ASR_MODEL"], "custom/model")

    def test_upload_and_submission_follow_live_seed_asr_schema(self):
        module = load_module()
        responses = [
            FakeResponse(
                {
                    "code": 200,
                    "data": {"download_url": "https://media/audio.mp3"},
                }
            ),
            FakeResponse({"code": 200, "data": {"id": "pred-1"}}),
        ]

        with TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "audio.mp3"
            audio_path.write_bytes(b"audio")
            with patch.object(module, "urlopen", side_effect=responses) as mocked:
                audio_url = module.upload_media(
                    audio_path,
                    "test-key",
                    "https://api.atlascloud.ai/api/v1",
                )
                prediction_id = module.submit_prediction(
                    audio_url,
                    audio_path,
                    "test-key",
                    "https://api.atlascloud.ai/api/v1",
                    "bytedance/seed-asr-2.0",
                    "zh-CN",
                )

        self.assertEqual(prediction_id, "pred-1")
        self.assertEqual(mocked.call_count, 2)
        upload_request = mocked.call_args_list[0].args[0]
        self.assertEqual(upload_request.method, "POST")
        self.assertTrue(upload_request.full_url.endswith("/model/uploadMedia"))
        submit_request = mocked.call_args_list[1].args[0]
        payload = json.loads(submit_request.data.decode("utf-8"))
        self.assertEqual(
            payload,
            {
                "model": "bytedance/seed-asr-2.0",
                "audio_url": "https://media/audio.mp3",
                "format": "mp3",
                "enable_itn": True,
                "enable_punc": True,
                "show_utterances": True,
                "language": "zh-CN",
            },
        )

    def test_poll_prediction_uses_bounded_backoff(self):
        module = load_module()
        responses = [
            FakeResponse({"data": {"status": "created"}}),
            FakeResponse({"data": {"status": "processing"}}),
            FakeResponse({"data": {"status": "completed", "outputs": ["done"]}}),
        ]
        delays = []

        with patch.object(module, "urlopen", side_effect=responses) as mocked:
            result = module.poll_prediction(
                "pred-1",
                "test-key",
                "https://api.atlascloud.ai/api/v1",
                poll_interval=2.0,
                max_polls=3,
                sleep=delays.append,
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(mocked.call_count, 3)
        self.assertEqual(delays, [2.0, 3.0])

    def test_poll_prediction_does_not_retry_failed_task(self):
        module = load_module()
        response = FakeResponse(
            {"data": {"status": "failed", "error": "invalid audio"}}
        )

        with patch.object(module, "urlopen", return_value=response) as mocked:
            with self.assertRaisesRegex(RuntimeError, "invalid audio"):
                module.poll_prediction(
                    "pred-1",
                    "test-key",
                    "https://api.atlascloud.ai/api/v1",
                    poll_interval=0,
                    max_polls=3,
                )

        self.assertEqual(mocked.call_count, 1)


class OutputTests(unittest.TestCase):
    def test_extract_transcription_prefers_utterance_segments(self):
        module = load_module()
        prediction = {
            "outputs": ["第一句。 第二句。"],
            "stt_result": {
                "text": "第一句。 第二句。",
                "words": [
                    {"type": "word", "text": "第一句", "start": 0.0, "end": 1.0},
                    {"type": "utterance", "text": "第一句。", "start": 0.0, "end": 1.2},
                    {"type": "utterance", "text": "第二句。", "start": 1.2, "end": 2.5},
                ],
            },
        }

        text, segments = module.extract_transcription(prediction)

        self.assertEqual(text, "第一句。 第二句。")
        self.assertEqual(
            segments,
            [
                module.Segment(0.0, 1.2, "第一句。"),
                module.Segment(1.2, 2.5, "第二句。"),
            ],
        )

    def test_word_entries_are_grouped_into_readable_cues(self):
        module = load_module()
        prediction = {
            "stt_result": {
                "text": "Hello world. 下一句。",
                "words": [
                    {"type": "word", "text": "Hello", "start": 0.0, "end": 0.4},
                    {"type": "word", "text": "world", "start": 0.4, "end": 0.8},
                    {"type": "word", "text": ".", "start": 0.8, "end": 0.9},
                    {"type": "word", "text": "下", "start": 0.9, "end": 1.0},
                    {"type": "word", "text": "一句", "start": 1.0, "end": 1.3},
                    {"type": "word", "text": "。", "start": 1.3, "end": 1.4},
                ],
            }
        }

        _, segments = module.extract_transcription(prediction)

        self.assertEqual(
            segments,
            [
                module.Segment(0.0, 0.9, "Hello world."),
                module.Segment(0.9, 1.4, "下一句。"),
            ],
        )

    def test_write_outputs_creates_srt_and_text(self):
        module = load_module()
        segments = [
            module.Segment(0.0, 1.25, "第一句。"),
            module.Segment(1.25, 3.0, "第二句。"),
        ]

        with TemporaryDirectory() as tmpdir:
            output = module.write_outputs("第一句。 第二句。", segments, Path(tmpdir))

            self.assertEqual(
                output.srt_path.read_text(encoding="utf-8"),
                "1\n00:00:00,000 --> 00:00:01,250\n第一句。\n\n"
                "2\n00:00:01,250 --> 00:00:03,000\n第二句。\n\n",
            )
            self.assertEqual(
                output.text_path.read_text(encoding="utf-8"),
                "第一句。 第二句。\n",
            )

    def test_transcript_without_timestamps_uses_duration(self):
        module = load_module()

        text, segments = module.extract_transcription(
            {"stt_result": {"text": "Only text", "duration": 2.5}}
        )

        self.assertEqual(text, "Only text")
        self.assertEqual(segments, [module.Segment(0.0, 2.5, "Only text")])


if __name__ == "__main__":
    unittest.main()
