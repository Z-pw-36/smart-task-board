# Smart Task Board Backend

智能任务看板后端，用 FastAPI 和 PostgreSQL 实现任务创建、结构化拆解、参与人协作、状态流转、节点执行和完成验收的业务规则。

## 当前进度

已完成 Phase 0～5：

- Phase 0：工程、配置、健康检查、SQLAlchemy、Alembic、Pytest 和 Ruff。
- Phase 1：10张核心业务表的 ORM 和显式业务主键。
- Phase 2：首份 PostgreSQL 迁移及升级/降级验证。
- Phase 3：Repository 和 Unit of Work 事务边界。
- Phase 4：任务和节点状态机 Service。
- Phase 5：16个 REST API 业务路径，包括创建、查询、确认、发送、接受/退回、节点执行、完成提交和验收。

Phase 6 将加入仅限隔离演示环境的原型 JWT 身份、任务首页、统一待办和响应式前端。

## 技术栈

- Python 3.12（`>=3.12,<3.13`）
- FastAPI、Pydantic 2
- SQLAlchemy 2.x 同步 Engine/Session
- PostgreSQL 16、`psycopg[binary]`
- Alembic
- Pytest、Ruff
- Docker Compose

## 数据库与迁移

当前 Metadata 精确包含10张业务表：

```text
users
departments
task_inputs
ai_extraction_records
tasks
task_participants
task_nodes
task_node_participants
task_node_dependencies
task_status_logs
```

当前唯一 Alembic revision：

```text
17f69ea12754_initial_schema.py
```

PostgreSQL 数据通过 `./data/postgres:/var/lib/postgresql/data` 绑定到 D 盘项目目录，不使用默认命名卷。

## 核心流程

```text
创建任务草稿
→ 提交创建人确认
→ 确认并发送
→ 主承办人接受或退回
→ 节点开始、更新进度和完成
→ 主承办人提交完成
→ 验收人确认完成
```

每个状态动作都由 Service 校验权限、当前状态和 `task_version`，并在一个数据库事务中写入状态日志。

## 环境配置

`.env.example` 只是开发占位模板。运行时必须通过环境变量提供 `DATABASE_URL`，严禁把真实数据库密码、JWT 密钥或 API Key 写入代码、README 或 Git。`.env`、`.venv/` 和 `data/` 均已被 Git 忽略。

## 启动后端

```powershell
$ProjectRoot = "D:\SmartTaskBoard\backend"
$VenvPath = Join-Path $ProjectRoot ".venv"
Set-Location $ProjectRoot

$env:DATABASE_URL = "<set-in-your-local-environment>"
& (Join-Path $VenvPath "Scripts\python.exe") -m uvicorn app.main:app --reload
```

运行后：

- Swagger UI：`http://127.0.0.1:8000/docs`
- 存活检查：`GET /health/live`
- 数据库就绪检查：`GET /health/ready`

## 当前身份边界

Phase 5 API 暂时使用 `X-Employee-No` 请求头验证 Service 权限。它只是测试身份，不是正式认证，不能用于生产环境。Phase 6 原型将使用短期 JWT；公司正式环境仍需 SSO 或企业微信可信身份。

## 测试

默认质量门不连接 PostgreSQL：

```powershell
& (Join-Path $VenvPath "Scripts\python.exe") -m ruff check .
& (Join-Path $VenvPath "Scripts\python.exe") -m pytest
& (Join-Path $VenvPath "Scripts\python.exe") -m pip check
```

PostgreSQL Repository、Service 和 HTTP 测试默认安全跳过，只有显式提供隔离测试数据库配置和运行开关时才会执行。

已知警告：FastAPI/Starlette `TestClient` 当前会产生一条已知 `StarletteDeprecationWarning`，尚不影响测试结果。

## 有效需求文档

项目仅以 `docs/` 中以下两份文档为当前有效需求，不得修改或删除：

- `第二版-智能任务看板核心逻辑与用户使用流程节点(1).docx`
- `第四版-智能任务看板数据表结构文档-显式ID版(1).docx`

## 尚未完成

- 真实 AI/LLM 和多轮对话。
- 语音上传和 ASR。
- Web 前端。
- 汇报记录、负荷看板、绩效关联和归档复用。
- 企业微信正式身份和通知。
