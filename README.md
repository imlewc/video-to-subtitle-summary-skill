# video-to-subtitle-summary

一个 **Codex / Claude Code Skill**，基于 **[i琢片（top9.cc）](https://top9.cc/?utm_source=github&utm_medium=readme&utm_campaign=video-to-subtitle-summary)** 将抖音、小红书、B 站、X/Twitter、YouTube 视频与本地音视频自动转换为文字稿、SRT 字幕、AI 摘要与**抖音评论区洞察**，并支持**抖音对标博主主页批量拆解**。

[English](./README_en.md)

## 不想折腾本地环境？直接用在线版

如果你不是开发者，或只想粘贴链接马上出结果，无需安装任何软件：
- **网页版**：直接打开 [https://top9.cc](https://top9.cc/?utm_source=github&utm_medium=readme_online&utm_campaign=video-to-subtitle-summary)，注册即送 **100 积分**
- **微信小程序**：微信搜索「**琢片**」，粘贴抖音/小红书/B 站链接即可提取字幕、摘要与下载直链

## 复制给 Agent，一句话安装使用

将下面这段话复制给 Codex / Claude Code 等能操作本地环境的 Agent，替换末尾的链接即可：

```text
请安装并使用 https://github.com/imlewc/video-to-subtitle-summary-skill ，先阅读 README.md 和 SKILL.md，完成配置后帮我处理以下链接（默认使用 i琢片 https://top9.cc/?utm_source=github&utm_medium=readme_prompt&utm_campaign=video-to-subtitle-summary 的 API Key；如果是抖音博主主页就拉取近期作品并拆解爆款，如果是单条视频就提取字幕、摘要与评论洞察；缺少 API Key 时再提示我填写，不要输出密钥）：〔视频链接或抖音博主主页链接〕
```

## 核心能力

| 能力 | 适用场景 | 依赖要求 | 计费（1 元 = 100 积分） |
| --- | --- | --- | --- |
| **云端一站式分析（推荐）** | 抖音/小红书/B 站/X 视频摘要、完整转录、**抖音评论区痛点洞察** | 仅需 Python 3 + `AI_DOUYIN_API_KEY`（**免装 FFmpeg / Whisper**） | **10 积分/分钟**（最低 10 积分；抖音评论洞察 +10 积分） |
| **抖音博主主页批量获取** | 拉取对标博主最新/最热作品列表与点赞/评论数据，批量拆解口播 | 仅需 Python 3 + `AI_DOUYIN_API_KEY` | **5 积分/次** |
| **直链解析 + 本地 SRT** | 需要导出可编辑 `.srt` 字幕、剪辑对齐、或本地 `.mp4`/`.mp3` 转写 | Python 3 + FFmpeg + `faster-whisper` | 在线直链解析 **10 积分/次**；本地文件无 API 费用 |
| **YouTube 字幕直抓** | 抓取 YouTube 人工/自动字幕并总结 | `yt-dlp` | 无 API 费用 |

> 新用户注册 [i琢片（top9.cc）](https://top9.cc/?utm_source=github&utm_medium=readme&utm_campaign=video-to-subtitle-summary) 即送 **100 积分**；充值满 20/50/100 元分别加赠 5%/7%/10%，支持开具电子发票。

## 快速开始

### 1. 获取 i琢片 API Key（处理抖音/小红书/B 站/X 必需）

1. 打开 [https://top9.cc](https://top9.cc/?utm_source=github&utm_medium=readme_setup&utm_campaign=video-to-subtitle-summary) 注册/登录并完成邮箱验证。
2. 在 [API 密钥管理](https://top9.cc/api-keys?utm_source=github&utm_medium=readme_setup&utm_campaign=video-to-subtitle-summary) 创建一个 Key。
3. 复制 Skill 到 Codex / Claude Code 并配置 `.env`：

```bash
git clone https://github.com/imlewc/video-to-subtitle-summary-skill.git video-to-subtitle-summary

# Codex
mkdir -p ~/.codex/skills && cp -r video-to-subtitle-summary ~/.codex/skills/video-to-subtitle-summary

# Claude Code
mkdir -p ~/.claude/skills && cp -r video-to-subtitle-summary ~/.claude/skills/video-to-subtitle-summary

cp ~/.codex/skills/video-to-subtitle-summary/.env.example ~/.codex/skills/video-to-subtitle-summary/.env
# 在 .env 中填入 AI_DOUYIN_API_KEY="sk_xxx"
```

### 2. （可选）仅当你需要在本地生成 `.srt` 或处理本地文件时安装

- **FFmpeg**（本地视频提取音频）：`brew install ffmpeg`（macOS） / `sudo apt install ffmpeg`（Ubuntu）
- **yt-dlp**（B 站备用 / YouTube 字幕）：`brew install yt-dlp` 或 `python3 -m pip install -U yt-dlp`
- **faster-whisper**（本地语音转文字）：

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/install_faster_whisper.py
```

## 常用工作流示例

### 1. 零本地依赖：云端分析单条视频（含抖音评论洞察）

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/analyze_video_cloud.py \
  "https://v.douyin.com/xxxxxx/" \
  --output-dir /tmp/video_analysis/demo
```

直接向 Codex / Claude Code 发链接即可：

```text
用云端模式帮我拆解这条抖音视频，并重点总结评论区痛点：https://v.douyin.com/xxxxxx/
```

### 2. 抖音对标博主主页批量拆解

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/fetch_douyin_user_posts.py \
  "https://www.douyin.com/user/MS4wLjABAAAA..." \
  --count 10 \
  --sort-type 1
```

也可以直接告诉 Agent：

```text
拉取这个抖音博主最热的 10 条视频，挑点赞最高的 3 条做云端拆解，整理开头钩子和话术结构：https://www.douyin.com/user/MS4wLjABAAAA...
```

### 3. 本地转写导出 `.srt` 字幕（在线链接或本地文件）

```text
请帮我提取这个小红书视频的 SRT 字幕并总结重点：https://www.xiaohongshu.com/explore/xxxxxx
```

```text
/video-to-subtitle-summary /Users/me/Downloads/video.mp4
```

### 4. 查询自己的 i琢片历史任务

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/list_ai_douyin_tasks.py --page 1 --page-size 20
```

## 安装与技术文档

| 项目 | 文档 |
| --- | --- |
| i琢片 API 配置与计费 | [配置指南](./docs/ai-douyin-setup.md) |
| faster-whisper 本地运行时 | [安装指南](./docs/faster-whisper-setup.md) |
| 火山引擎 VC（可选 ASR） | [开通教程](./docs/bytedance-vc-setup.md) |

## 私有化部署支持

支持程序私有化部署，可落地到企业服务器或内网环境，满足数据隔离与合规要求。如需私有化部署方案、技术支持或商务合作，请联系：`eyr8odvl1i@163.com`

## 高级自托管选项（可选）

如果你已有自有 TikHub Token 或火山引擎 VC 账号，可在 `.env` 中切换 `VIDEO_INFO_PROVIDER=tikhub` 或 `ASR_BACKEND=volcengine`（参考 [TikHub 申请教程](./docs/tikhub-setup.md) 与 [火山引擎开通教程](./docs/bytedance-vc-setup.md)）。注意自托管链路仅提供基础单条视频解析，不包含云端分析、抖音博主批量拉取、评论洞察与任务归档。

## 项目结构

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
