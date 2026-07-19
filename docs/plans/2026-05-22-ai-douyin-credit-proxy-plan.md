# AI Douyin Credit Proxy Integration Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 让 `video-to-subtitle-summary` skill 默认支持 `https://top9.cc` 作为视频解析/下载代理：用户无需注册 TikHub，只需注册 AI Douyin、领取免费额度、创建 API Key 后即可试用；后续可在 AI Douyin 购买积分，或改回自有 TikHub Token。

**Architecture:** 保留 TikHub 直连作为可选高级/自托管路径；新增 AI Douyin API Key 路径作为默认推荐。后端新增“视频解析代理”计费语义（当前 `/api/v1/video/download-url` 已存在但不扣积分），skill 侧用 `AI_DOUYIN_API_BASE` + `AI_DOUYIN_API_KEY` 调用该代理拿到下载直链，再继续本地 ASR/总结流程。

**Tech Stack:** Go + Gin + GORM + Viper（`/Users/wangchang/code/ai-douyin/be`）；Next.js + TypeScript（`/Users/wangchang/code/ai-douyin/fe`）；Markdown Skill + Bash/curl/jq（`/Users/wangchang/code/video-to-subtitle-summary-skill`）。

---

## Phase 0: 边界确认

### Task 0.1: 确认商业规则

**Objective:** 明确免费额度与解析扣费，避免 skill 上线后无法计费。

**Files:**
- Modify later: `ai-douyin/be/configs/config.example.yaml`
- Modify later: `ai-douyin/be/internal/api/video.go`
- Modify later: `video-to-subtitle-summary-skill/README.md`

**Decision recommended:**
- 新注册用户继续获得当前默认免费余额。
- `POST /api/v1/video/download-url` 从“不扣积分”改成“扣少量积分”，建议配置项：`video_proxy.downloadUrlCost`，默认 `1`。
- 全量网站视频分析 `POST /api/v1/analysis` 保持现有按时长扣费逻辑。
- API Key 用户可用 `/api/v1/tasks` 或 `/api/v1/tasks/history` 查看自己任务；解析代理调用只产生交易记录，不必创建完整视频任务。

**Verification:** 产品文案里能解释清楚：
1. 免费额度可试用 skill。
2. 用完后可充值/购买积分。
3. 高级用户也可自己注册 TikHub 并配置 `TIKHUB_TOKEN`。

---

## Phase 1: 后端提供可计费的视频解析代理

### Task 1.1: 为解析代理增加配置项

**Objective:** 用配置控制 `/api/v1/video/download-url` 是否扣费和扣多少。

**Files:**
- Modify: `/Users/wangchang/code/ai-douyin/be/configs/config.example.yaml`
- Modify: `/Users/wangchang/code/ai-douyin/be/internal/api/video.go`
- Test: `/Users/wangchang/code/ai-douyin/be/internal/api/video_test.go`

**Implementation sketch:**
```yaml
video_proxy:
  download_url_cost: 1
  # true = 成功拿到 download_url 后扣费；false = 保持兼容，不扣费
  charge_download_url: true
```

**Behavior:**
- 只在成功返回 `download_url` 后扣费。
- 失败不扣费。
- 余额不足返回 HTTP `402`：
```json
{
  "error": "insufficient balance",
  "cost": 1,
  "extracted_url": "..."
}
```

**Verification:**
```bash
cd /Users/wangchang/code/ai-douyin/be
make test
```

---

### Task 1.2: 给 TransactionService 增加通用扣费方法

**Objective:** 避免复用“视频分析服务费用”的文案，给解析代理单独记账。

**Files:**
- Modify: `/Users/wangchang/code/ai-douyin/be/internal/services/transaction_service.go`
- Test: 新增或修改 `/Users/wangchang/code/ai-douyin/be/internal/services/transaction_service_test.go`

**Implementation sketch:**
```go
func (s *TransactionService) CreateVideoProxyUsageTransaction(
    userID uint64,
    amount uint64,
    videoURL string,
) (*models.Transaction, error) {
    // db.Transaction:
    // 1. SELECT user FOR UPDATE / or GORM transaction query
    // 2. if balance < amount return ErrInsufficientBalance
    // 3. update balance = balance - amount
    // 4. create Transaction{Type: models.TransactionTypeUsage, Amount: -int64(amount), Description: fmt.Sprintf("视频解析代理: %s", videoURL)}
}
```

