# Smart Task Board

智能任务看板使用 FastAPI、PostgreSQL 和 React 实现任务创建、结构化拆解、参与人协作、状态流转、节点执行、完成验收与返工。后端业务规则通过 JSON REST API 提供，前端提供适配桌面和移动设备的任务看板界面。

## 当前进度

Phase 0～5 后端基础已经完成：

- Phase 0：工程、配置、健康检查、SQLAlchemy、Alembic、Pytest 和 Ruff。
- Phase 1：10张核心业务表的 ORM 和显式业务主键。
- Phase 2：首份 PostgreSQL 迁移及升级、降级验证。
- Phase 3：Repository 和 Unit of Work 事务边界。
- Phase 4：任务和节点状态机 Service。
- Phase 5：16条核心 REST API 业务路径，包括创建、查询、确认、发送、接受或退回、节点执行、完成提交和验收。

Batch 1 已经实现基础原型身份、任务列表、统一 Inbox、Dashboard 首页摘要、后端授权动作投影和 React 响应式前端，并已通过全部质量门。Batch 2A 已新增进度汇报和任务卡点模型及迁移，本地 checkpoint 为 `94108af17225ca9e4a2f728e47a117f1d546a0af`。Batch 2B 已完成进度汇报、问题闭环及真实 PostgreSQL 验收，本地 checkpoint 为 `7a0cf4e3c6b920d5fea10c351d4d7789f39baf90`。

Wave 1 的完成验收与返工现已实现并通过总质量门：每次提交形成不可变验收轮次；验收人按任务指定 reviewer 快照，未指定时回退创建人；支持通过、强制原因驳回、仅返工整体交付物、指定节点显式重开、多轮历史、API、Inbox、任务详情和响应式 UI。旧有 `pending_review` / `completed` 数据由迁移安全回填。本文档随 Wave 1 checkpoint 候选提交，checkpoint commit hash 尚未创建。

## 当前已实现能力

后端和 API：

- 原型用户列表、原型登录、短期 Bearer JWT 和 `GET /api/v1/me`。
- 创建任务草稿、创建人确认、确认发送、承办人接受或退回、创建人重新发送。
- 节点开始、进度更新和完成，主承办人提交不可变完成验收轮次。
- reviewer 快照授权、验收通过、填写原因驳回、整体交付物返工和指定节点显式重开。
- 多轮验收历史与旧数据安全回填；历史轮次不会被重新提交覆盖。
- 当前用户任务列表、任务详情、节点查询和状态日志查询。
- 统一 Inbox、Dashboard 首页摘要和由后端计算的 `allowed_actions`。
- 任务级和节点级不可变进度汇报、追加式汇报更正、周期待汇报查询。
- 卡点、资源需求、协同支持和风险上报，以及 `open → processing/resolved/rejected → closed` 生命周期。
- 活动 blocker 禁止完成对应节点；任何未关闭卡点禁止提交任务验收。
- 后端在业务 Service 中继续校验身份、权限、状态和 `task_version`；前端按钮不是权限边界。

React 前端：

- 原型登录页、Dashboard 首页、任务列表、Inbox、新建任务和任务详情。
- 创建任务节点及依赖关系，执行当前后端已支持的任务和节点动作。
- 任务详情中的进度汇报、汇报历史、更正入口、卡点创建和卡点处理。
- Inbox 待汇报入口，以及 Dashboard 待汇报和待处理卡点指标。
- Inbox 待我验收动作，以及任务详情中的完成提交、通过、驳回、节点重开和验收历史面板。
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

当前 SQLAlchemy Metadata 精确包含13张业务表：

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
task_progress_reports
task_issues
task_completion_reviews
```

当前有三份不可重写的迁移，Alembic head 为 `c31f8e7a4d02`：

```text
alembic/versions/17f69ea12754_initial_schema.py
alembic/versions/576787492bd1_add_progress_reports_and_task_issues.py
alembic/versions/c31f8e7a4d02_add_task_completion_reviews.py
```

不要手工创建或修改业务表，应通过 Alembic 管理结构变更。Docker Compose 中的 PostgreSQL 数据通过 `./data/postgres:/var/lib/postgresql/data` 绑定到项目目录，不使用默认命名卷。

Wave 1 downgrade 只允许在 `task_completion_reviews` 为空时执行；一旦存在验收历史，迁移会主动中止，避免静默删除不可变业务记录。需要回退有数据的环境时，必须先制定并验证独立的数据保全与恢复迁移。

## 核心流程

```text
创建任务草稿
→ 提交创建人确认
→ 确认并发送
→ 主承办人接受或退回
→ 节点开始、更新进度和完成
→ 进度汇报、卡点上报与闭环处理
→ 主承办人提交完成，生成新的不可变验收轮次
→ 本轮 reviewer 快照验收
   ├─ 通过：pending_review → completed
   └─ 驳回并填写原因：pending_review → in_progress
      ├─ 仅返工整体交付物，保留全部已完成节点
      └─ 指定节点后执行显式重开，保留原完成历史
