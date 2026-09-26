# Coupling Life Clone

一个基于 FastAPI + LangGraph + LangChain 的本地优先 AI 工作台，包含对话、历史记录、回收站、长期记忆、知识库、文件上传、PPT 大纲、备忘录、公告和个人设置等功能。

## 技术结构

- ASGI 应用：`main.py`，导出 `main:app`
- 应用装配入口：`app.py`，只负责创建 FastAPI、挂载静态资源和注册路由
- 智能体编排：`backend/agents/runtime.py`，使用 LangGraph 组织上下文准备和请求路由
- HTTP 路由：`backend/routers/`
- 业务服务：`backend/services/`
- 数据库和运行时配置：`backend/core/`
- 静态前端：`static/`
- SQLite 数据库：`data/app.db`
- 上传文件：`data/uploads/`
- API 文档：`/docs`、`/redoc`
- 健康检查：`/health`

## 后端目录职责

```text
app.py                         # FastAPI 组装入口，不放业务逻辑
main.py                        # 部署入口，导出 main:app
backend/
  agents/
    runtime.py                 # LangGraph 状态图、LangChain 模型流式调用
  core/
    config.py                  # 路径和运行时配置
    db.py                      # SQLite 连接、表结构、生命周期
  routers/
    chat.py                    # /api/chat/*，只负责聊天请求和 SSE
    auth.py                    # /auth/*，登录、资料、API Key
    history.py                 # /api/history/*、/api/trash
    memory.py                  # /api/memory/*、/api/memories/*
    knowledge.py               # /api/knowledge/*
    settings.py                # 知识库和上下文开关
    productivity.py            # 备忘录、公告、PPT、演化、研究
    system.py                  # 健康检查、上传、STT/TTS、可视化
  services/
    agent_service.py           # 智能体运行时依赖注入
    storage.py                 # SQLite 持久化适配和文件保存
```

路由层只处理 HTTP 参数、状态码和响应格式；智能体流程放在 `agents/`，文件和 SQLite 持久化放在 `services/`，数据库初始化放在 `core/`。以后接入 PostgreSQL、Redis、真实 STT 或 DeepAgent 时，可以替换对应层，不需要改前端接口。

数据库会在 FastAPI 应用启动时通过 lifespan 自动初始化，不需要手动执行迁移脚本。

## 安装

```bash
python -m venv .venv
```

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

也可以使用项目元数据安装：

```bash
python -m pip install -e .
```

## 启动

开发环境：

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

生产或部署环境：

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

Windows 也可以直接运行：

```powershell
python main.py
```

打开 <http://127.0.0.1:8000> 使用前端，打开 <http://127.0.0.1:8000/docs> 查看 OpenAPI 文档。

## 环境变量

复制 `.env.example` 为 `.env` 并按需设置环境变量。项目启动时会自动读取项目根目录的 `.env`；也可以在 PowerShell 中直接设置：

```powershell
$env:OPENAI_API_KEY = "你的 API Key"
$env:OPENAI_MODEL = "gpt-4o-mini"
$env:TAVILY_API_KEY = "可选的 Tavily Key"
python main.py
```

未配置 `OPENAI_API_KEY` 时，聊天接口仍然可以离线运行，但会使用 LangGraph 的本地回复节点；配置后会使用 LangChain 的异步流式模型。配置 `TAVILY_API_KEY` 后，联网模式会启用 Tavily 检索。

### 对话数据存储到 PostgreSQL

默认情况下，对话数据仍然存储在本地 SQLite，便于 PyCharm 直接运行。如果要把普通对话相关数据存到 PostgreSQL，配置：

```env
CHAT_DATABASE_URL=postgresql://postgres:password@127.0.0.1:5432/green_leaves
```

配置后以下聊天数据会写入 PostgreSQL：

- `conversations`
- `messages`
- `/api/history`
- `/api/trash`
- `/api/chat/stream` 中的用户消息和 AI 回复
- LangGraph 读取最近对话上下文时使用的消息历史

长期记忆、知识库、系统设置等非对话表暂时仍使用 SQLite，以便分阶段迁移。应用启动时会自动在 PostgreSQL 中创建 `conversations` 和 `messages` 表及索引。

如果你已经在本地 SQLite 里有旧对话，配置好 `CHAT_DATABASE_URL` 后可以执行一次迁移：

```powershell
python scripts/migrate_chat_sqlite_to_pg.py
```

迁移脚本只复制 `conversations` 和 `messages`，不会删除 SQLite 原数据；重复执行会按消息 ID 和会话 ID 覆盖更新，避免重复插入。

### Docker 一键启动 PostgreSQL

项目已提供 `docker-compose.yml`，会同时启动应用和 PostgreSQL。应用容器内会自动连接数据库容器：

```env
CHAT_DATABASE_URL=postgresql://postgres:postgres@postgres:5432/green_leaves
```

启动：

```powershell
docker compose up -d --build
```

打开：

```text
http://127.0.0.1:8000/
```

查看运行状态：

```powershell
docker compose ps
docker compose logs -f app
```

停止：

```powershell
docker compose down
```

如果要连本机数据库工具，连接信息是：

```text
Host: 127.0.0.1
Port: 5433
Database: green_leaves
User: postgres
Password: postgres
```

PostgreSQL 数据会保存在 Docker volume `postgres_data` 中，应用上传文件和本地 SQLite 兜底数据会保存在 `app_data` 中。普通停止不会删除数据；如果你要彻底清空 Docker 数据，才使用 `docker compose down -v`。

## 智能体流程

1. `prepare_context`：读取当前会话、长期记忆和耦合知识库。
2. `route_request`：根据联网模式和问题是否具有时效性，选择知识库回答或联网研究路径。
3. `stream_answer`：使用 LangChain 模型异步流式输出；没有模型 Key 时使用本地可部署的离线回复。

当前没有使用 DeepAgent，因为这个复刻应用暂时没有多代理委派、长时间文件系统任务或需要自主规划的大型工作流。后续如果增加“研究任务后台执行、文件夹级资料处理、自动生成并反复修改 PPT”等长任务，再将其中的研究节点升级成 DeepAgent 更合适。

## 主要接口

| 模块 | 路径 |
| --- | --- |
| 健康检查 | `GET /health` |
| 对话流式回复 | `POST /api/chat/stream` |
| 对话历史 | `/api/history` |
| 长期记忆 | `/api/memories`、`/api/memory/settings` |
| 知识库 | `/api/knowledge/*` |
| 文件上传 | `/api/uploads/*` |
| 个人资料 | `/auth/profile` |
| 自动文档 | `/docs`、`/redoc` |

## 注意事项

- 当前版本使用 SQLite，适合单机或低并发部署。
- 生产环境建议配置反向代理、HTTPS、认证、限流和数据库备份。
- `data/` 包含运行时数据，不建议提交真实用户数据到代码仓库。
