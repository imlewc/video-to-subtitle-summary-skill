# video-to-subtitle-summary

A **Codex / Claude Code Skill** powered by **[AI Douyin (top9.cc)](https://top9.cc/?utm_source=github&utm_medium=readme_en&utm_campaign=video-to-subtitle-summary)** that turns Douyin, Xiaohongshu, Bilibili, X/Twitter, YouTube videos, and local media files into transcripts, SRT subtitles, AI summaries, **Douyin comment insights**, and **Douyin creator batch breakdowns**.

[中文文档](./README.md)

## No-Setup Online Version

Prefer a browser or WeChat mini program without local setup?
- **Web App**: Open [https://top9.cc](https://top9.cc/?utm_source=github&utm_medium=readme_en_online&utm_campaign=video-to-subtitle-summary) — new accounts get **100 free credits**.
- **WeChat Mini Program**: Search **「琢片」** in WeChat.

## Core Capabilities

| Capability | Use Case | Requirements | Pricing (1 CNY = 100 credits) |
| --- | --- | --- | --- |
| **Cloud Analysis (Zero Local Deps)** | Douyin/Xiaohongshu/Bilibili/X summaries, full transcript, **Douyin comment insights** | Python 3 + `AI_DOUYIN_API_KEY` (no FFmpeg/Whisper needed) | **10 credits/min** (min 10 credits; Douyin comment insights +10 credits) |
| **Douyin Creator Batch Posts** | Fetch a creator's latest/hottest posts with likes & comment stats for batch breakdown | Python 3 + `AI_DOUYIN_API_KEY` | **5 credits/request** |
| **Download URL + Local SRT** | Export editable `.srt` subtitles or transcribe local `.mp4`/`.mp3` | Python 3 + FFmpeg + `faster-whisper` | **10 credits/success** for online URL parsing; local files incur no API fee |
| **YouTube Subtitle Fetch** | Fetch manual/auto YouTube captions directly | `yt-dlp` | No API fee |

> New users registering on [AI Douyin (top9.cc)](https://top9.cc/?utm_source=github&utm_medium=readme_en&utm_campaign=video-to-subtitle-summary) receive **100 credits**; top-ups of 20/50/100 CNY include 5%/7%/10% bonus credits.

## Quick Start

### 1. Get an AI Douyin API Key (Required for Douyin / Xiaohongshu / Bilibili / X)

1. Register at [https://top9.cc](https://top9.cc/?utm_source=github&utm_medium=readme_en_setup&utm_campaign=video-to-subtitle-summary) and verify your email.
2. Create an API key on the [API Keys page](https://top9.cc/api-keys?utm_source=github&utm_medium=readme_en_setup&utm_campaign=video-to-subtitle-summary).
3. Install the Skill and configure `.env`:

```bash
git clone https://github.com/imlewc/video-to-subtitle-summary-skill.git video-to-subtitle-summary

# Codex
mkdir -p ~/.codex/skills && cp -r video-to-subtitle-summary ~/.codex/skills/video-to-subtitle-summary

# Claude Code
mkdir -p ~/.claude/skills && cp -r video-to-subtitle-summary ~/.claude/skills/video-to-subtitle-summary

cp ~/.codex/skills/video-to-subtitle-summary/.env.example ~/.codex/skills/video-to-subtitle-summary/.env
# Set AI_DOUYIN_API_KEY="sk_xxx" in .env
```

### 2. Optional Local Runtime (Only for local `.srt` generation or local files)

- **FFmpeg**: `brew install ffmpeg` (macOS) / `sudo apt install ffmpeg` (Ubuntu)
- **yt-dlp** (Bilibili fallback / YouTube subtitles): `brew install yt-dlp` or `python3 -m pip install -U yt-dlp`
- **faster-whisper**:

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/install_faster_whisper.py
```

## Usage Examples

### 1. Cloud Analysis (Zero Local Dependencies + Douyin Comment Insights)

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/analyze_video_cloud.py \
  "https://v.douyin.com/xxxxxx/" \
  --output-dir /tmp/video_analysis/demo
```

### 2. Douyin Creator Homepage Batch Fetch

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/fetch_douyin_user_posts.py \
  "https://www.douyin.com/user/MS4wLjABAAAA..." \
  --count 10 \
  --sort-type 1
```

### 3. Local SRT & Summary (Online Link or Local Media)

```text
/video-to-subtitle-summary https://www.xiaohongshu.com/explore/xxxxxx
/video-to-subtitle-summary /Users/me/Downloads/video.mp4
```

### 4. List Your AI Douyin Task History

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/list_ai_douyin_tasks.py --page 1 --page-size 20
```

## Setup Guides

| Topic | Guide |
| --- | --- |
| AI Douyin proxy & cloud billing | [Setup Guide](./docs/ai-douyin-setup.md) |
| faster-whisper runtime | [Setup Guide](./docs/faster-whisper-setup.md) |
| Volcengine VC (optional ASR) | [Setup Guide](./docs/bytedance-vc-setup.md) |

## Advanced Self-Hosted Options (Optional)

If you prefer your own TikHub token (`VIDEO_INFO_PROVIDER=tikhub`, see [TikHub Setup](./docs/tikhub-setup.md)) or Volcengine VC (`ASR_BACKEND=volcengine`), you can configure them in `.env`. Note that self-hosted mode only covers single-video download URL resolution and does not include cloud analysis, Douyin creator batch posts, comment insights, or task archiving.

## Project Structure

```text
video-to-subtitle-summary/
├── README.md
├── README_en.md
├── LICENSE
├── SKILL.md
├── .env.example
├── scripts/
│   ├── ai_douyin_client.py
│   ├── analyze_video_cloud.py
│   ├── download_video_candidates.py
│   ├── download_youtube_subtitles.py
│   ├── fetch_douyin_user_posts.py
│   ├── install_faster_whisper.py
│   ├── list_ai_douyin_tasks.py
│   └── transcribe_faster_whisper.py
├── tests/
│   ├── test_ai_douyin_client.py
│   ├── test_analyze_video_cloud.py
│   ├── test_download_video_candidates.py
│   ├── test_download_youtube_subtitles.py
│   ├── test_fetch_douyin_user_posts.py
│   ├── test_install_faster_whisper.py
│   ├── test_list_ai_douyin_tasks.py
│   └── test_transcribe_faster_whisper.py
└── docs/
    ├── ai-douyin-setup.md
    ├── tikhub-setup.md
    ├── faster-whisper-setup.md
    └── bytedance-vc-setup.md
```

## License

[MIT](./LICENSE)
