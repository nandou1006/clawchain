# Session重构和权限管理计划

## 背景

当前ClawChain是单用户本地应用，没有用户认证机制。本计划实现：
1. **多用户Session隔离** - 不同用户的会话互不可见
2. **用户角色管理** - admin/user两种角色
3. **API Key认证** - 支持`/api/chat`接口的API访问

---

## 1. 配置Schema扩展

### 1.1 新增配置结构 (`backend/config_schema.py`)

```python
# 用户配置
class UserConfig(BaseModel):
    id: str
    name: Optional[str] = None
    role: Literal["admin", "user"] = "user"

class UsersConfig(BaseModel):
    enabled: bool = False
    default_user_id: str = "default"
    users: List[UserConfig] = Field(default_factory=list)

# API Key配置（单个key）
class ApiKeyConfig(BaseModel):
    enabled: bool = False
    key: Optional[str] = None  # 单个API key

class AuthConfig(BaseModel):
    api_key: ApiKeyConfig = Field(default_factory=ApiKeyConfig)
    users: UsersConfig = Field(default_factory=UsersConfig)

# 扩展ClawChainConfig
class ClawChainConfig(BaseModel):
    # ... existing fields ...
    auth: AuthConfig = Field(default_factory=AuthConfig)
```

### 1.2 配置示例 (`data/config.json`)

```json
{
  "auth": {
    "api_key": {
      "enabled": true,
      "key": "sk-xxxxxxxxxxxx"
    },
    "users": {
      "enabled": true,
      "default_user_id": "default",
      "users": [
        {"id": "default", "name": "Default", "role": "admin"},
        {"id": "ethannan", "name": "Ethan", "role": "admin"},
        {"id": "jiaweicui", "name": "Jiawei", "role": "user"}
      ]
    }
  }
}
```

### 1.3 环境变量引用

API Key支持环境变量引用，避免明文存储：

```json
{
  "auth": {
    "api_key": {
      "enabled": true,
      "key": "${CLAWCHAIN_API_KEY}"
    }
  }
}
```

---

## 2. 后端实现

### 2.1 认证模块 (新建 `backend/api/auth.py`)

**说明**：认证逻辑暂不实现，接口预留。

| 函数 | 说明 |
|------|------|
| `get_user_id_from_request(request)` | 从URL参数/Header获取user_id |
| `verify_api_key(request)` | 验证X-API-Key header（暂留空） |
| `get_user_role(user_id)` | 查询用户角色，返回给前端判断页面路由 |
| `require_admin(user_id)` | 依赖注入：要求admin角色（暂留空） |

**get_user_role 用途**：
```python
def get_user_role(user_id: str) -> str:
    """查询用户角色，供前端判断进入管理员页面还是普通用户页面"""
    from config import get_config
    cfg = get_config()
    users = cfg.get("auth", {}).get("users", {}).get("users", [])
    for user in users:
        if user.get("id") == user_id:
            return user.get("role", "user")
    return "user"
```

**新增API端点**：
```
GET /api/auth/user/{user_id} -> 返回 { id, role, name }
```

前端根据返回的 `role` 字段决定页面路由：
- `admin` → 管理员页面
- `user` → 普通用户页面

### 2.2 Session Manager重构 (`backend/graph/session_manager.py`)

**核心变更**：所有方法添加`user_id`参数

| 方法 | 变更 |
|------|------|
| `_session_path(session_id, agent_id, user_id)` | 路径变为 `sessions/{user_id}/{session_id}.json` |
| `load_session(session_id, agent_id, user_id)` | 按user_id加载session |
| `save_message(..., user_id)` | 按user_id保存消息 |
| `list_sessions(agent_id, user_id)` | 列出用户的sessions |
| `list_all_sessions(agent_id, admin_user_id)` | 管理员查看所有用户sessions |

**缓存Key变更**：`{agent_id}:{user_id}:{session_id}`