**Pitfall:** 并发 API 调用时不能先读余额再单独扣，必须在事务里完成余额检查和扣减。

**Verification:**
```bash
go test -v ./internal/services -run TestCreateVideoProxyUsageTransaction
```

---

### Task 1.3: 修改 `GetVideoDownloadURL` 成功后扣费

**Objective:** API Key 用户调用 AI Douyin 代理时消耗积分，从而支撑免费试用/付费续费。

**Files:**
- Modify: `/Users/wangchang/code/ai-douyin/be/internal/api/video.go:222-257`
- Test: `/Users/wangchang/code/ai-douyin/be/internal/api/video_test.go`

**Implementation detail:**
- 从 context 取 `userId`（HybridAuth/APIKeyAuth 已设置）。
- 先调用 `api.videoService.GetVideoDownloadURL(extractedURL)`。
- 成功后读取：
```go
cost := viper.GetUint64("video_proxy.download_url_cost")
charge := viper.GetBool("video_proxy.charge_download_url")
if cost == 0 { cost = 1 }
```
- 如果 `charge` 为 true，调用 `transactionService.CreateVideoProxyUsageTransaction(userID, cost, extractedURL)`。
- 响应中增加：
```json
{
  "download_url": "...",
  "extracted_url": "...",
  "cost": 1
}
```

**Verification:**
```bash
cd /Users/wangchang/code/ai-douyin/be
go test -v ./internal/api -run 'TestGetVideoDownloadURL'
make test
```

---

### Task 1.4: 线上 API 使用说明与 curl 示例

**Objective:** 让 skill 和用户都能按稳定 API 接入。

**Files:**
- Modify: `/Users/wangchang/code/ai-douyin/be/docs/swagger.yaml`（通过 `make swagger`）
- Modify: `/Users/wangchang/code/ai-douyin/be/docs/swagger.json`（通过 `make swagger`）
- Modify: `/Users/wangchang/code/ai-douyin/DEPLOYMENT.md` 或新增 docs

**Public contract:**
```bash
curl -sS -X POST 'https://top9.cc/api/v1/video/download-url' \
  -H 'X-API-Key: sk_xxx' \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://v.douyin.com/.../"}'
```

**Expected response:**
```json
{
  "download_url": "https://...mp4...",
  "extracted_url": "https://v.douyin.com/.../",
  "cost": 1
}
```

---

## Phase 2: 前端引导用户注册、领免费额度、生成 API Key

### Task 2.1: API Key 页面加“给 Skill 使用”的引导

**Objective:** 用户进入 AI Douyin 后能快速知道如何生成 API Key 并复制到 skill。

**Files:**
- Inspect/Modify: `/Users/wangchang/code/ai-douyin/fe/src/app/api-keys/**`
- Modify likely: `/Users/wangchang/code/ai-douyin/fe/src/services/api.ts`

**UI copy:**
```text
给 video-to-subtitle-summary Skill 使用：
1. 注册/登录后，系统会赠送免费额度。
2. 创建一个 API Key。
3. 在 skill 的 .env 中配置：
   AI_DOUYIN_API_BASE=https://top9.cc
   AI_DOUYIN_API_KEY=sk_xxx
4. 没有额度时可充值；也可以配置自己的 TIKHUB_TOKEN 走 TikHub。
```

**Verification:**
```bash
cd /Users/wangchang/code/ai-douyin/fe
pnpm lint
pnpm build
```

---

### Task 2.2: 注册/余额页加免费额度与充值闭环说明

**Objective:** 让商业闭环清晰：免费试用 → 用完购买积分 → 或自带 TikHub。

**Files:**
- Inspect/Modify: `/Users/wangchang/code/ai-douyin/fe/src/app/(auth)/**`
- Inspect/Modify: `/Users/wangchang/code/ai-douyin/fe/src/app/dashboard/**`
- Inspect/Modify: `/Users/wangchang/code/ai-douyin/fe/src/app/payments/**`（如果存在）

