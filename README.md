# Smart Task Board

智能任务看板使用 FastAPI、PostgreSQL 和 React 实现任务创建、结构化拆解、参与人协作、状态流转、节点执行和完成验收。后端业务规则通过 JSON REST API 提供，前端提供适配桌面和移动设备的基础任务看板界面。

## 当前进度

Phase 0～5 后端基础已经完成：

- Phase 0：工程、配置、健康检查、SQLAlchemy、Alembic、Pytest 和 Ruff。
- Phase 1：10张核心业务表的 ORM 和显式业务主键。
- Phase 2：首份 PostgreSQL 迁移及升级、降级验证。
- Phase 3：Repository 和 Unit of Work 事务边界。
- Phase 4：任务和节点状态机 Service。
- Phase 5：16条核心 REST API 业务路径，包括创建、查询、确认、发送、接受或退回、节点执行、完成提交和验收。

Batch 1 已经实现基础原型身份、任务列表、统一 Inbox、Dashboard 首页摘要、后端授权动作投影和 React 响应式前端，并已通过全部质量门。Batch 1 Git checkpoint 已经建立，`main` 分支及 Phase 0～5、Batch 1 两个基线标签均已上传至 GitHub 私有仓库。当前尚未进入 Batch 2；下一阶段是 Batch 2“任务进度汇报与卡点管理”的只读设计审查。

## 当前已实现能力

后端和 API：

- 原型用户列表、原型登录、短期 Bearer JWT 和 `GET /api/v1/me`。
- 创建任务草稿、创建人确认、确认发送、承办人接受或退回、创建人重新发送。
- 节点开始、进度更新和完成，任务提交完成及验收通过。
- 当前用户任务列表、任务详情、节点查询和状态日志查询。
- 统一 Inbox、Dashboard 首页摘要和由后端计算的 `allowed_actions`。
- 后端在业务 Service 中继续校验身份、权限、状态和 `task_version`；前端按钮不是权限边界。

React 前端：

- 原型登录页、Dashboard 首页、任务列表、Inbox、新建任务和任务详情。
- 创建任务节点及依赖关系，执行当前后端已支持的任务和节点动作。
- 桌面端和移动端响应式导航与布局。

## 技术栈

- Python 3.12（`>=3.12,<3.13`）
- FastAPI、Pydantic 2
- SQLAlchemy 2.x 同步 Engine/Session
- PostgreSQL 16、`psycopg[binary]`
- Alembic
- Pytest、Ruff
- React 19、TypeScript、Vite、TanStack Query
- Vitest、Testing Library、ESLint
- Docker Compose

## 数据库与迁移

当前 SQLAlchemy Metadata 精确包含10张业务表：

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

当前只有一份初始迁移，Alembic head 为 `17f69ea12754`：

```text
alembic/versions/17f69ea12754_initial_schema.py
```

不要手工创建或修改业务表，应通过 Alembic 管理结构变更。Docker Compose 中的 PostgreSQL 数据通过 `./data/postgres:/var/lib/postgresql/data` 绑定到项目目录，不使用默认命名卷。

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

每个状态动作都由 Service 校验权限、当前状态和 `task_version`，并在一个数据库事务中更新数据和写入状态日志。

## 环境配置

项目只正式支持 Python 3.12。`.env.example` 和 `web/.env.example` 只是开发占位模板，不能直接当作安全配置使用。

后端运行必须提供 `DATABASE_URL`。使用原型身份时还需要配置：

```text
AUTH_MODE=prototype
PROTOTYPE_AUTH_ENABLED=true
PROTOTYPE_USER_EMPLOYEE_NOS=<comma-separated-demo-employee-numbers>
JWT_SECRET_KEY=<locally-generated-secret-of-at-least-32-characters>
ALLOW_TEST_EMPLOYEE_HEADER=false
CORS_ALLOWED_ORIGINS=<frontend-origin>
```

Docker Compose 启动 PostgreSQL 时还需要在本地环境提供 `POSTGRES_DB`、`POSTGRES_USER` 和 `POSTGRES_PASSWORD`。不要把真实数据库密码、JWT 密钥、API Key、Token 或完整数据库连接 URL 写入代码、README 或 Git。`.env`、`.venv/`、`data/` 和前端本地环境文件均已被 Git 忽略。

## 启动后端

在项目根目录执行以下 Windows PowerShell 命令：

```powershell
py -3.12 -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -e ".[dev]"

# 先在当前进程或未提交的本地 .env 中安全提供所需环境变量
docker compose up -d postgres
& ".\.venv\Scripts\python.exe" -m alembic upgrade head
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --reload
```

使用通用 shell 时，可先激活项目内虚拟环境，再运行等价的 `python -m pip`、`python -m alembic` 和 `python -m uvicorn` 命令。

Uvicorn 未指定其他监听参数时，默认地址为 `http://127.0.0.1:8000`：

- 存活检查：`GET /health/live`
- 数据库就绪检查：`GET /health/ready`
- Swagger UI：`GET /docs`
- OpenAPI JSON：`GET /openapi.json`

## 原型身份边界

当前正常原型运行使用 HTTP Bearer JWT。客户端通过原型登录接口获得短期 Token，受保护接口使用：

```http
Authorization: Bearer <token>
```