**Session存储结构**：
```
data/agents/{agent_id}/sessions/
├── {user_id}/
│   ├── {session_id}.json
│   └── sessions.json
├── default/          # 默认用户（向后兼容）
│   └── ...
└── archive/
```

### 2.3 Chat API修改 (`backend/api/chat.py`)

```python
class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    agent_id: str = "main"
    stream: bool = True
    user_id: str = ""  # 新增，前端传入

@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    # 解析user_id
    user_id = req.user_id or get_user_id_from_request(request)

    # 传递user_id到下游
    # ...
```

### 2.4 Sessions API修改 (`backend/api/sessions.py`)

| 端点 | 变更 |
|------|------|
| `GET /agents/{id}/session` | 返回用户特定的session |
| `GET /agents/{id}/sessions` | 返回用户sessions；`?all_users=true`返回所有（仅admin） |
| `GET /agents/{id}/sessions/{sid}/messages` | 验证session归属 |

### 2.5 Message Queue修改 (`backend/graph/message_queue.py`)

队列Key变更：`{agent_id}:{user_id}:{session_id}`

### 2.6 Config模块修改 (`backend/config.py`)

```python
def resolve_agent_sessions_dir(agent_id: str, user_id: str = "default") -> Path:
    base = resolve_agent_dir(agent_id) / "sessions"
    if user_id and user_id != "default":
        return base / user_id
    return base
```

---

## 3. 前端实现

### 3.1 访问控制 (`frontend/src/app/page.tsx`)

**强制user_id验证**：URL参数必须携带`user_id`，否则跳转到"无法访问"页面。

**URL参数**：
- `user_id`：必需，用户标识
- `agent_id`：可选，默认为"main"
- `session_id`：可选，默认为主会话

**角色路由**：根据用户角色进入不同页面。

```typescript
import { useSearchParams, useRouter } from "next/navigation";

function HomeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const userId = searchParams.get("user_id");
  const agentId = searchParams.get("agent_id") || "main";
  const sessionId = searchParams.get("session_id");

  // 无user_id时跳转到错误页面
  useEffect(() => {
    if (!userId) {
      router.push("/unauthorized");
      return;
    }

    // 获取用户角色并设置
    const initUser = async () => {
      setUserId(userId);
      const userInfo = await api.fetchUserInfo(userId);
      setUserRole(userInfo.role);
      setAgentId(agentId);
      if (sessionId) setCurrentSessionId(sessionId);
      loadAgents();
    };
    initUser();
  }, [userId, agentId, sessionId]);

  if (!userId) {
    return null; // 或显示loading
  }

  // 根据角色渲染不同页面
  if (userRole === "admin") {
    return <AdminPage />;
  }
  return <UserPage />;
}
```

### 3.2 错误页面 (新建 `frontend/src/app/unauthorized/page.tsx`)

```typescript
export default function UnauthorizedPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen">
      <h1 className="text-2xl font-bold">无法访问</h1>
      <p className="text-gray-500 mt-2">请在URL中提供有效的 user_id 参数</p>
      <p className="text-sm text-gray-400 mt-4">示例: localhost:3000/?user_id=ethannan</p>
    </div>
  );
}
```

### 3.3 管理员页面与普通用户页面

```typescript
// 新建 frontend/src/components/admin/AdminPage.tsx
export function AdminPage() {
  // 管理员特有功能：显示Navbar、查看所有用户sessions等
  return (
    <>
      <Navbar />
      <ChatPanel />
    </>
  );
}

// 新建 frontend/src/components/user/UserPage.tsx
export function UserPage() {
  // 普通用户功能：不显示Navbar
  return <ChatPanel />;
}
```

### 3.4 Session列表功能 (`frontend/src/components/chat/ChatPanel.tsx`)

**UI变更**：在ChatPanel顶部Navbar添加Session列表入口。

