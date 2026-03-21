# NetClaw 项目文档

本文档整合自 `docs/` 目录，用于帮助 Claude 理解项目结构、配置方式和运行机制。

---

## 文档目录

- **start/**：安装与启动
- **configuration/**：配置结构与 Provider 说明
- **agents/**：Agent 架构、Prompt 与记忆机制
- **api/**：后端 API 参考
- **help/**：故障排查

---

## 5 分钟上手

### 目标

在 5 分钟内完成后端、前端启动，并确认流式对话可用。

### 前置条件

- Python 3.11+
- Node.js 20+
- 可用模型 Provider API Key（或本地 Ollama）

### 最小步骤

```bash
python scripts/dev.py
```

可选：仅启动后端或前端

```bash
python scripts/dev.py --backend-only
python scripts/dev.py --frontend-only
```

打开 `http://localhost:3000`，发送一句"你好"。

首次使用若未配置 Provider/模型：启动后在 Web 配置中心完成，或先运行 `cd backend && python cli.py onboard` 完成 CLI 配置后再执行 `python scripts/dev.py`。

### 成功判据

- 前端可看到 assistant 流式输出
- 后端日志无 500 错误
- Inspector 中能看到 lifecycle 事件

### 常见错误与修复

- `ModuleNotFoundError`：确认在 `backend/` 下执行并已安装依赖。
- 前端一直转圈：先检查后端 `http://localhost:8002/api/health` 是否可访问。
- 无模型响应：检查配置中心的 Provider `apiKey` 与默认模型是否匹配。
- 首次启动想免交互：使用 `python cli.py start --provider deepseek --api-key "sk-xxx" --model deepseek-chat`。
- 需要回到干净目录：使用 `python cli.py clean --clean`。
- 想跳过依赖安装：使用 `python scripts/dev.py --skip-install`。

---

## CLI 初始化速查

### 目标

通过命令行完成配置初始化与健康检查。

### 前置条件

- 已安装后端依赖
- 从仓库根目录进入：`cd backend`

### 最小步骤

```bash
cd backend
python cli.py setup
python cli.py onboard
python cli.py doctor
python cli.py serve
```

### 命令说明

- `setup`：创建 `data/config.json` 与默认工作区模板文件
- `onboard`：交互式写入 Provider、模型、默认 agent model
- `doctor`：检查配置完整性与关键文件状态
- `serve`：启动 FastAPI 服务

### 常见错误与修复

- `serve` 报未初始化：使用 `python cli.py setup` 后重试。
- `onboard` 后无模型：确认 `agents.defaults.model` 指向 `provider/modelId`。
- 端口占用：用 `--port` 更换端口，例如 `python cli.py serve --port 8010`。

---

## 环境与依赖

### 目标

建立稳定的本地运行环境，避免"装得上但跑不起来"。

### 前置条件

- macOS / Linux / Windows（WSL）

### 最小步骤

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
```

```bash
cd frontend
npm install
```

### 配置建议

- 在 `.env` 中维护密钥，`config.json` 使用 `${ENV_VAR}` 引用。
- 项目环境变量前缀统一为 `NETCLAW_*`。

### 常见错误与修复

- `npm` 安装失败：优先使用 Node.js 20 LTS。
- `pip` 编译失败：升级 `pip setuptools wheel` 后重试。
- 环境变量不生效：确认后端启动目录为 `backend/` 且 `.env` 位于该目录。

---

## Agent 架构

### 目标

理解一条用户消息如何从前端进入后端并产出 SSE 事件。

### 执行流（简化）

1. 前端 `streamChat` 发起请求并监听 SSE。
2. 后端按 `agent_id + session_id` 获取会话队列；忙碌则 followup 排队。
3. 后端 Agent 装配系统提示（prompt_builder + 工作区模板）。
4. 进入 LangGraph 执行：模型推理 -> 工具调用 -> 事件上报。
5. 前端根据 token/tool/lifecycle 事件实时渲染消息与 Inspector。
6. 用户主动停止时，前端调用 `/api/chat/abort`，后端取消 active run 并下发 `aborted`。

### 关键组件

- `backend/graph/agent.py`：会话、命令、工具调度核心
- `backend/graph/message_queue.py`：会话级串行与 followup 队列
- `backend/graph/prompt_builder.py`：full/minimal/none prompt 分层
- `backend/api/chat.py`：SSE 编排、中断事件与终态返回
- `frontend/src/lib/hooks/useChat.ts`：流式状态机、stop/abort 协同与异常回补
- `frontend/src/components/inspector/*`：运行态可视化

### 常见错误与修复

- 工具事件不闭合：检查 SSE `done` 或 `aborted` 是否收到，必要时前端会自动回补加载。
- `/new` 慢：当前采用后台异步记忆写入与索引重建，不阻塞主链路。
- stop 后立刻追问串写：前端应按当前流消息 id 更新，不应仅按最后一条消息更新。
- 子 Agent 状态不一致：查看 Inspector 事件和 `subagents list`。

---

## Prompt 与记忆机制

### 目标

确保提示词、工具能力、记忆机制形成闭环，不出现"提示词提到但系统没有"的能力。

### Prompt 分层

- `full`：身份、工具、消息路由、安全、技能、记忆、心跳、运行时、工作区上下文
- `minimal`：子 Agent 场景，保留必要约束与工具说明
- `none`：最小身份提示，仅用于极简模式

### 文档注入策略

系统提示强制加入 `docs/` 入口，要求任务前先读文档对应页面。

### 记忆策略

- 日常记忆：`memory/YYYY-MM-DD.md`
- 长期记忆：`MEMORY.md`
- `/new`：先重置会话，再后台异步保存会话记忆并发事件反馈

### 常见错误与修复

- 心跳只回 `HEARTBEAT_OK`：应先读 `HEARTBEAT.md`，仅在无事项时返回。
- 记忆保存阻塞：检查后台任务事件 `session_memory_saved/failed`。
- 提示词过长：切换 `minimal` 并减少上下文注入。

---

## 配置总览

### 目标

明确配置从模板到运行时的完整链路，避免"改了没生效"。

### 前置条件

- 已有 `backend/data/config.json`

### 结构概览

- `agents`：默认 agent 配置、agent 列表
- `models.providers`：各厂商 API、模型列表
- `tools`：工具总开关与细粒度配置
- `chat`：聊天请求超时（`timeoutSeconds`，0=无超时，默认 120）
- `session`：压缩、清理、上限
- `cron`：定时任务

### 超时配置

| 配置路径 | 说明 | 默认 |
|---------|------|------|
| `chat.timeoutSeconds` | 聊天请求超时秒数，0=无超时 | 120 |
| `agents.defaults.subagents.run_timeout_seconds` | 子 Agent 执行超时，0=无超时 | 0 |

### Exec 执行确认

`tools.exec.approval` 控制 exec、process_kill 等危险工具的执行前确认：

| 字段 | 说明 | 默认 |
|------|------|------|
| `security` | `deny` | `allowlist` | `full` | 安全策略 | 无配置时 `full` |
| `ask` | `off` | `on_miss` | `always` | 何时弹确认 | 无配置时 `off` |
| `ask_timeout_seconds` | 确认超时秒数 | 60 |
| `allowlist` | 白名单模式（glob） | [] |

- `security=full` + `ask=off`：无确认直接执行（当前默认行为）
- `security=allowlist`：仅白名单内命令可执行
- `ask=always`：每次执行都需用户确认
- `ask=on_miss`：白名单未命中时需确认

可选：`data/exec-approvals.json` 可追加 allowlist，与 config 合并。

### 生效机制

1. 读取原始配置（保留 `${ENV_VAR}`）。
2. 运行时解析环境变量得到 resolved 配置。
3. 前端提交时做 schema 校验与敏感字段保护。
4. 保存回 raw 配置，防止模板占位符丢失。

### 常见错误与修复

- 保存后密钥变成掩码：已做后端保护，不会覆盖真实密钥。
- provider/model 不匹配：检查 `agents.defaults.model` 是否为 `provider/modelId`。
- JSON 编辑器改完无效：确认提交后接口返回 200 且无校验错误。

---

## Provider 与模型配置

### 目标

用统一结构配置多家模型服务，并让前端可直接选择。

### 最小示例

```json
{
  "models": {
    "providers": {
      "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "apiKey": "${OPENAI_API_KEY}",
        "api": "openai-completions",
        "models": [
          { "id": "gpt-4o-mini", "name": "GPT-4o Mini", "contextWindow": 128000, "maxTokens": 16384 }
        ]
      }
    }
  },
  "agents": {
    "defaults": {
      "model": "openai/gpt-4o-mini"
    }
  }
}
```

### 厂商差异

- OpenAI / DeepSeek / OpenRouter：通常使用 `openai-completions`。
- Anthropic：使用 `anthropic-messages`。
- Ollama：本地推理，`baseUrl` 常见为 `http://localhost:11434`。

### 常见错误与修复

- 401：`apiKey` 错误或未替换环境变量。
- 404 model not found：`model.id` 与厂商端实际 ID 不一致。
- 前端下拉无模型：检查 provider 下 `models` 数组是否为空。

---

## API 参考（核心）

### 目标

快速定位关键接口和预期行为。

### 核心接口

- `POST /api/chat`：SSE 聊天流（token、tool、lifecycle、done、aborted）
- `POST /api/chat/abort`：中断指定会话正在运行的流（可选清空 followup 队列）
- `GET /api/agents`：获取 agent 列表
- `GET /api/agents/{id}/session/messages`：加载会话消息
- `PUT /api/config`：更新表单配置（脱敏字段保护）
- `GET /api/config`：脱敏后的完整配置
- `GET /api/config/chat`：聊天配置（`timeoutSeconds`，供前端请求超时）
- `GET /api/config/raw`：原始配置（默认仅 localhost）
- `PUT /api/config/replace`：整份替换配置（会恢复 masked secrets）
- `GET /api/init/status`：初始化状态（支持 CLI/前端双轨）
- `POST /api/approvals/{approval_id}/resolve`：用户确认/拒绝危险工具执行（Body: `{ "decision": "approved" | "denied" }`）

### SSE 事件建议

- 前端必须处理流结束残留 buffer，避免丢失最终 `done`。
- 对用户主动 stop，建议调用 `POST /api/chat/abort`，并优先消费 `aborted` 事件。
- 若不是用户主动停止且 `done` 未收到，回退到 `loadMessages` 做状态修复。
- 实现流式 UI 时，建议按"当前流消息 id"更新，而不是按"最后一条消息"更新，避免 stop 后立刻追问时事件串写。

### 中断与队列语义

- 会话级串行：同一 `agent_id + session_id` 同时只处理一条运行链路。
- 忙碌时新消息进入 followup 队列（返回 `queued` + `done`）。
- `POST /api/chat/abort` 会尝试取消该会话的当前运行任务。
- 发生中断时，后端会尽量保留并写入本轮 partial assistant 内容，并发送 `aborted` 终态事件。

### 常见错误与修复

- 403 on `/config/raw`：非本机访问被限制；可用环境变量显式放开。
- 422 校验错误：配置不符合 schema。
- 前端卡流：检查网络代理、SSE 分块与 `done/aborted` 事件。

---

## 常见问题排查

### 目标

按"症状 -> 检查 -> 修复"方式缩短故障定位时间。

### 症状 1：前端一直转圈

- 检查后端是否可达：`GET /api/health`
- 检查 SSE 是否有 `done` 或 `aborted` 事件
- 检查浏览器控制台是否有 CORS 或网络中断

### 症状 1.1：点 stop 后消息"消失"或界面突兀刷新

- 先确认前端 stop 是否调用了 `POST /api/chat/abort`（而不仅是本地断开流）。
- 确认后端能返回 `aborted` 事件；该事件应带回当前 partial 内容。
- 仅在"非用户主动 stop 且未收到 done/aborted"时，才建议回退 `loadMessages`。

### 症状 2：`/new` 感觉卡住

- 当前策略是前台快速 reset、后台保存记忆
- 在 Inspector 查看 `session_memory_saved` 或 `session_memory_failed`
- 若长期无事件，检查模型延迟与磁盘写入权限

### 症状 3：模型不可用

- 校验 `agents.defaults.model` 与 provider/modelId 是否一致
- 校验 `apiKey`、`baseUrl`、网络连通性
- 对私有网关检查兼容的 OpenAI 协议字段

### 症状 4：配置保存异常

- 确认 JSON 结构合法
- 避免将掩码值当成真实密钥提交（后端已做恢复保护）
- 看接口返回中的 schema error 详情

### 症状 5：stop 后立刻追问，内容串写到新消息

- 前端流式状态更新应锚定"本轮 assistant 消息 id"，不要依赖"最后一条消息"。
- 在 stop 后保留被中断 partial，可作为下一轮"否定信息"输入上下文。
- 如果偶发串写，检查是否有延迟到达的旧 run 事件未按消息 id 过滤。