**Verification:**
- 新用户注册后可以看到余额。
- API Key 页面能看到“余额不足时充值”的入口。

---

## Phase 3: 修改 Skill：默认推荐 AI Douyin，保留 TikHub 兜底

### Task 3.1: 更新 `.env.example`

**Objective:** 新用户先填 AI Douyin，而不是必须填 TikHub。

**Files:**
- Modify: `/Users/wangchang/code/video-to-subtitle-summary-skill/.env.example`

**New env:**
```bash
# 推荐：AI Douyin 代理，注册即可领取免费额度
AI_DOUYIN_API_BASE="https://top9.cc"
AI_DOUYIN_API_KEY=""

# 可选：如果你有自己的 TikHub Token，可绕过 AI Douyin 代理
TIKHUB_TOKEN=""

ASR_BACKEND="faster-whisper"
FW_MODEL_SIZE="small"
FW_DEVICE="auto"
FW_COMPUTE_TYPE=""
```

---

### Task 3.2: 更新 `SKILL.md` 的依赖与检查逻辑

**Objective:** 把“抖音/小红书/B 站必须 TikHub”改为“AI Douyin API Key 或 TikHub Token 二选一”。

**Files:**
- Modify: `/Users/wangchang/code/video-to-subtitle-summary-skill/SKILL.md`

**Required behavior:**
- 在线视频平台为抖音/小红书/B站时：
  - 若 `AI_DOUYIN_API_KEY` 存在，优先走 AI Douyin。
  - 否则若 `TIKHUB_TOKEN` 存在，走 TikHub。
  - 两者都没有时，提示：
    1. 去 `https://top9.cc` 注册领取免费额度并创建 API Key；或
    2. 自行注册 TikHub 并填 `TIKHUB_TOKEN`。

**Suggested pseudo shell:**
```bash
AI_DOUYIN_API_BASE="$(read_env AI_DOUYIN_API_BASE)"
[ -z "$AI_DOUYIN_API_BASE" ] && AI_DOUYIN_API_BASE="https://top9.cc"
AI_DOUYIN_API_KEY="$(read_env AI_DOUYIN_API_KEY)"
TIKHUB_TOKEN="$(read_env TIKHUB_TOKEN)"

if [ "$PLATFORM" != "youtube" ]; then
  if [ -z "$AI_DOUYIN_API_KEY" ] && [ -z "$TIKHUB_TOKEN" ]; then
    echo "ERROR: 缺少视频解析凭证。推荐注册 https://top9.cc 获取免费额度并创建 API Key；或配置自己的 TIKHUB_TOKEN。"
    exit 1
  fi
fi
```

---

### Task 3.3: 新增 AI Douyin 获取下载直链步骤

**Objective:** 在 skill 中通过 AI Douyin 代理拿到 `download_url`，下载视频后继续本地 ASR/总结。

**Files:**
- Modify: `/Users/wangchang/code/video-to-subtitle-summary-skill/SKILL.md`
- Optional Create: `/Users/wangchang/code/video-to-subtitle-summary-skill/scripts/fetch_ai_douyin_download_url.py`
- Test: `/Users/wangchang/code/video-to-subtitle-summary-skill/tests/test_fetch_ai_douyin_download_url.py`

**Preferred implementation:** 用 Python 脚本封装，避免 Markdown 里堆复杂 jq：
```python
# scripts/fetch_ai_douyin_download_url.py
# input: URL, env AI_DOUYIN_API_BASE, AI_DOUYIN_API_KEY
# output JSON: {"download_url": "...", "extracted_url": "...", "cost": 1}
```

**Curl equivalent:**
```bash
curl -sS -X POST "$AI_DOUYIN_API_BASE/api/v1/video/download-url" \
  -H "X-API-Key: $AI_DOUYIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"$VIDEO_URL\"}"
```

**Fallback:** 如果 AI Douyin 返回 `401/402/5xx`：
- 有 `TIKHUB_TOKEN`：自动 fallback 到 TikHub。
- 没有 `TIKHUB_TOKEN`：输出明确错误，特别处理 `402 insufficient balance`，提示充值或自带 TikHub。

---

### Task 3.4: 更新 README / README_en 商业引导

**Objective:** README 首页让用户知道“不用 TikHub 也能试”。

