# i琢片（AI Douyin）API 配置指南

i琢片（`top9.cc`）为本 Skill 提供抖音、小红书、B 站与 X/Twitter 的视频直链解析、**抖音博主主页批量获取**，以及**免本地依赖的云端 AI 视频分析（含抖音评论洞察）**。

## 适用场景

- 处理抖音、小红书、B 站链接时，自动解析无水印/高清视频下载直链。
- 批量获取抖音博主主页的最新/最热作品列表，快速筛选爆款进行拆解。
- 不想在本地安装 FFmpeg / `faster-whisper` 时，直接调用云端一站式分析（输出摘要、关键词、完整字幕，抖音视频自动附带评论区洞察）。
- YouTube 链接仍优先使用 `yt-dlp` 直接抓取原生/自动字幕，无需消耗积分。

## 获取 API Key

1. 打开 [https://top9.cc](https://top9.cc/?utm_source=github&utm_medium=setup_doc&utm_campaign=video-to-subtitle-summary)
2. 注册/登录账号并完成邮箱验证（新用户注册即送 **100 积分**）。
3. 进入 [API 密钥页面](https://top9.cc/api-keys?utm_source=github&utm_medium=setup_doc&utm_campaign=video-to-subtitle-summary) 创建并复制 Key。
4. 在本 Skill 的 `.env` 中填入：

```bash
VIDEO_INFO_PROVIDER=ai-douyin
AI_DOUYIN_API_BASE=https://top9.cc
AI_DOUYIN_API_KEY=sk_xxx
```

## 计费规则（1 元 = 100 积分）

| 能力 | 接口 | 计费规则 |
| --- | --- | --- |
| 视频下载直链解析 | `POST /api/v1/video/download-url` | 成功解析扣 **10 积分/次**；失败不扣 |
| 抖音博主主页作品列表 | `POST /api/v1/douyin/user-post-videos` | 成功解析扣 **5 积分/次**；失败不扣 |
| 云端视频分析（含抖音评论洞察） | `POST /api/v1/analysis` + `GET /api/v1/analysis/:id` | **10 积分/分钟**（最低 10 积分）；抖音视频自动附带评论洞察（+10 积分） |
| 历史任务查询 | `GET /api/v1/tasks` | 免费 |

充值满 20 元多送 5%，满 50 元多送 7%，满 100 元多送 10%；支持开具电子发票。
余额不足时，可在 [充值页](https://top9.cc/recharge?utm_source=github&utm_medium=setup_doc&utm_campaign=video-to-subtitle-summary) 补充积分。

## 核心能力与调用方式

### 1. 获取视频下载直链

```bash
curl -sS -X POST "https://top9.cc/api/v1/video/download-url" \
  -H "X-API-Key: sk_xxx" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://v.douyin.com/xxxxxx/"}'
```

成功响应示例：

```json
{
  "download_url": "https://...",
  "download_urls": ["https://...", "https://..."],
  "extracted_url": "https://v.douyin.com/xxxxxx/",
  "cost": 10
}
```

### 2. 批量获取抖音博主主页作品

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/fetch_douyin_user_posts.py \
  "https://www.douyin.com/user/MS4wLjABAAAA..." \
  --count 10 \
  --sort-type 1
```

- `--sort-type 0` 按最新排序，`1` 按最热排序；每页最多 20 条。

### 3. 零本地依赖云端视频分析（含抖音评论洞察）

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/analyze_video_cloud.py \
  "https://v.douyin.com/xxxxxx/" \
  --output-dir /tmp/video_analysis/demo
```

会提交云端任务并自动轮询直到完成，输出摘要、抖音评论洞察（抖音链接）和完整转录文本。

### 4. 查询历史任务

```bash
python3 ~/.codex/skills/video-to-subtitle-summary/scripts/list_ai_douyin_tasks.py \
  --page 1 \
  --page-size 20
```

脚本默认读取 Skill 目录 `.env` 或环境变量中的 `AI_DOUYIN_API_BASE` / `AI_DOUYIN_API_KEY`，调用 `GET /api/v1/tasks`，只返回当前用户自己的任务。

## 故障处理

- `401`：API Key 缺失、无效或已撤销。请前往 [API 密钥页面](https://top9.cc/api-keys?utm_source=github&utm_medium=setup_doc_401&utm_campaign=video-to-subtitle-summary) 重新复制 active Key。
- `402 insufficient balance`：免费额度或当前积分不足。请前往 [充值页](https://top9.cc/recharge?utm_source=github&utm_medium=setup_doc_402&utm_campaign=video-to-subtitle-summary) 充值积分后重试。
- `5xx`：视频平台暂时不可用或解析超时，请稍后重试；提交云端分析后若轮询超时，请先通过 `list_ai_douyin_tasks.py` 查看任务状态，避免重复提交扣费。

## 可选自托管说明

如已有自有 TikHub Token，可在 `.env` 中设置 `VIDEO_INFO_PROVIDER=tikhub` 与 `TIKHUB_TOKEN`，详细见 [TikHub 申请教程](./tikhub-setup.md)（仅覆盖基础单条视频解析，不包含云端 AI 总结、抖音评论洞察与任务归档）。
