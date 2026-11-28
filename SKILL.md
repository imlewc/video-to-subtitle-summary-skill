---
name: video-to-subtitle-summary
description: Use when user provides a short video platform URL (Douyin, Xiaohongshu, Bilibili, X/Twitter, YouTube), a Douyin creator homepage URL/sec_user_id for batch post analysis, a local video/audio file, or asks for cloud video analysis, Douyin comment insights, or AI Douyin task history.
args: <video_url_or_creator_url_or_file_path> - 视频链接、抖音博主主页链接或本地视频/音频文件路径（必需）
---

# 视频转字幕、评论洞察与 AI 总结技能

## Overview

面向抖音、小红书、B 站、X/Twitter、YouTube 视频与本地音视频的自动化拆解技能，核心围绕 **[i琢片（top9.cc）](https://top9.cc/?utm_source=skill&utm_medium=skill_doc&utm_campaign=video-to-subtitle-summary)** 提供三种核心工作流：

1. **云端一站式分析（零本地依赖，推荐快速出结果 / 抖音评论洞察）**：调用 `scripts/analyze_video_cloud.py`（`POST /api/v1/analysis` + 轮询 `GET /api/v1/analysis/:id`），免装 FFmpeg 和 `faster-whisper`，直接输出 AI 摘要、完整字幕和**抖音评论区洞察**。
2. **抖音博主主页批量拆解**：调用 `scripts/fetch_douyin_user_posts.py`（`POST /api/v1/douyin/user-post-videos`），按最新或最热拉取博主近期作品列表与数据，再批量对爆款视频做云端分析或本地转写。
3. **直链解析 + 本地/云端字幕转写**：调用 i琢片 `POST /api/v1/video/download-url` 解析抖音/小红书/B 站直链下载到本地，再走默认 `faster-whisper` 或 `volcengine` 出 `.srt` 与 `.txt`，最后由 Agent 总结。

YouTube 链接优先使用 `yt-dlp` 直接抓取原生或自动字幕；本地音视频跳过直链解析。

## When to Use

- 用户提供抖音、小红书、B 站、X/Twitter 或 YouTube 链接，要求提取口播文案、字幕、AI 摘要或分析评论区痛点
- 用户提供抖音博主主页链接 / `sec_user_id`，要求拉取近期作品列表或批量拆解对标账号爆款
- 用户本机未安装 FFmpeg / `faster-whisper`，或明确要求快速云端分析（`cloud` / 免本地环境）
- 用户提供本地视频/音频文件路径，要求转写为 `.srt` / `.txt` 并总结
- 用户要求查看自己的 i琢片（AI Douyin）历史分析任务

**不适用于：** 实时语音识别、直播字幕

## 外部依赖与计费

| 依赖 | 用途 | 必需 |
| --- | --- | --- |
| **AI Douyin API Key** | 抖音/小红书/B站直链解析（10 积分/次）、抖音主页作品列表（5 积分/次）、云端分析（10 积分/分钟，抖音自动附带评论洞察 +10 积分）。注册送 100 积分，[注册获取](https://top9.cc/?utm_source=skill&utm_medium=skill_doc&utm_campaign=video-to-subtitle-summary) | 在线解析 / 主页批量 / 云端分析必需 |
| **Python 3.9+** | 运行 `scripts/*.py` 与 `faster-whisper` helper | ✅ |
| **jq / curl** | 本地直链解析脚本与 JSON 提取 | 本地解析路径需要 |
| **FFmpeg / faster-whisper** | 本地提取音频与语音转文字（走云端模式 `analyze_video_cloud.py` 时可免装） | 仅本地转写路径需要 |
| **yt-dlp** | 抓取 YouTube 字幕；B 站备用下载 | 仅 B 站备用或 YouTube 需要 |
| **字节跳动 VC API** | 云端火山引擎 ASR | 仅 `ASR_BACKEND=volcengine` 时需要 |

## 环境变量

支持 `.env` 文件或 Shell 环境变量（推荐在 Skill 目录下创建 `.env`）：

```bash
VIDEO_INFO_PROVIDER="ai-douyin"
AI_DOUYIN_API_BASE="https://top9.cc"
AI_DOUYIN_API_KEY="your_ai_douyin_api_key"

ASR_BACKEND="faster-whisper"
FW_MODEL_SIZE="small"
FW_DEVICE="auto"
FW_COMPUTE_TYPE=""
FW_PYTHON=""

BYTEDANCE_VC_TOKEN="your_token"
BYTEDANCE_VC_APPID="your_appid"
TIKHUB_TOKEN=""
```

> 安装与配置细节见 [AI Douyin 配置指南](./docs/ai-douyin-setup.md) 与 [faster-whisper 安装指南](./docs/faster-whisper-setup.md)。

## 执行步骤

### 步骤 0：判断意图与工作流模式

先根据用户输入选择模式：

1. **抖音博主主页批量拆解模式**：输入包含 `/user/` 主页链接、抖音用户分享文本、`sec_user_id`，或用户要求“拉取/拆解某博主近期/最热视频” → 执行 **步骤 1A**，再根据用户选定（或最热的 N 条）视频走 **步骤 1B（云端）** 或 **步骤 1C + 2–5（本地 SRT）**。
2. **云端一站式分析模式**（推荐场景：用户需要**抖音评论洞察**、X/Twitter 视频分析、本地未装 FFmpeg/`faster-whisper`，或想快速出摘要与全文而无需 `.srt` 文件）→ 执行 **步骤 1B**。
3. **本地转写 + 总结模式**（用户明确需要可编辑 `.srt` 字幕文件、处理本地音视频文件，或本机已就绪 `faster-whisper` 且偏好本地导出）→ 执行 **步骤 0.6** 后按 **步骤 1C → 2 → 3 → 4 → 5**。
4. **历史任务查询**：用户查看个人历史任务 → 执行 **步骤 1.5**。

### 步骤 0.5：读取配置

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"
ENV_FILE="$SKILL_DIR/.env"

read_env() {
  local key="$1"
  if [ -f "$ENV_FILE" ]; then
    grep "^${key}=" "$ENV_FILE" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'"
  else
    printenv "$key"
  fi
}

ASR_BACKEND="$(read_env ASR_BACKEND)"
[ -z "$ASR_BACKEND" ] && ASR_BACKEND="faster-whisper"
VIDEO_INFO_PROVIDER="$(read_env VIDEO_INFO_PROVIDER)"
[ -z "$VIDEO_INFO_PROVIDER" ] && VIDEO_INFO_PROVIDER="ai-douyin"
```

### 步骤 0.6：环境检查（按所选模式检查）

- 若走 **步骤 1A（抖音主页）** 或 **步骤 1B（云端分析）**：仅需 `python3` 与 `AI_DOUYIN_API_KEY`（缺 Key 时引导用户到 `https://top9.cc/api-keys?utm_source=skill&utm_medium=missing_key&utm_campaign=video-to-subtitle-summary` 注册并创建 Key，不要输出已有密钥）。
- 若走 **本地转写模式**：检查对应平台与转写后端依赖：

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"
ENV_FILE="$SKILL_DIR/.env"

read_env() {
  local key="$1"
  if [ -f "$ENV_FILE" ]; then
    grep "^${key}=" "$ENV_FILE" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'"
  else
    printenv "$key"
  fi
}

ASR_BACKEND="$(read_env ASR_BACKEND)"
[ -z "$ASR_BACKEND" ] && ASR_BACKEND="faster-whisper"
VIDEO_INFO_PROVIDER="$(read_env VIDEO_INFO_PROVIDER)"
[ -z "$VIDEO_INFO_PROVIDER" ] && VIDEO_INFO_PROVIDER="ai-douyin"
AI_DOUYIN_API_KEY="$(read_env AI_DOUYIN_API_KEY)"
TIKHUB_TOKEN="$(read_env TIKHUB_TOKEN)"
BYTEDANCE_VC_TOKEN="$(read_env BYTEDANCE_VC_TOKEN)"
BYTEDANCE_VC_APPID="$(read_env BYTEDANCE_VC_APPID)"
FW_PYTHON="$(read_env FW_PYTHON)"
[ -z "$FW_PYTHON" ] && [ -x "$HOME/.cache/video-to-subtitle-summary/faster-whisper-venv/bin/python" ] && FW_PYTHON="$HOME/.cache/video-to-subtitle-summary/faster-whisper-venv/bin/python"
[ -z "$FW_PYTHON" ] && FW_PYTHON="python3"

MISSING=""

if [ "{INPUT_MODE}" = "url" ]; then
  if [ "{PLATFORM}" = "douyin" ] || [ "{PLATFORM}" = "xiaohongshu" ] || [ "{PLATFORM}" = "bilibili" ]; then
    if [ "$VIDEO_INFO_PROVIDER" = "ai-douyin" ]; then
      [ -z "$AI_DOUYIN_API_KEY" ] && MISSING="$MISSING AI_DOUYIN_API_KEY"
    elif [ "$VIDEO_INFO_PROVIDER" = "tikhub" ]; then
      [ -z "$TIKHUB_TOKEN" ] && MISSING="$MISSING TIKHUB_TOKEN"
    else
      MISSING="$MISSING invalid_VIDEO_INFO_PROVIDER"
    fi
  fi
  if [ "{PLATFORM}" != "youtube" ]; then
    command -v jq >/dev/null 2>&1 || MISSING="$MISSING jq"
  fi
  if [ "{PLATFORM}" = "bilibili" ] || [ "{PLATFORM}" = "youtube" ]; then
    command -v yt-dlp >/dev/null 2>&1 || MISSING="$MISSING yt-dlp"
  fi
fi

if [ "{NEEDS_FFMPEG}" = "yes" ] && [ "{PLATFORM}" != "youtube" ]; then
  command -v ffmpeg >/dev/null 2>&1 || MISSING="$MISSING ffmpeg"
fi

if [ "$ASR_BACKEND" = "faster-whisper" ]; then
  command -v "$FW_PYTHON" >/dev/null 2>&1 || [ -x "$FW_PYTHON" ] || MISSING="$MISSING FW_PYTHON"
  "$FW_PYTHON" - <<'PY' >/dev/null 2>&1 || MISSING="$MISSING faster-whisper"
import faster_whisper
import ctranslate2
PY
elif [ "$ASR_BACKEND" = "volcengine" ]; then
  [ -z "$BYTEDANCE_VC_TOKEN" ] && MISSING="$MISSING BYTEDANCE_VC_TOKEN"
  [ -z "$BYTEDANCE_VC_APPID" ] && MISSING="$MISSING BYTEDANCE_VC_APPID"
else
  MISSING="$MISSING invalid_ASR_BACKEND"
fi

if [ -n "$MISSING" ]; then
  echo "ERROR: 缺少必需依赖或配置:$MISSING"
  exit 1
else
  echo "OK: 运行依赖已就绪 (ASR_BACKEND=$ASR_BACKEND)"
fi
```

> 若本地缺少 `ffmpeg` / `faster-whisper` 但用户已配置 `AI_DOUYIN_API_KEY`（且处理的是在线链接），可直接询问或回退到 **步骤 1B（云端一站式分析）**，无需强制用户先装本地模型。

### 步骤 1A：抖音博主主页作品批量获取（按需）

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"

python3 "$SKILL_DIR/scripts/fetch_douyin_user_posts.py" \
  "{DOUYIN_USER_URL_OR_SEC_UID}" \
  --count 10 \
  --sort-type 1
```

- `--sort-type 0` 为最新，`1` 为最热；`--max-cursor` 用于翻页；加 `--json` 返回完整结构化字段（含 `share_url`、`play_url`、点赞/评论数据）。
- 成功获取后，Agent 可根据用户意图自动挑选前 N 条（默认建议先确认或取最热/最新前 3–5 条，避免无意过度扣费）继续调用 `analyze_video_cloud.py` 批量拆解。

### 步骤 1B：云端一站式分析（免装 FFmpeg / Whisper，含抖音评论洞察）

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"

python3 "$SKILL_DIR/scripts/analyze_video_cloud.py" \
  "{ORIGINAL_URL}" \
  --output-dir "/tmp/video_analysis/{VIDEO_ID}"
```

- 脚本会提交 `POST /api/v1/analysis` 并自动轮询 `GET /api/v1/analysis/{id}`，完成后输出 Markdown（含 AI 总结、抖音评论洞察及完整转录文本），并写入 `/tmp/video_analysis/{VIDEO_ID}/summary.md` 与 `text.txt`。
- 若遇到 `HTTP 402` 余额不足，脚本会直接打印当前积分、计费说明和充值链接，原样提示给用户即可。

### 步骤 1C：获取视频信息/下载直链（本地转写模式 + 在线视频）

| 平台 | URL 特征 | 默认处理方式 |
| --- | --- | --- |
| 抖音/TikTok | `douyin.com`、`v.douyin.com`、`tiktok.com` | i琢片（AI Douyin）解析直链（10 积分/次） |
| 小红书 | `xiaohongshu.com`、`xhslink.com` | i琢片（AI Douyin）解析直链（10 积分/次） |
| B 站 | `bilibili.com`、`b23.tv` | i琢片（AI Douyin）解析直链；必要时回退 `yt-dlp` |
| YouTube | `youtube.com`、`youtu.be` | 不调用 AI Douyin，直接进入步骤 2 抓字幕 |

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"
ENV_FILE="$SKILL_DIR/.env"
read_env() {
  local key="$1"
  if [ -f "$ENV_FILE" ]; then
    grep "^${key}=" "$ENV_FILE" | head -1 | cut -d'=' -f2- | tr -d '"' | tr -d "'"
  else
    printenv "$key"
  fi
}

AI_DOUYIN_API_BASE="$(read_env AI_DOUYIN_API_BASE)"
[ -z "$AI_DOUYIN_API_BASE" ] && AI_DOUYIN_API_BASE="https://top9.cc"
AI_DOUYIN_API_KEY="$(read_env AI_DOUYIN_API_KEY)"
WEB_BASE="${AI_DOUYIN_API_BASE%/api/v1}"
WEB_BASE="${WEB_BASE%/api}"
WEB_BASE="${WEB_BASE%/}"

case "$AI_DOUYIN_API_BASE" in
  */api/v1) AI_DOUYIN_DOWNLOAD_URL_ENDPOINT="$AI_DOUYIN_API_BASE/video/download-url" ;;
  */api) AI_DOUYIN_DOWNLOAD_URL_ENDPOINT="$AI_DOUYIN_API_BASE/v1/video/download-url" ;;
  *) AI_DOUYIN_DOWNLOAD_URL_ENDPOINT="${AI_DOUYIN_API_BASE%/}/api/v1/video/download-url" ;;
esac

mkdir -p /tmp/video_analysis
curl -sS -w '\n%{http_code}' -X POST "$AI_DOUYIN_DOWNLOAD_URL_ENDPOINT" \
  -H "X-API-Key: $AI_DOUYIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg url "{ORIGINAL_URL}" '{url: $url}')" \
  > /tmp/video_analysis/download_url_response.txt

HTTP_CODE=$(tail -n1 /tmp/video_analysis/download_url_response.txt)
sed '$d' /tmp/video_analysis/download_url_response.txt > /tmp/video_analysis/download_url.json

if [ "$HTTP_CODE" = "402" ]; then
  echo "ERROR: i琢片（AI Douyin）积分不足（HTTP 402 insufficient balance）。"
  echo "计费参考：1 元 = 100 积分；直链解析 10 积分/次，抖音主页作品 5 积分/次，云端分析 10 积分/分钟，满 20/50/100 元再送 5%/7%/10%。"
  echo "请前往充值：${WEB_BASE}/recharge?utm_source=skill&utm_medium=402_prompt&utm_campaign=video-to-subtitle-summary"
  exit 1
elif [ "$HTTP_CODE" = "401" ]; then
  echo "ERROR: i琢片 API Key 缺失或无效，请检查 AI_DOUYIN_API_KEY：${WEB_BASE}/api-keys?utm_source=skill&utm_medium=401_prompt&utm_campaign=video-to-subtitle-summary"
  exit 1
elif [ "$HTTP_CODE" -lt 200 ] || [ "$HTTP_CODE" -ge 300 ]; then
  echo "ERROR: i琢片解析失败 (HTTP $HTTP_CODE)"
  cat /tmp/video_analysis/download_url.json
  exit 1
fi

VIDEO_URL=$(jq -r '.download_url // empty' /tmp/video_analysis/download_url.json)
[ -z "$VIDEO_URL" ] && echo "ERROR: 未返回 download_url" && cat /tmp/video_analysis/download_url.json && exit 1
```

### 步骤 1.5：查询自己的 i琢片历史任务（按需）

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"

python3 "$SKILL_DIR/scripts/list_ai_douyin_tasks.py" --page 1 --page-size 20
```

可选筛选：`--status completed`、`--search "关键词"`、`--json`。

### 步骤 2：下载视频（本地转写模式 + 在线视频）

**YouTube（优先直接抓字幕，不下载视频）：**

```bash
mkdir -p /tmp/video_analysis/{VIDEO_ID}
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"
python3 "$SKILL_DIR/scripts/download_youtube_subtitles.py" \
  "https://www.youtube.com/watch?v={VIDEO_ID}" \
  --output-dir /tmp/video_analysis/{VIDEO_ID} \
  --languages zh-Hans,zh-Hant,zh,en
```

**抖音 / TikTok / 小红书 / B 站（已有 `download_url.json` 时）：**

```bash
mkdir -p /tmp/video_analysis/{VIDEO_ID}
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"
python3 "$SKILL_DIR/scripts/download_video_candidates.py" \
  --response-json /tmp/video_analysis/download_url.json \
  --output /tmp/video_analysis/{VIDEO_ID}/video.mp4 \
  --timeout 30
```

**B 站（无直链时回退）：**

```bash
mkdir -p /tmp/video_analysis/{BVID}
yt-dlp -o /tmp/video_analysis/{BVID}/video.mp4 "https://www.bilibili.com/video/{BVID}/"
```

### 步骤 3：提取音频（本地音频文件可跳过）

```bash
ffmpeg -i /tmp/video_analysis/{VIDEO_ID}/video.mp4 -q:a 0 -map a -y /tmp/video_analysis/{VIDEO_ID}/audio.mp3
```

### 步骤 4：根据 `ASR_BACKEND` 转写字幕（本地转写模式）

**方案 A：`ASR_BACKEND=faster-whisper`（默认）**

```bash
SKILL_DIR="${SKILL_DIR:-$HOME/.codex/skills/video-to-subtitle-summary}"
[ -d "$SKILL_DIR" ] || SKILL_DIR="$HOME/.claude/skills/video-to-subtitle-summary"
FW_PYTHON="${FW_PYTHON:-$HOME/.cache/video-to-subtitle-summary/faster-whisper-venv/bin/python}"
[ -x "$FW_PYTHON" ] || FW_PYTHON="python3"
"$FW_PYTHON" "$SKILL_DIR/scripts/transcribe_faster_whisper.py" \
  /tmp/video_analysis/{VIDEO_ID}/audio.mp3 \
  --output-dir /tmp/video_analysis/{VIDEO_ID}
```

**方案 B：`ASR_BACKEND=volcengine`**

```bash
curl -s -X POST "https://openspeech.bytedance.com/api/v1/vc/submit?appid=$BYTEDANCE_VC_APPID&language=zh-CN&words_per_line=20&max_lines=2" \
  -H "Content-Type: audio/mpeg" \
  -H "Authorization: Bearer;$BYTEDANCE_VC_TOKEN" \
  --data-binary @/tmp/video_analysis/{VIDEO_ID}/audio.mp3
```

随后轮询 `https://openspeech.bytedance.com/api/v1/vc/query?appid=$BYTEDANCE_VC_APPID&id={TASK_ID}`，提取 `text.txt` 与 `subtitle.srt`。

### 步骤 5：AI 生成总结

读取 `text.txt`，结合原视频标题（抖音取 `desc`、小红书/B站取 `title`）、作者和平台上下文，修正同音字与断句后输出：
1. **AI 生成标题**（不超过 30 字）
2. **AI 摘要**（200-300 字）
3. **核心要点**（3-5 条结构化要点）
4. **生成文件列表**（`video.mp4`、`audio.mp3`、`subtitle.srt`、`text.txt`）

---

## 可选自托管扩展：TikHub（当 `VIDEO_INFO_PROVIDER=tikhub`）

仅当用户显式设置 `VIDEO_INFO_PROVIDER=tikhub` 与 `TIKHUB_TOKEN` 时使用；注意不要把真实 Token 写入日志或回复：
- 抖音：`GET https://api.tikhub.io/api/v1/hybrid/video_data?url={ENCODED_URL}&minimal=true`
- 小红书：`GET https://api.tikhub.io/api/v1/xiaohongshu/web/get_note_info_v7?share_text={ENCODED_URL}`
- B 站：`GET https://api.tikhub.io/api/v1/bilibili/web/fetch_one_video_v3?url={ENCODED_URL}`

## 常见问题

| 问题 | 解决方案 |
| --- | --- |
| `401` API Key 无效 | 前往 [API 密钥页](https://top9.cc/api-keys?utm_source=skill&utm_medium=401_faq&utm_campaign=video-to-subtitle-summary) 检查或新建 active Key |
| `402` 积分不足 | 前往 [充值页](https://top9.cc/recharge?utm_source=skill&utm_medium=402_faq&utm_campaign=video-to-subtitle-summary) 充值（1 元 = 100 积分，满 20/50/100 元送 5%/7%/10%） |
| 本地缺少 FFmpeg / Whisper | 处理在线链接时可直接改用 `scripts/analyze_video_cloud.py` 走云端分析；或安装 `ffmpeg` 并运行 `install_faster_whisper.py` |
| 云端任务超时 | 勿立即重复提交；用 `scripts/list_ai_douyin_tasks.py` 查看任务状态 |