```
                                                       【原来的Navbar】
┌─────────────────────────────────────────────────────────┐
│ [MessageSquare] Agent: main       [Inspector] [Settings]│
├─────────────────────────────────────────────────────────┤
│                                                         │
│  [会话列表弹窗]                                          │
│  ┌─────────────────────┐                               │
│  │ 会话列表 (user: xxx) │                               │
│  │ ───────────────────  │                               │
│  │ • 主会话 (当前)      │                               │
│  │   2026.03.19...      │                               │
│  │ • 昨天的会话         │                               │
│  │   2026.03.18...      │                               │
│  │ • 3天前的会话        │                               │
│  │   2026.03.16...      │                               │
│  └─────────────────────┘                               │
│                                                         │
│  [聊天消息区域]                                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**交互逻辑**：点击会话条目，通过URL参数跳转到对应会话。

```
点击 -> 跳转 URL: localhost:3000/?user_id=xxx&agent_id=main&session_id=xxx
```

**组件实现**：

```typescript
// SessionList.tsx - 新建组件
import { MessageSquare } from "lucide-react";

interface SessionListProps {
  agentId: string;
  userId: string;
  currentSessionId: string;
}

export function SessionList({ agentId, userId, currentSessionId }: SessionListProps) {
  const [open, setOpen] = useState(false);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const router = useRouter();

  // 加载会话列表
  const loadSessions = async () => {
    const data = await api.fetchSessions(agentId, userId);
    setSessions(data);
  };

  // 点击会话 -> 跳转URL
  const handleSelectSession = (sessionId: string) => {
    setOpen(false);
    router.push(`/?user_id=${userId}&agent_id=${agentId}&session_id=${sessionId}`);
  };

  return (
    <>
      <Button variant="ghost" size="icon" onClick={() => { setOpen(true); loadSessions(); }}>
        <MessageSquare className="w-5 h-5" />
      </Button>
      {open && (
        <Dialog onClose={() => setOpen(false)}>
          <DialogTitle>会话列表 ({userId})</DialogTitle>
          <List>
            {sessions.map(session => (
              <ListItem key={session.session_id}>
                <ListItemButton onClick={() => handleSelectSession(session.session_id)}>
                  <div className="flex flex-col">
                    <span>{session.label || "未命名会话"}</span>
                    <span className="text-xs text-gray-500">{session.updated_at}</span>
                  </div>
                  {session.session_id === currentSessionId && <span className="text-xs text-blue-500">(当前)</span>}
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Dialog>
      )}
    </>
  );
}
```

### 3.4 ChatPanel修改

```typescript
// ChatPanel.tsx 顶部新增
import { SessionList } from "./SessionList";

<div className="flex items-center gap-2 px-4 py-2 border-b">
  <SessionList
    agentId={currentAgentId}
    userId={userId}
    currentSessionId={currentSessionId}
  />
  <span className="text-sm font-medium">Agent: {currentAgent?.name || currentAgentId}</span>
</div>
```

### 3.5 Store扩展 (`frontend/src/lib/store.tsx`)

```typescript
interface AppState {
  // ...existing
  userId: string;
  setUserId: (id: string) => void;
  userRole: "admin" | "user" | null;
  // URL参数状态
  agentId: string;
  setAgentId: (id: string) => void;
}
```

### 3.6 API模块修改 (`frontend/src/lib/api.ts`)

- 所有请求携带`user_id`参数

```typescript
export async function streamChat(message, sessionId, agentId, onEvent, opts) {
  const userId = getUserId(); // 从URL获取

  await fetch(`${API_BASE}/chat?user_id=${userId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id, agent_id, user_id, stream: true }),
  });
}

// 获取用户信息和角色
export async function fetchUserInfo(userId: string): Promise<{ id: string; role: string; name?: string }> {
  const resp = await fetch(`${API_BASE}/auth/user/${userId}`);
  return resp.json();
}

// 获取用户会话列表
export async function fetchSessions(agentId: string, userId: string): Promise<SessionInfo[]> {
  const resp = await fetch(`${API_BASE}/agents/${agentId}/sessions?user_id=${userId}`);
  return resp.json();
}
```

---

## 4. 迁移策略

### 4.1 现有数据处理

1. 现有session文件归档或迁移到指定用户目录
2. API签名保持兼容（user_id有默认值，但前端强制传值）

### 4.2 迁移脚本 (`backend/scripts/migrate_sessions.py`)

将现有session文件移动到指定用户目录：
```python
# sessions/main-main.json -> sessions/{user_id}/main-main.json
```

---

## 5. 关键文件清单

### 5.1 后端文件

| 文件 | 修改类型 |
|------|----------|
| `backend/config_schema.py` | 新增AuthConfig、UsersConfig |
| `backend/api/auth.py` | 新建（get_user_role等，鉴权逻辑暂留空） |
| `backend/api/sessions.py` | 添加用户隔离 |
| `backend/graph/session_manager.py` | 重构（添加user_id参数） |
| `backend/graph/message_queue.py` | 修改队列Key |
| `backend/api/chat.py` | 添加user_id参数 |
| `backend/config.py` | 添加resolve_agent_sessions_dir(user_id) |

### 5.2 前端文件

| 文件 | 修改类型 |
|------|----------|
| `frontend/src/app/page.tsx` | 访问控制、角色路由（无user_id跳转错误页） |
| `frontend/src/app/unauthorized/page.tsx` | 新建错误页面 |
| `frontend/src/components/admin/AdminPage.tsx` | 新建管理员页面（显示Navbar） |
| `frontend/src/components/user/UserPage.tsx` | 新建普通用户页面（不显示Navbar） |
| `frontend/src/components/chat/ChatPanel.tsx` | 添加Session列表按钮、Agent名称显示 |
| `frontend/src/components/chat/SessionList.tsx` | 新建Session列表组件 |
| `frontend/src/lib/store.tsx` | 添加userId、userRole状态 |
| `frontend/src/lib/api.ts` | 添加user_id参数、fetchUserInfo、fetchSessions |

---

## 6. 安全考虑

1. **Session隔离**：路径包含user_id，防止越权访问
2. **角色区分**：前端根据角色显示不同UI（管理员显示Navbar，普通用户不显示）
3. **敏感配置**：API Key使用`${ENV_VAR}`引用

---

## 7. 验证方案

### 7.1 功能测试

1. **访问控制**：
   - 访问`localhost:3000`无user_id -> 跳转到错误页面
   - 访问`localhost:3000/?user_id=ethannan` -> 正常进入

2. **用户隔离**：
   - 用户A创建session，用户B不可见
   - 用户A无法访问用户B的session

3. **角色验证**：
   - admin用户登录 -> 显示Navbar
   - 普通用户登录 -> 不显示Navbar
   - admin可以查看所有用户sessions

4. **Session列表**：
   - 点击会话列表图标，弹出当前用户的所有会话
   - 点击会话条目，跳转到对应会话URL
   - Agent名称正确显示在图标右侧

### 7.2 启动验证

```bash
# 1. 配置多用户
# 2. 启动服务
python scripts/dev.py

# 3. 测试访问控制
open "http://localhost:3000"  # 应跳转到错误页面

# 4. 测试管理员用户（显示Navbar）
open "http://localhost:3000/?user_id=ethannan"

# 5. 测试普通用户（不显示Navbar）
open "http://localhost:3000/?user_id=jiaweicui"

# 6. 测试会话跳转
# 点击Session列表中的会话条目 -> URL跳转
```

---

## 8. 实施阶段

| 阶段 | 内容 | 预估时间 |
|------|------|----------|
| 1 | 配置Schema + 认证模块（后端） | 1天 |
| 2 | Session Manager重构（后端） | 2天 |
| 3 | API层修改（后端） | 1天 |
| 4 | 访问控制 + 错误页面（前端） | 0.5天 |
| 5 | Session列表组件（前端） | 1.5天 |
| 6 | 迁移脚本 + 测试 | 1天 |