**Files:**
- Modify: `/Users/wangchang/code/video-to-subtitle-summary-skill/README.md`
- Modify: `/Users/wangchang/code/video-to-subtitle-summary-skill/README_en.md`

**Chinese copy:**
```markdown
### 不想注册 TikHub？
可以使用在线代理：注册 [AI Douyin](https://top9.cc) 后领取免费额度，创建 API Key，填入：

AI_DOUYIN_API_BASE=https://top9.cc
AI_DOUYIN_API_KEY=sk_xxx

免费额度用完后可在 AI Douyin 购买积分；如果你已有 TikHub，也可以直接配置 TIKHUB_TOKEN。
```

**Verification:**
- README 不再让用户误以为 TikHub 是唯一选择。
- 前置条件表格将 TikHub 改为“可选”。

---

## Phase 4: 端到端验证

### Task 4.1: 本地后端 API 测试

**Objective:** 确认 API Key 鉴权、扣费、返回下载直链可用。

**Commands:**
```bash
cd /Users/wangchang/code/ai-douyin/be
make test
make build
```

**Manual curl:**
```bash
curl -sS -X POST 'http://localhost:18088/api/v1/video/download-url' \
  -H 'X-API-Key: sk_test' \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://v.douyin.com/.../"}' | jq
```

---

### Task 4.2: Skill 端测试

**Objective:** 验证无 TikHub Token、仅 AI Douyin API Key 时能跑完整流程。

**Commands:**
```bash
cd /Users/wangchang/code/video-to-subtitle-summary-skill
python3 -m pytest tests -q
```

**Manual test matrix:**
1. `AI_DOUYIN_API_KEY` 有效，`TIKHUB_TOKEN` 为空：应成功。
2. `AI_DOUYIN_API_KEY` 余额不足，`TIKHUB_TOKEN` 为空：提示充值/自带 TikHub。
3. `AI_DOUYIN_API_KEY` 无效，`TIKHUB_TOKEN` 有效：fallback 成功。
4. YouTube：不调用 AI Douyin/TikHub，仍走 `yt-dlp` 字幕优先。

---

## Phase 5: 部署与发布

### Task 5.1: 部署 AI Douyin 后端/前端

**Objective:** 线上 `https://top9.cc` 提供稳定代理能力。

**Commands:**
```bash
cd /Users/wangchang/code/ai-douyin
skills/deploy-douyin-be/scripts/deploy.sh
skills/deploy-douyin-fe/scripts/deploy.sh
```

**Pitfall:** 远端后端仓库可能有 server-local commits；如果 `git pull` divergent，先备份远端分支，再 rebase 到 origin/main。

---

### Task 5.2: 发布 Skill 更新

**Objective:** 用户安装新版 skill 后可直接按 AI Douyin 流程配置。

**Commands:**
```bash
cd /Users/wangchang/code/video-to-subtitle-summary-skill
git status
git diff
git add SKILL.md README.md README_en.md .env.example scripts/ tests/ docs/plans/
git commit -m "feat: support ai douyin credit proxy"
```

**Release notes:**
- 新增 `AI_DOUYIN_API_BASE` / `AI_DOUYIN_API_KEY`。
- TikHub 从必需改为可选。
- 免费试用入口：`https://top9.cc`。
- 余额不足时可充值或配置自有 TikHub。

---

## Confirmed Decisions

1. `POST /api/v1/video/download-url` 从“不创建分析任务、不扣积分”改为：**成功解析下载直链后扣 1 积分**。
2. 失败不扣积分。
3. 余额不足返回 HTTP `402`，错误语义为 `insufficient balance`，提示用户充值或改用自有 TikHub Token。

## Open Questions

1. AI Douyin 当前是否已给新用户默认余额？如果没有，需要补注册奖励逻辑或运营配置。
2. Skill 是否只需要“解析下载直链 + 本地 ASR/总结”，还是要直接调用 AI Douyin 的完整 `/api/v1/analysis` 并轮询结果？当前推荐前者，因为它保留 skill 的本地 ASR 能力，且接入最小。
3. 是否需要给 AI Douyin 增加“仅解析接口”的独立使用统计页面？如果后续要商业化，建议加。