→ 返工完成后重新提交，生成下一验收轮次
```

每个状态动作都由 Service 校验权限、当前状态和 `task_version`，并在一个数据库事务中更新数据和写入状态日志。只有主承办人可以提交完成；每轮验收人快照取任务指定 reviewer，未指定时才回退创建人，创建人、高管或管理员等身份本身不会自动获得验收权限。

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

当前 Wave 1 checkpoint 候选的完整质量门为：后端全量 `306 passed`，其中真实 PostgreSQL 16 集成测试 `20 passed`；前端 `10 test files / 28 tests passed`。Ruff、`pip check`、`pip-audit`、SQLAlchemy mapper、Alembic check 与 downgrade/upgrade、ESLint、TypeScript（随构建执行）和 Vite build 均已通过。OpenAPI 当前包含 `35` 条 API 路径、`38` 个 operations；测试后 PostgreSQL 业务数据残留为零。当前迁移 head 为 `c31f8e7a4d02`，Metadata 为13张业务表。

上述 Wave 1 门禁只证明完成验收与返工核心闭环。完成提醒与外部通知仍延期至 Wave 6，完成对绩效关联的影响延期至 Wave 4，负荷/看板统计重算延期至 Wave 5，完成后归档快照、检索与复用延期至 Wave 7。

## Git checkpoint状态

- Phase 0～5 基线：
  - commit：`9a228cdd624339b964d21cff92e3f2533efd8275`
  - tag：`phase-5-rest-api-baseline`
- Batch 1 稳定基线：
  - commit：`637106a172d5c10d54461b2a1f910fb5fee9d0df`
  - tag：`batch-1-task-board-baseline`
- Batch 2A 本地基线：
  - commit：`94108af17225ca9e4a2f728e47a117f1d546a0af`
  - push：待 GitHub 网络恢复
- Batch 2B 本地 checkpoint：
  - commit：`7a0cf4e3c6b920d5fea10c351d4d7789f39baf90`
- Wave 1 checkpoint 候选：
  - 完成验收与返工实现及总质量门已通过
  - commit hash：尚未创建；本文档随候选提交
- 远程仓库：`https://github.com/Z-pw-36/smart-task-board.git`
- 两个稳定基线标签均已上传至 GitHub 私有仓库且不得移动；本地 `main` 当前领先 `origin/main`。

## 后续计划

Batch 1、Batch 2A、Batch 2B 和 Wave 1 功能与验收均已完成。下一步是在安全复核后创建 Wave 1 本地 checkpoint，再进入 Wave 2：不可变任务变更申请，以及取消、撤回、合并、关闭和允许场景下的恢复。不会在 Wave 1 checkpoint 中虚报 Wave 4～7 的完成下游能力。

## 当前未实现

- 正式生产登录认证、企业统一身份或企业微信认证。
- 完整 JWT 刷新、撤销和登出机制，以及正式 RBAC 和组织范围权限。
- 任务变更申请，以及取消、撤回、合并、关闭和允许场景下的恢复。
- AI 结构化提取、真实 AI/LLM、多轮对话、语音上传和 ASR。
- 企业微信机器人、通知和 Outbox。
- 附件及交付物文件管理。
- 负荷分析、冲突分析、优先级分析和绩效关联。
- 完成提醒、完成后的绩效关联影响、负荷/看板统计重算、归档检索与复用，以及其他后续 Wave 功能。

## 有效需求文档

项目仅以 `docs/` 中以下两份文档为当前有效需求，不得修改或删除：

- `第二版-智能任务看板核心逻辑与用户使用流程节点(1).docx`
- `第四版-智能任务看板数据表结构文档-显式ID版(1).docx`