`X-Employee-No` 只保留给既有测试兼容模式或明确隔离的测试场景，不能替代正式认证。原型 JWT 也不是生产级身份方案：目前没有完整的刷新、撤销和登出机制，没有正式 RBAC 或组织范围授权，也没有接入企业统一身份或企业微信认证。

不要在生产环境使用示例密钥或员工编号 Header。JWT 密钥必须由运行环境安全提供，不得提交 Git。

## 启动前端

前端位于 `web/`。`web/package.json` 当前提供 `dev`、`lint`、`test` 和 `build` 脚本：

```powershell
Set-Location web
npm.cmd ci

# 可通过未提交的 web/.env.local 设置 VITE_API_BASE_URL
npm.cmd run dev
npm.cmd run lint
npm.cmd run test -- --run
npm.cmd run build
```

`VITE_API_BASE_URL` 指向后端 API 根地址；未设置时，前端客户端默认使用 `http://localhost:8000`。如果 Windows PowerShell 执行策略阻止 `npm.ps1`，可直接使用 `npm.cmd`，不需要关闭系统安全策略。

## 原型登录使用流程

1. 准备并启动隔离的 PostgreSQL。
2. 通过 Alembic 将数据库迁移到当前 head。
3. 按下一节的安全要求检查并准备演示用户。
4. 配置原型身份环境变量并启动后端。
5. 配置 `VITE_API_BASE_URL` 并启动前端。
6. 在浏览器中打开 Vite 输出的本地开发地址。
7. 在登录页选择或输入允许的原型用户。
8. 前端通过原型登录获得 Bearer 身份。
9. 进入 Dashboard、任务列表、Inbox，并完成任务核心流程。

## Demo Seed安全说明

`scripts/seed_demo_data.py` 是显式启用、幂等的隔离演示数据工具。它只接受名称以 `_test` 或 `_demo` 结尾的数据库，并要求命令行确认值与当前配置中的数据库名完全一致。

先使用 dry-run 检查动作并回滚：

```powershell
& ".\.venv\Scripts\python.exe" -m scripts.seed_demo_data `
  --dry-run `
  --confirm-database-name "<isolated_test_or_demo_database_name>"
```

只有在再次核对目标后，才可以由用户明确选择持久化模式：

```powershell
& ".\.venv\Scripts\python.exe" -m scripts.seed_demo_data `
  --apply `
  --confirm-database-name "<isolated_test_or_demo_database_name>"
```

`--dry-run` 会回滚，不持久化数据；`--apply` 遇到已存在的演示员工编号时会跳过，不覆盖用户。禁止对未知、共享、开发或生产数据库运行该脚本，也不要打印或提交数据库凭据。本项目不会自动执行持久化 seed。

## 测试

默认后端质量门不连接 PostgreSQL；数据库集成测试会安全跳过：

```powershell
& ".\.venv\Scripts\python.exe" -m ruff check .
& ".\.venv\Scripts\python.exe" -m pytest
& ".\.venv\Scripts\python.exe" -m pip check
```

PostgreSQL Repository、Service 和 HTTP 集成测试只有在显式提供已批准的隔离测试数据库配置和运行开关时才会执行：

```powershell
$env:RUN_POSTGRESQL_INTEGRATION = "1"
$env:POSTGRES_TEST_DATABASE_URL = "<approved-isolated-postgresql-test-url>"
& ".\.venv\Scripts\python.exe" -m pytest tests/integration
```

前端质量门：

```powershell
Set-Location web
npm.cmd run lint
npm.cmd run test -- --run
npm.cmd run build
```

当前 Batch 1 最终验收基线为：后端 `202 passed, 18 skipped, 1 warning`，前端 `8 test files / 15 tests passed`。这是当前工作区的一次验证结果，不是永久固定的测试数量。唯一已知警告是 FastAPI/Starlette `TestClient` 的 `StarletteDeprecationWarning`。

## Git checkpoint状态

- Phase 0～5 基线：
  - commit：`9a228cdd624339b964d21cff92e3f2533efd8275`
  - tag：`phase-5-rest-api-baseline`
- Batch 1 稳定基线：
  - commit：`637106a172d5c10d54461b2a1f910fb5fee9d0df`
  - tag：`batch-1-task-board-baseline`
- 远程仓库：`https://github.com/Z-pw-36/smart-task-board.git`
- `main` 已同步到 `origin/main`，两个稳定基线标签均已上传至 GitHub 私有仓库。

## 后续计划

Batch 1 已经完成，Batch 2 尚未实施。Batch 2 拟实现任务进度汇报与卡点管理，但必须先完成只读设计审查；本次 README 状态同步不代表 Batch 2 已经开始。

## 当前未实现

- 正式生产登录认证、企业统一身份或企业微信认证。
- 完整 JWT 刷新、撤销和登出机制，以及正式 RBAC 和组织范围权限。
- 验收驳回、节点返工、节点重新打开和重试。
- AI 结构化提取、真实 AI/LLM、多轮对话、语音上传和 ASR。
- 企业微信机器人、通知和 Outbox。
- 附件及交付物文件管理。
- 进度汇报、负荷分析、逾期分析、冲突分析、优先级分析和绩效关联。
- 归档复用，以及 Batch 2 和后续任务看板功能。

## 有效需求文档

项目仅以 `docs/` 中以下两份文档为当前有效需求，不得修改或删除：

- `第二版-智能任务看板核心逻辑与用户使用流程节点(1).docx`
- `第四版-智能任务看板数据表结构文档-显式ID版(1).docx`
