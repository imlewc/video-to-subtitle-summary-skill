# video-to-subtitle-summary

一个 Codex / Claude Code Skill，自动将短视频平台（抖音、小红书、B 站、YouTube 等）视频或本地视频/音频文件转换为字幕文本并生成 AI 摘要。

**核心流程：**
- **在线视频：** 提供视频链接 → 自动下载视频或直接抓字幕 → 生成字幕 → AI 总结
- **本地文件：** 提供本地视频/音频路径 → 提取音频（如需） → 选择字幕后端 → 生成字幕 → AI 总结

默认字幕后端是本地 `faster-whisper`，也支持通过环境变量切换到火山引擎 VC。
YouTube 链接会优先用 `yt-dlp` 直接抓取人工字幕或自动字幕，不需要 AI Douyin/TikHub，也不会默认下载视频或跑 ASR。

[English](./README_en.md)

## 更新说明

当前版本支持两种字幕转写后端：
- **`faster-whisper`**：默认方案，本地转写，不依赖火山引擎
- **`volcengine`**：可选方案，使用火山引擎音视频字幕服务

这意味着：
- 默认情况下不需要注册和开通火山引擎
- 只有在 `ASR_BACKEND=volcengine` 时，才需要配置 `BYTEDANCE_VC_TOKEN` 和 `BYTEDANCE_VC_APPID`
- 如果你更看重本地化与零 API 转写费用，保持默认即可
- 如果你更偏好云端转写能力，切换环境变量即可

> 抖音、小红书、B 站默认推荐使用 [AI Douyin](https://top9.cc) 解析下载直链：注册后可用免费额度试用，成功解析一次扣 1 积分。已有 TikHub 用户也可以改用自有 `TIKHUB_TOKEN`。YouTube 直接由 `yt-dlp` 抓字幕。ASR 字幕识别后端由 `ASR_BACKEND` 控制。

## 一键免部署方案

不想本地安装和配置环境时，可直接使用在线版本：

- [https://top9.cc](https://top9.cc)

## 私有化部署支持

支持程序私有化部署，可落地到企业服务器或内网环境，满足数据隔离与合规要求。

如需私有化部署方案、技术支持或商务合作，请联系：`eyr8odvl1i@163.com`

## 效果展示

输入一个视频链接或本地文件路径，自动输出：

```markdown
## 视频分析结果

### 视频信息
| 项目 | 内容 |
|------|------|
| 视频ID | 7456789012345 |
| 作者 | 某知识博主 |
| 时长 | 3:25 |

### AI生成标题
深度解析 2024 年 AI 发展趋势与个人应对策略

### AI摘要
视频主要讨论了 2024 年 AI 技术的发展趋势，包括大模型的演进方向、
AI 在各行业的落地应用，以及普通人如何把握 AI 时代的机遇...

### 核心要点
1. 大模型正在从“通用智能”向“专业智能”演进
2. AI 应用层的创业机会远大于基础模型层
3. 掌握 AI 工具使用能力将成为职场核心竞争力

### 生成文件
- 视频: /tmp/video_analysis/7456789012345/video.mp4
- 音频: /tmp/video_analysis/7456789012345/audio.mp3
- SRT字幕: /tmp/video_analysis/7456789012345/subtitle.srt
- 纯文本: /tmp/video_analysis/7456789012345/text.txt
```

## 前置条件

| 依赖 | 说明 |
|------|------|
| Codex 或 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | 支持本地 Skill 的 Agent 环境 |
| [FFmpeg](https://ffmpeg.org/) | 音视频处理工具 |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | 视频下载和 YouTube 字幕抓取工具（B 站 / YouTube 需要） |
| [AI Douyin](https://top9.cc) API Key | 推荐的视频解析/下载代理；新用户免费额度，可避免单独注册 TikHub |
| [TikHub](https://tikhub.io/) 账号 | 可选视频接口获取方案：自带 Token 直接解析抖音/小红书/B 站 |
| Python 3.9+ + [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 当 `ASR_BACKEND=faster-whisper` 时需要 |
| [火山引擎](https://www.volcengine.com/) 账号 | 当 `ASR_BACKEND=volcengine` 时需要 |

## 快速安装

### 1. 选择字幕后端

默认推荐 `faster-whisper`：

```bash
ASR_BACKEND=faster-whisper
```

如需使用火山引擎：

```bash
ASR_BACKEND=volcengine
```

### 2. 按后端安装依赖

**方案 A：faster-whisper（默认）**

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/install_faster_whisper.py
```

> 安装 helper 会先测速 PyPI 镜像，选择最快可用源，再创建独立 venv 安装。默认按 CPU 路径运行；检测到 NVIDIA/CUDA 时会自动切到 GPU。Apple Silicon 会继续走 CPU 路径。GPU 安装细节见 [docs/faster-whisper-setup.md](./docs/faster-whisper-setup.md)。

**方案 B：火山引擎 VC（可选）**

按照 [docs/bytedance-vc-setup.md](./docs/bytedance-vc-setup.md) 开通服务并获取 `APPID` / `Token`。

### 2.5 安装 FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu / Debian
sudo apt install ffmpeg

# Windows (使用 Chocolatey)
choco install ffmpeg
```

### 2.8 安装 yt-dlp（B 站 / YouTube 需要）

```bash
# macOS
brew install yt-dlp

# 通用（需要 Python）
python3 -m pip install -U yt-dlp
```

### 3. 复制 Skill 到 Codex / Claude Code

```bash
# 克隆仓库
git clone https://github.com/imlewc/video-to-subtitle-summary-skill.git video-to-subtitle-summary

# Codex
mkdir -p ~/.codex/skills
cp -r video-to-subtitle-summary ~/.codex/skills/video-to-subtitle-summary

# Claude Code
mkdir -p ~/.claude/skills
cp -r video-to-subtitle-summary ~/.claude/skills/video-to-subtitle-summary
```

### 4. 配置环境变量

如需处理抖音、小红书或 B 站，推荐注册 [AI Douyin](https://top9.cc) 并创建 API Key；YouTube 不需要视频解析代理。已有 TikHub 用户可改用自有 TikHub Token。然后配置你要使用的字幕后端。

**方式一：使用 .env 文件（推荐）**

```bash
cp .env.example ~/.codex/skills/video-to-subtitle-summary/.env
# 编辑 .env 文件填入你的配置
```

**方式二：写入 Shell 配置**

```bash
# 添加到 ~/.zshrc 或 ~/.bashrc
export ASR_BACKEND="faster-whisper"

# 默认推荐：AI Douyin 代理（成功解析下载直链后扣 1 积分）
export VIDEO_INFO_PROVIDER="ai-douyin"
export AI_DOUYIN_API_BASE="https://top9.cc"
export AI_DOUYIN_API_KEY="your_ai_douyin_api_key"

# 可选视频接口获取方案：自有 TikHub Token
export TIKHUB_TOKEN=""

export FW_MODEL_SIZE="small"
export FW_DEVICE="auto"
export FW_COMPUTE_TYPE=""
export FW_PYTHON=""

export BYTEDANCE_VC_TOKEN="your_bytedance_vc_token"
export BYTEDANCE_VC_APPID="your_bytedance_vc_appid"
```

说明：
- `ASR_BACKEND`：可选，默认 `faster-whisper`
- `VIDEO_INFO_PROVIDER`：可选，默认 `ai-douyin`；可改为 `tikhub`
- `AI_DOUYIN_API_BASE` / `AI_DOUYIN_API_KEY`：默认推荐的视频解析代理；抖音/小红书/B 站需要；YouTube 不需要；成功解析下载直链后扣 1 积分
- `TIKHUB_TOKEN`：可选视频接口获取方案；当 `VIDEO_INFO_PROVIDER=tikhub` 或 AI Douyin 不可用时使用
- AI Douyin 返回 `402 insufficient balance` 时，表示免费额度用完或余额不足，可在平台充值积分，或切换为自有 TikHub Token
- `FW_MODEL_SIZE` / `FW_DEVICE` / `FW_COMPUTE_TYPE`：仅 `faster-whisper` 使用
- `FW_PYTHON`：可选，指定安装了 `faster-whisper` 的 Python；留空时优先使用安装 helper 创建的默认 venv
- `BYTEDANCE_VC_TOKEN` / `BYTEDANCE_VC_APPID`：仅 `volcengine` 使用

## 使用方法

### 在线视频

在 Claude Code 中直接发送视频链接即可（支持抖音、小红书、B 站、YouTube 等）：

```
请帮我提取这个视频的字幕并总结：https://v.douyin.com/xxxxxx/
```

```
请帮我总结这个小红书视频：https://www.xiaohongshu.com/explore/xxxxxx
```

```
请帮我总结这个B站视频：https://www.bilibili.com/video/BVxxxxxxxxxx/
```

```
请帮我总结这个 YouTube 视频：https://www.youtube.com/watch?v=O87FdYIPeQk
```

或者使用 skill 命令：

```
/video-to-subtitle-summary https://v.douyin.com/xxxxxx/
```

### 本地文件

直接提供本地视频或音频文件路径：

```
请帮我提取字幕并总结：/Users/me/Downloads/video.mp4
```

```
/video-to-subtitle-summary ~/Desktop/recording.mp3
```

> 本地文件模式会自动跳过视频下载步骤，音频文件还会跳过音频提取步骤，无需 AI Douyin/TikHub 视频解析代理。

### YouTube 字幕直抓

YouTube 链接优先执行：

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/download_youtube_subtitles.py \
  "https://www.youtube.com/watch?v=O87FdYIPeQk" \
  --output-dir /tmp/video_analysis/O87FdYIPeQk \
  --languages zh-Hans,zh-Hant,zh,en
```

生成 `/tmp/video_analysis/O87FdYIPeQk/subtitle.srt` 和 `/tmp/video_analysis/O87FdYIPeQk/text.txt`。如果视频没有可抓取字幕，再回退到下载音频并使用 `ASR_BACKEND` 转写。

### 查看自己的 AI Douyin 历史任务

已配置 `AI_DOUYIN_API_KEY` 后，可以查询当前 API Key 对应用户的历史任务：

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/list_ai_douyin_tasks.py \
  --page 1 \
  --page-size 20
```

可选筛选：

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/list_ai_douyin_tasks.py --status completed
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/list_ai_douyin_tasks.py --search "关键词" --json
```

该脚本默认读取 skill 目录 `.env` 或环境变量中的 `AI_DOUYIN_API_BASE` / `AI_DOUYIN_API_KEY`，调用 `GET /api/v1/tasks`，只返回当前用户自己的任务。

## 安装指南

| 项目 | 文档 |
|------|------|
| AI Douyin 代理 | [配置指南](./docs/ai-douyin-setup.md) |
| TikHub API（可选视频接口获取方案） | [申请教程](./docs/tikhub-setup.md) |
| faster-whisper 运行时 | [安装指南](./docs/faster-whisper-setup.md) |
| 火山引擎 VC | [开通教程](./docs/bytedance-vc-setup.md) |

## 费用说明

| 服务 | 费用 |
|------|------|
| AI Douyin 代理 | 新用户免费额度；成功解析下载直链后扣 1 积分，额度用完可充值 |
| TikHub API（可选） | 使用自有 TikHub Token 时按 TikHub 套餐计费 |
| YouTube 字幕抓取 | 无 API 费用，依赖本地 `yt-dlp` |
| faster-whisper | 无 API 费用，消耗本地 CPU/GPU 计算资源 |
| 火山引擎 VC | 仅在 `ASR_BACKEND=volcengine` 时产生字幕接口费用 |
| Claude Code | 取决于你的订阅计划 |

> 默认方案 `faster-whisper` 不会产生火山字幕接口费用。
> 首次运行 `faster-whisper` 会下载模型文件，之后会复用本地缓存。

## 项目结构

```text
video-to-subtitle-summary/
├── README.md                     # 项目介绍（本文件）
├── README_en.md                  # English README
├── LICENSE                       # MIT 协议
├── SKILL.md                      # Skill 本体
├── .env.example                  # 环境变量模板
├── scripts/
│   ├── download_video_candidates.py
│   ├── download_youtube_subtitles.py
│   ├── install_faster_whisper.py
│   ├── list_ai_douyin_tasks.py
│   └── transcribe_faster_whisper.py
├── tests/
│   ├── test_download_video_candidates.py
│   ├── test_download_youtube_subtitles.py
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
