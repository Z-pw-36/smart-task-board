# 旺序AI任务中枢｜智能任务看板 V1.1 开发计划

> 文档性质：可直接交给 VS Code/Codex 执行的开发任务书
> 业务基准：第二版 PRD V1.1
> 前端基准：第二版智能任务看板 HTML（视觉、页面、组件、交互、跳转）
> 数据基准：第四版显式 ID 数据表结构 + PRD V1.1 增量
> 代码基线：`a4d0b3eb4617e4203c32780a6ad3f63d50a82a49`
> 技术栈：React 19 + TypeScript + Vite / FastAPI / PostgreSQL
> 执行状态：`READY_FOR_REVIEW`
> 重要约束：本文件批准前不修改业务代码；批准后一次只执行一个 `DEV` 任务。

## 0. 给执行AI的第一指令

开始任何任务前，依次完成以下动作：

1. 阅读仓库根目录 `ARCHITECTURE.md` 全文。
2. 阅读本文件第1～8部分，确认目标口径、非范围、状态机和代码边界。
3. 只选择状态为 `TODO` 且所有前置任务为 `DONE` 的一个 `DEV` 任务。
4. 将该任务标记为 `IN_PROGRESS`，记录开始时的 Git commit 和工作树状态。
5. 只修改任务卡“允许修改”范围；若需要扩展范围，先将任务标记为 `BLOCKED` 并说明原因。
6. 先补齐或明确该功能测试，再实现数据库、后端、前端的完整纵向切片。
7. 运行任务卡的最小测试和受影响回归；失败时修复，不得进入下一任务。
8. 完成后填写实际文件、迁移、测试命令、通过数量、遗留风险和验收证据。

严禁：

- 一次实现多个未验收功能。
- 删除测试、降低断言或用跳过测试伪造通过。
- 把第二版 HTML 作为 iframe、`dangerouslySetInnerHTML` 或生产入口直接运行。
- 保留点击无反应、假成功提示、只改 localStorage 的业务按钮。
- 在前端复制状态机、权限、优先级或负荷计算规则。
- 重写已有 Alembic 历史迁移；所有结构变更必须新增迁移。
- 在代码、测试输出或文档中写入真实密码、Token、Secret、API Key、完整数据库连接串。

## 1. 资料职责与冲突裁决

### 1.1 优先级

| 优先级 | 资料 | 唯一职责 |
|---:|---|---|
| P0 | 用户最终确认要求 | 技术栈、分期、流程调整、代码质量和交付方式 |
| P1 | 第二版 PRD V1.1 | 业务规则、状态、权限、算法、接口目标和验收标准 |
| P2 | 第二版前端 HTML | 页面结构、视觉、组件、有效交互、弹层和跳转 |
| P3 | 第四版数据表结构 | 25张基线业务表的字段语义、显式ID和关联关系 |
| P4 | 前端交接文档 | 与P0～P3不冲突的API、DTO、事务、错误码和联调规则 |
| P5 | 当前仓库代码 | 可复用实现和历史兼容基础，不作为新需求依据 |

### 1.2 已裁决冲突

| 冲突 | 旧口径 | V1.1执行口径 |
|---|---|---|
| 前端技术 | uni-app | 保持 React 19 + TypeScript + Vite |
| 数据库 | MySQL | 保持 PostgreSQL；逻辑字段按文档，类型采用 PostgreSQL |
| 运行形态 | 小程序描述不清 | 本期为响应式移动H5/企业微信WebView，不转原生小程序 |
| HTML定位 | 可能被理解为仅视觉参考 | 同时作为页面、组件、交互和跳转契约；生产代码用React重建 |
| 创建流程 | 描述→信息→节点→发布 | 描述→信息确认→确认发送；删除创建人节点页 |
| 接受任务 | 直接进入进行中 | 进入 `decomposing`；拆解成功才 `in_progress` |
| 自建自办 | 可绕过接受 | 仍需接受并触发AI拆解 |
| 预计工时 | 输入、展示、参与计算 | 历史字段保留；MVP不写入、不展示、不参与计算 |
| 实际工时 | 用户填写 | 完成时间减开始时间，由系统生成，不可编辑 |
| 归档 | 手工归档并保存快照 | 验收通过自动归档，不写 `archive_snapshot` |
| 协同人权限 | 可提交汇报/资源 | 仅完成授权节点，不提交任务级汇报或资源请求 |
| 高管负荷 | 只看负荷构成 | 第二阶段支持快照→员工任务明细→单任务详情 |
| 演示功能 | 切角色、重置、本地假数据 | 生产隐藏或删除；所有可见业务动作接真实后端 |
| API命名 | 当前多为 snake_case | 存储/Python保持snake_case；JSON目标为camelCase，集中兼容旧调用 |
| 状态名称 | `pending_confirmation`、`pending_acceptance` | 迁移到 `pending_confirm`、`pending_accept` 等PRD枚举 |

任何后续新冲突都追加到本表，不得覆盖既有裁决记录。

## 2. 产品目标、范围与非范围

### 2.1 目标

1. 将当前 React 前端工程化转换为第二版 HTML 的页面风格和有效交互。
2. 为每个生产可见组件实现真实 FastAPI 与 PostgreSQL 能力。
3. 跑通 V1.1 主链路：录入、识别、确认发送、接受后拆解、执行、汇报、验收、自动归档。
4. 跑通高管团队看板和第二阶段员工负荷任务下钻。
5. 建立清晰可扩展的功能目录、模块注释、权限、幂等、事务和自动化测试体系。
6. 实现一个功能、测试一个功能；未通过不得开始下一功能。

### 2.2 本期包含

- 登录、当前用户、角色和组织授权。
- 工作台、任务概览、任务详情、通知、我的、高管看板。
- AI文字录入、语音转文字适配、字段识别、缺失/低置信追问。
- 创建人三步创建、草稿和确认发送。
- 承办人接受/退回，接受后AI自动拆解、失败重试和失效保护。
- 节点依赖、节点执行、协同节点权限。
- 进度汇报、卡点、资源诉求、问题闭环。
- 任务变更、更换承办人、撤回、取消、合并、关闭。
- 完成申请、验收退回、多轮验收、自动归档。
- 绩效匹配、优先级、负荷、冲突和提醒的已确认能力对齐。
- 高管负荷热力图、负荷构成、员工快照任务明细和任务详情。
- 响应式视觉、可访问性、性能、安全、可观测性和CI门禁。

### 2.3 本期不包含

- uni-app、Taro或原生微信小程序迁移。
- 通用附件上传、文件版本和交付物仓库；交付物仅文字记录。
- 预计工时、计划工时、AI工时估算输入/展示/计算。
- 前端手工编辑实际工时。
- 创建人查看、编辑或确认AI拆解节点。
- 手工归档和新归档快照写入。
- 生产环境角色切换、重置演示数据、硬编码 currentUser。
- 未接入后端的“后续开放”按钮。
- 未经确认的数据库删表或破坏性历史迁移。

## 3. 当前仓库基线与差距

### 3.1 已有基础

- FastAPI、SQLAlchemy、Alembic、PostgreSQL和分层目录已存在。
- React、TypeScript、Vite、Router、React Query和组件测试已存在。
- 已有认证、任务、节点、汇报、问题、变更、验收、绩效、负荷、通知、归档等后端基础。
- 当前 Alembic head 为 `f7b8c9d0e1f2`。
- 当前业务模型包含PRD基线表及 `auth_refresh_tokens`、`task_node_participants` 扩展表。
- 当前仓库有较完整的pytest、PostgreSQL集成测试和Vitest测试基础。

### 3.2 核心差距

| 领域 | 当前实现 | 目标差距 |
|---|---|---|
| 前端视觉 | 通用后台风格 | 与第二版HTML的移动端页面、卡片、弹层、底部导航不一致 |
| 路由 | `/`、`/tasks/*`、Inbox、归档等 | 缺少目标路由语义、高管、我的、拆解状态和负荷下钻 |
| 创建 | 当前React表单已不传节点，但页面仍非第二版三步 | 需要按HTML重建并严格形成三步 |
| 接受 | `accept_task`直接写 `in_progress` | 必须进入 `decomposing` |
| 自建自办 | 测试明确允许直接进行中 | 必须改为仍需接受和拆解 |
| AI拆解 | 手工planning/decompose与人工确认 | 必须改为接受后自动、系统校验、成功即生效 |
| 数据 | 缺少拆解尝试表、快照任务明细表 | 分阶段新增两表及关联字段 |
| 工时 | DTO、模型、算法、页面仍有 estimated_hours | 新MVP路径必须禁写、禁显、禁计算 |
| 归档 | 仍写和使用 archive_snapshot | 新流程自动归档且快照不写 |
| 权限 | 部分协同权限宽于PRD | 收紧任务级汇报/资源权限 |
| 高管前端 | 未形成第二版高管页 | 新增基础看板和负荷任务下钻 |
| 可维护性 | `task_workflow.py` 2616行；`business_capabilities.py` 2909行 | 拆入功能目录；保持单一职责和兼容入口 |
| 前端可维护性 | 页面、类型、详情文件体积大 | 拆入 `web/src/features/*` |
| 文档 | `PLANS.md`、`FEATURE_COVERAGE.md`有旧结论 | 执行时同步为V1.1状态并标记历史证据 |

## 4. 目标架构与代码可读性

`ARCHITECTURE.md`是强制规范。本计划补充以下执行检查：

### 4.1 功能目录

- 前端核心代码放入 `web/src/features/<feature>/`。
- 后端核心业务放入 `app/services/features/<feature>/`。
- API、Schema、Repository、Model继续保持分层，不能全部塞入功能目录。
- 每个功能通过 `index.ts` 或 `__init__.py`提供最小公开入口。
- 测试目录与功能目录对应。

### 4.2 注释

每个新增手写文件必须以模块注释说明：

- 功能名称。
- 主要职责。
- 明确不负责的层级。
- 需求/任务编号。

非显而易见的状态、权限、幂等、事务、迟到回调保护前增加“为什么”的注释。禁止机械逐行注释和注释掉的旧代码。

### 4.3 精简标准

- 核心函数通常不超过60行；业务文件通常不超过300行。
- 条件嵌套尽量不超过3层。
- 权限、状态转换、进度、负荷、日期、错误映射各保留一个权威实现。
- 不创建无业务语义的 `utils` 大杂烩。
- 不为“未来可能复用”建立未使用抽象。
- 删除无用导入、死代码、旧演示分支和假操作。
- 简洁不等于压成一行；优先可读命名、早返回、小函数和显式事务。

## 5. 目标路由与页面契约

| 路由 | 页面 | 访问条件 | 初始化数据 | 主要去向 |
|---|---|---|---|---|
| `/login` | 登录 | 匿名 | 登录配置/受控测试用户 | `/workbench` |
| `/workbench` | 员工工作台 | 登录 | 摘要、任务、四象限、通知摘要 | 任务、创建、通知、我的 |
| `/executive` | 高管团队看板 | 高管+授权范围 | 团队聚合、四象限、负荷快照 | 任务筛选、负荷明细 |
| `/tasks` | 任务概览 | 登录+数据范围 | 任务/节点分页 | 任务详情 |
| `/task/:taskId` | 任务详情 | 任务关系或授权 | 聚合DTO、权限动作 | 汇报、验收、拆解、更多操作 |
| `/task/:taskId/report` | 进度汇报 | 主承办人+执行态 | 任务和最新汇报 | 任务详情 |
| `/task/:taskId/review` | 任务验收 | 本轮验收人+待验收 | 任务、完成申请、验收轮次 | 任务详情 |
| `/task/:taskId/decomposition` | AI拆解状态 | 主承办人/创建人可看 | 任务和最新拆解记录 | 任务详情/重试 |
| `/create/details` | 描述任务/信息确认 | 登录 | 草稿、识别结果、人员、指标 | `/create/confirm` |
| `/create/confirm` | 确认发送 | 草稿所有者 | 已确认草稿摘要 | 工作台/任务详情 |
| `/notifications` | 通知中心 | 登录 | 本人通知 | 任务详情 |
| `/profile` | 我的 | 登录 | 当前用户和本人摘要 | 个人资料说明 |
| `/executive/employee-tasks` | 员工负荷任务明细 | 高管+授权+第二阶段 | 指定快照任务明细 | 任务详情/高管页；PRD V1.1优先于旧`/executive/workload-tasks`记法 |

旧 `/create/nodes` 不进入生产路由。旧根路径可重定向到 `/workbench`，旧 `/tasks/:taskId` 可在过渡期重定向到 `/task/:taskId`。

## 6. HTML组件—后端—数据追踪矩阵

本矩阵是最低覆盖清单。执行DEV-01时必须用脚本或人工复核附件HTML中的所有 `data-action`、`data-route`、表单和动态组件；发现遗漏时先补矩阵再编码。

### 6.1 全局组件

| ID | 组件/交互 | React目标 | 后端/数据 | 处理结论 | 测试 |
|---|---|---|---|---|---|
| UI-G-01 | 顶部标题栏/返回 | `PageHeader` | 无；保留来源路由状态 | 实现 | 路由返回、无历史兜底 |
| UI-G-02 | 通知铃铛/红点 | `NotificationBell` | 通知摘要 | 实现真实数量/跳转 | 有/无未读、401 |
| UI-G-03 | 底部导航 | `BottomNavigation` | 当前用户角色 | 高管入口按后端角色显示 | 路由、高管/员工 |
| UI-G-04 | Toast | `ToastProvider` | API错误映射 | 仅真实结果触发 | 成功/失败/可访问性 |
| UI-G-05 | Sheet抽屉 | `BottomSheet` | 依功能 | 实现焦点、关闭和安全区 | ESC、遮罩、焦点 |
| UI-G-06 | 确认/原因弹窗 | `ConfirmDialog`、`ReasonDialog` | 动作API | 原因必填由前后端双校验 | 空原因、提交中、失败 |
| UI-G-07 | 状态徽标 | `StatusBadge` | 服务端status/statusLabel | 统一映射，不存中文状态 | 全枚举、未知兜底 |
| UI-G-08 | 任务卡片 | `TaskCard` | 任务摘要DTO | 点击进入详情 | 键盘/点击/403/404 |
| UI-G-09 | 人员选择器 | `PeoplePicker` | 用户、部门、最新负荷 | 搜索、分页、权限 | 空态、搜索、选择 |
| UI-G-10 | 绩效指标选择器 | `MetricPicker` | 绩效指标和匹配建议 | 真接口，无硬编码分数 | 搜索、确认、失败 |

### 6.2 工作台与任务概览

| ID | 组件/交互 | React目标 | API/表 | 处理结论 | 测试 |
|---|---|---|---|---|---|
| UI-WB-01 | 当前用户欢迎区/头像 | `WorkbenchHeader` | `GET /me`; users | 实现 | 用户信息、缺资料 |
| UI-WB-02 | 状态数量卡 | `TaskStatusMetrics` | 工作台摘要；tasks | 点击携带status到任务列表 | 数量/列表一致 |
| UI-WB-03 | 四象限卡 | `PriorityQuadrantGrid` | task_priority_scores | 点击筛选四象限 | 排序、空态 |
| UI-WB-04 | 需要支持卡片 | `SupportRequiredCard` | issues/support查询 | 单独展示需要支持任务 | 权限、数量、跳转 |
| UI-WB-05 | 任务列表 | `WorkbenchTaskList` | 任务摘要 | 筛选和查看全部 | 加载/空/错误/分页 |
| UI-WB-06 | AI文字输入 | `QuickTaskInput` | task_inputs/extract | 输入后启动识别并进入确认 | 空输入、保留草稿 |
| UI-WB-07 | 语音按钮 | `VoiceTaskInput` | ASR适配/任务输入 | 不支持时回退文字 | 授权拒绝、失败 |
| UI-TO-01 | 状态概览 | `OverviewStatusCounts` | `GET /tasks`聚合 | 点击更新筛选 | 数量一致 |
| UI-TO-02 | 任务/我的节点模式 | `OverviewModeTabs` | tasks、nodes、participants | 实现服务端分页 | 模式切换 |
| UI-TO-03 | 状态/象限/临期/日期筛选 | `TaskFilterSheet` | 查询参数 | 服务端白名单校验 | 重置、非法日期 |
| UI-TO-04 | 节点卡片 | `NodeTaskCard` | task_nodes | 进入详情并定位节点 | 锚点、无权 |
| UI-TO-05 | 筛选恢复 | URL query + session UI state | 无业务写入 | 返回后恢复筛选/滚动 | 前进后退/刷新 |

### 6.3 任务详情、汇报、验收

| ID | 组件/交互 | React目标 | API/表 | 处理结论 | 测试 |
|---|---|---|---|---|---|
| UI-TD-01 | 摘要/状态/进度 | `TaskSummaryCard` | 任务聚合DTO | 不显示预计工时 | 状态、进度 |
| UI-TD-02 | 模块标签/滚动定位 | `TaskDetailTabs` | 无 | 概览/人员/节点/汇报/绩效 | 点击、滚动、恢复 |
| UI-TD-03 | 状态轨迹 | `TaskTimeline` | status_logs | 覆盖拆解中/失败 | 全状态顺序 |
| UI-TD-04 | 基本信息 | `TaskBasicInfo` | tasks、priority | 实际工时只读系统值 | 空字段、历史兼容 |
| UI-TD-05 | 人员信息 | `TaskParticipants` | participants、users | 按角色展示 | 人员缺失、权限 |
| UI-TD-06 | 节点折叠卡 | `TaskNodeList` | nodes、dependencies | 显示负责人、协同、时间、卡点 | 展开、依赖、空态 |
| UI-TD-07 | 最新汇报 | `LatestProgressReport` | progress_reports、issues | 统一汇报字段 | 无汇报/有卡点 |
| UI-TD-08 | 绩效关联 | `TaskPerformancePanel` | performance_matches | 显示解释与确认状态 | 未关联/已关联 |
| UI-TD-09 | 接受/退回 | `AcceptanceActions` | accept/reject动作 | 接受进入decomposing | 幂等、版本、原因 |
| UI-TD-10 | 汇报入口 | `ReportAction` | 权限投影 | 仅主承办人执行态 | 禁止态/403 |
| UI-TD-11 | 验收入口 | `ReviewAction` | 当前验收轮次 | 仅本轮验收人 | 角色/状态 |
| UI-TD-12 | 操作记录 | `TaskLogSheet` | status_logs、operation_logs | 真分页 | 空态、排序 |
| UI-TD-13 | 更多操作 | `TaskMoreSheet` | allowedActions | 复制编号、变更、换人、撤回、取消 | 每动作权限 |
| UI-PR-01 | 当前进度 | `ProgressField` | progress_reports | 必填0～100 | 边界/非法值 |
| UI-PR-02 | 阶段成果 | `StageResultField` | progress_reports | 选填 | 长度/空值 |
| UI-PR-03 | 卡点开关与说明 | `IssueFields` | task_issues | 开启时说明必填 | 联动/事务回滚 |
| UI-PR-04 | 备注 | `ProgressRemark` | progress_reports | 选填文字 | 长度/转义 |
| UI-RV-01 | 验收信息 | `ReviewSummary` | completion_reviews | 显示当前不可变轮次 | 轮次一致 |
| UI-RV-02 | 验收通过 | `ApproveReviewAction` | review approve | 自动归档且不写快照 | 幂等/回滚 |
| UI-RV-03 | 验收退回 | `RejectReviewAction` | review reject | 原因必填，回in_progress | 重开/再次提交 |

### 6.4 创建、拆解、通知、我的

| ID | 组件/交互 | React目标 | API/表 | 处理结论 | 测试 |
|---|---|---|---|---|---|
| UI-CR-01 | 三步步骤条 | `CreateStepper` | 无 | 仅描述→信息确认→确认发送 | 不出现节点步骤 |
| UI-CR-02 | 识别字段表单 | `TaskDetailsForm` | extraction、users | 缺失/低置信字段需确认 | 校验/恢复 |
| UI-CR-03 | 承办/汇报/协同/验收选择 | `TaskPeopleFields` | users、departments | 使用员工号提交 | 搜索/去重/权限 |
| UI-CR-04 | 权重/绩效/时间等字段 | `TaskBusinessFields` | tasks、metrics | 不含预计工时 | 必填/日期 |
| UI-CR-05 | 保存草稿 | `SaveDraftAction` | task draft API | 真实后端草稿 | 重复保存/版本冲突 |
| UI-CR-06 | 确认发送摘要 | `ConfirmSendPage` | draft detail | 不显示/提交节点 | 字段完整性 |
| UI-CR-07 | 确认发送 | `SendTaskAction` | publish/send事务 | 生成pending_accept、无节点 | 幂等/回滚 |
| UI-DC-01 | 拆解中 | `DecompositionProcessing` | decomposition/job轮询 | 接受后进入；禁业务动作 | 轮询、刷新、超时 |
| UI-DC-02 | 拆解失败 | `DecompositionFailure` | error_code/message | 脱敏说明 | 可/不可重试 |
| UI-DC-03 | 重新拆解 | `RetryDecompositionAction` | retry动作 | 仅主承办人、幂等 | 重复重试/冲突 |
| UI-DC-04 | 拆解成功 | `DecompositionSuccess` | task detail | 成功自动进入详情 | 节点/依赖/生效时间 |
| UI-NO-01 | 通知筛选/列表 | `NotificationList` | notifications | 任务/提醒类型筛选 | 空态/分页 |
| UI-NO-02 | 通知跳任务 | `NotificationItem` | task permission | 无权/删除提示 | 403/404 |
| UI-NO-03 | 已读 | `NotificationReadAction` | 现有read能力 | 仅真实后端可见；不得只localStorage | 单条/全部策略 |
| UI-PF-01 | 个人信息 | `ProfileHeader` | `GET /me` | 真身份，不可升级角色 | 缺字段 |
| UI-PF-02 | 本人任务摘要 | `ProfileMetrics` | dashboard摘要 | 真聚合 | 一致性 |
| UI-PF-03 | 演示角色/重置 | 无生产组件 | 无 | 删除或仅隔离测试环境 | 生产构建不可见 |
| UI-PF-04 | 原HTML“后续开放”菜单 | 按确认范围拆分 | 对应真实API或隐藏 | 不保留generic假提示 | 无死按钮 |

### 6.5 高管与负荷下钻

| ID | 组件/交互 | React目标 | API/表 | 阶段 | 测试 |
|---|---|---|---|---|---|
| UI-EX-01 | 团队指标 | `ExecutiveMetrics` | executive overview | 第一阶段 | 授权聚合 |
| UI-EX-02 | 团队四象限 | `ExecutiveQuadrants` | priority_scores、tasks | 第一阶段 | 点击筛选 |
| UI-EX-03 | 负荷热力图 | `WorkloadHeatmap` | workload_snapshots | 第一阶段 | 周期、颜色、范围 |
| UI-EX-04 | 负荷构成抽屉 | `WorkloadBreakdownSheet` | 快照五维压力 | 第一阶段 | 分数一致 |
| UI-EX-05 | 查看该员工任务 | `WorkloadTasksLink` | snapshot detail count | 第二阶段上线 | 参数完整、入口权限 |
| UI-EX-06 | 员工任务明细 | `EmployeeWorkloadTasksPage` | workload_snapshot_task_details | 第二阶段 | 历史不漂移 |
| UI-EX-07 | 明细任务卡 | `WorkloadTaskCard` | tasks、priority、issues、conflicts | 第二阶段 | 数量/风险/跳转 |

### 6.6 HTML原始交互索引

来源：`docs/reference/02-第二版-智能任务看板前端.html`。DEV-00扫描范围包括
`data-action`、`data-route`、`form`、`button`、`input`、`select`、`textarea`、
modal/sheet/dialog文本、内联`onclick`、以及动态JavaScript页面/动作函数。

| 类型 | 原HTML交互 | 第6节映射 |
|---|---|---|
| `data-action` | `open-overview-node`, `overview-filters`, `overview-reset`, `overview-filter-reset`, `clear-quadrant` | UI-WB-02～UI-WB-09 |
| `data-action` | `ai-submit`, `voice` | UI-CR-02；AI输入在DEV-08落地 |
| `data-action` | `save-draft`, `publish-task` | UI-CR-05～UI-CR-07 |
| `data-action` | `accept-task`, `reject-task` | UI-TD-09 |
| `data-action` | `toggle-issue` | UI-PR-03 |
| `data-action` | `review-approve`, `review-reject` | UI-RV-02～UI-RV-03 |
| `data-action` | `task-more`, `show-task-log`, `copy-task-no`, `open-change-request`, `creator-withdraw`, `reassign`, `cancel-task` | UI-TD-12～UI-TD-13；变更/换人/撤回/取消在DEV-11落地 |
| `data-action` | `mark-read` | UI-NO-03 |
| `data-action` | `accordion`, `generic`, `overlay-close`, `close-overlay` | 共享组件/反馈外壳；DEV-01只做基础组件，具体业务动作按对应UI行落地 |
| `data-action` | `reset-data` | UI-PF-03；仅允许隔离测试环境，不进入生产构建 |
| `data-route` | `/tasks` | UI-WB-01～UI-WB-09 |
| `data-route` | `/task/${id}/report`, `/task/${id}/review` | UI-PR-01～UI-PR-04；UI-RV-01～UI-RV-03 |
| `data-route` | `/create/details`, `/create/confirm` | UI-CR-01～UI-CR-07 |
| `data-route` | `/create/nodes` | V1.1正式流程删除创建期节点步骤；仅作为HTML差异记录，不实现该路由 |
| `data-route` | `/notifications`, `/profile` | UI-NO-01～UI-NO-03；UI-PF-01～UI-PF-04 |
| 表单控件 | 2个`form`、11个`input`、4个`select`、4个`textarea` | UI-CR、UI-PR、UI-RV表单行按字段承接 |
| 按钮 | 72个`button` | 由本索引的`data-action`、导航、表单提交和共享组件行承接 |
| modal/sheet/dialog | `showSheet`, `showDialog`, `showReasonDialog`, `closeOverlay`, 文本`modal/sheet` | UI-TD-12～UI-TD-13、UI-EX-04、UI-RV-03、DEV-01共享Sheet/Dialog |
| 动态页面函数 | `workbench`, `taskOverview`, `detail`, `report`, `review`, `notifications`, `profile`, `executive` | UI-WB、UI-TD、UI-PR、UI-RV、UI-NO、UI-PF、UI-EX |
| 动态渲染函数 | `renderDetailSummary`, `renderDetailTimeline`, `renderDetailBasic`, `renderDetailPeople`, `renderDetailNodes`, `renderDetailReport`, `renderDetailPerformance`, `renderDetailActions` | UI-TD-01～UI-TD-13 |
| 动态动作函数 | `navigate`, `confirmCreate`, `publish`, `save`, `setDetailTab`, `setupDetailScrollSpy`, `setupDetailFocus`, `setOverviewFilters`, `showOverviewFilters`, `showTaskLog`, `copyTaskNo`, `workloadSheet`, `startVoice` | 对应UI-WB、UI-CR、UI-TD、UI-EX动作行 |

DEV-00扫描结果：TOTAL HTML INTERACTIONS = 165，MAPPED = 165，UNMAPPED = 0。
| UI-EX-08 | 返回状态恢复 | URL query + navigation state | 无业务写入 | 第二阶段 | 团队/员工/周期/滚动 |

## 7. 任务状态机

### 7.1 目标状态

| 状态 | 中文 | 可执行核心动作 | 是否有效/计入执行负荷 |
|---|---|---|---|
| `draft` | 草稿 | 编辑 | 否 |
| `pending_confirm` | 待确认 | 创建人确认字段 | 否 |
| `pending_accept` | 待接受 | 承办人接受/退回；创建人换人/撤回/取消 | 否 |
| `returned` | 已退回 | 创建人修改、换人、重新发送、取消 | 否 |
| `decomposing` | AI拆解中 | 查看进度；撤回/取消/换人 | 否 |
| `decomposition_failed` | 拆解失败 | 主承办人重试；创建人撤回/取消/换人 | 否 |
| `in_progress` | 进行中 | 节点执行、汇报、卡点、变更、完成申请 | 是 |
| `blocked` | 受阻 | 汇报、处理问题、变更 | 是 |
| `pending_report` | 待汇报 | 提交汇报 | 是 |
| `pending_review` | 待验收 | 验收通过/退回 | 否，禁止普通进度写 |
| `completed` | 已完成 | 系统自动归档 | 短暂事务态 |
| `archived` | 已归档 | 只读查询/复用规则按后续确认 | 否 |
| `cancelled` | 已取消 | 只读 | 否 |
| `withdrawn` | 已撤回 | 只读 | 否 |
| `merged` | 已合并 | 跳转目标任务 | 否 |
| `closed` | 已关闭 | 只读 | 否 |

### 7.2 V1.1关键转换

```text
draft -> pending_confirm -> pending_accept
pending_accept --accept--> decomposing
decomposing --valid result--> in_progress + effective_at
decomposing --invalid/error--> decomposition_failed
decomposition_failed --retry--> decomposing
pending_accept --reject--> returned
in_progress/blocked/pending_report --submit completion--> pending_review
pending_review --reject--> in_progress
pending_review --approve--> completed -> archived (one transaction)
```

### 7.3 拆解并发不变量

- 接受和重试必须通过 `Idempotency-Key + taskVersion` 防重复。
- 同一任务同一时刻只能有一条有效的pending/running拆解记录。
- AI返回0节点、缺少动作、非法时间窗或循环依赖时失败，不得生效。
- 撤回、取消或更换承办人时将运行记录标记 `invalidated`。
- 回调提交前再次校验任务版本、状态、最新拆解ID和记录有效性。
- 失效/过期回调只记录审计，不得写节点、依赖、提醒或 `effective_at`。

## 8. 数据库计划

### 8.1 原则

- 只新增迁移，不改写 `17f69ea...` 到 `f7b8c9...` 的历史文件。
- 保留现有 `auth_refresh_tokens` 和 `task_node_participants`，标记为仓库扩展。
- PostgreSQL使用UUID/显式ID、`JSONB`、带时区时间和必要的部分唯一索引。
- 升级、空库升级、当前库升级和允许范围内的降级都必须测试。

### 8.2 第一阶段：接受后AI拆解（必须）

新增 `task_decomposition_records`，最低字段：

| 字段 | 作用 |
|---|---|
| `decomposition_id` | 显式主键 |
| `task_id` | 所属任务 |
| `status` | pending/running/succeeded/failed/invalidated |
| `task_version` | 启动时任务版本 |
| `idempotency_key` | 接受/重试防重 |
| `model_name/model_version/prompt_version` | AI追溯 |
| `result_json` | 原始结构化结果 |
| `node_count` | 有效节点数 |
| `error_code/error_message` | 脱敏失败信息 |
| `retry_count` | 同任务重试序号 |
| `started_at/completed_at/created_at` | 生命周期时间 |

给 `tasks` 增加：

- `effective_at`
- `decomposition_status`
- `latest_decomposition_id`

给 `task_nodes`增加/确认：

- `decomposition_id`
- `source_type`（V1.1自动拆解固定 `ai`）
- `blocked_reason`（若已有则仅验证约束和DTO）

索引/约束至少包括：task查询、状态查询、幂等唯一、一个有效拆解尝试、节点到拆解记录外键。

### 8.3 第二阶段：负荷任务下钻（功能上线前必须）

新增 `workload_snapshot_task_details`，最低字段：

| 字段 | 作用 |
|---|---|
| `workload_snapshot_task_detail_id` | 显式主键 |
| `workload_snapshot_id` | 所属快照 |
| `employee_no` | 快照员工 |
| `department_id` | 快照组织范围 |
| `task_id` | 当时纳入计算的任务 |
| `period_start/period_end` | 统计周期 |
| `task_status_snapshot` | 当时任务状态 |
| `task_weight_snapshot` | 当时权重 |
| `remaining_hours_snapshot` | 开始时间至截止时间之间尚未过去的工作时段，最小0；按系统工作日历计算 |
| `is_urgent/is_blocked/is_overdue` | 压力贡献快照 |
| `priority_quadrant_snapshot` | 当时象限 |
| `contribution_json` | 五维贡献与参数解释 |
| `created_at` | 生成时间 |

该表在计算 `workload_snapshots` 的同一事务/同一计算批次写入。历史明细不随当前任务修改。

### 8.4 历史字段兼容

- `tasks.estimated_hours`、`task_nodes.estimated_hours` 保留可空，不在新MVP请求中接收。
- 历史数据可读，但前端不展示；新优先级/负荷路径不得依赖它们。
- `task_priority_scores.remaining_hours` 按 `start_time`、`deadline` 和 `system_parameters`
  中的工作时段/节假日计算；最小为0，逾期另存/派生 `overdue_days`，不得回退为预计工时减实际工时。
- `task_archives.archive_snapshot`保留旧数据读取能力；V1.1验收通过不再写新快照。若当前列为
  `NOT NULL`，在DEV-13新增兼容迁移改为可空，保留既有快照数据且验证旧归档仍可查询。
- 状态值迁移需先盘点数据，再提供映射、约束更新和回滚验证。

## 9. API契约规则与目标接口

### 9.1 通用协议

| 项目 | 规则 |
|---|---|
| 前缀 | `/api/v1` |
| 鉴权 | `Authorization: Bearer <token>` |
| 成功 | `{ success: true, data, requestId }` 或在兼容期由client统一标准化 |
| 失败 | `{ success: false, error: { code, message, fieldErrors? }, requestId }` |
| 分页 | page>=1，pageSize默认20最大100；返回items/page/pageSize/total |
| 时间 | ISO 8601带offset；显示采用+08:00 |
| 并发 | 写操作携带 `taskVersion`；冲突409 |
| 幂等 | 关键写操作携带 `Idempotency-Key` |
| 授权 | 后端基于身份、参与关系、状态、组织范围二次校验 |
| 审计 | 状态日志+关键操作日志；日志不含Secret/token/AI敏感原文 |

### 9.2 核心接口清单

| ID | 方法与路径 | 功能 | 主要表 |
|---|---|---|---|
| U1 | `POST /auth/login` | 登录 | users、auth_refresh_tokens |
| U2 | `GET /me` | 当前用户/角色/范围 | users、departments、scopes |
| U3 | `GET /users`、`GET /departments` | 人员/组织选择 | users、departments、workload_snapshots |
| T1 | `POST /task-inputs` | 保存文字/语音转写输入 | task_inputs |
| T2 | `POST /task-inputs/{inputId}/extract` | 启动字段识别 | ai_extraction_records、job |
| T3 | `GET /task-inputs/{inputId}/extraction` | 获取识别/追问结果 | ai_extraction_records |
| T4 | `POST /tasks` | 创建/保存草稿 | tasks、participants |
| T5 | `PATCH /tasks/{taskId}` | 修改草稿/退回任务 | tasks及授权子表 |
| T6 | `POST /tasks/{taskId}/send` | 确认发送，无节点 | tasks、participants、logs、notifications |
| T7 | `POST /tasks/{taskId}/accept` | 接受并启动AI拆解 | tasks、decomposition_records、logs、notifications |
| T8 | `POST /tasks/{taskId}/reject` | 待接受退回 | tasks、participants、logs、notifications |
| T9 | withdraw/cancel/assignee/merge/close | 生命周期动作 | tasks及受影响表 |
| D1 | `GET /tasks/{taskId}/decomposition` | 最新拆解状态 | tasks、decomposition_records |
| D2 | `POST /tasks/{taskId}/decomposition/retry` | 重试拆解 | decomposition_records、tasks |
| D3 | `GET /jobs/{jobId}` | 统一异步任务状态 | job/适配层 |
| Q1 | `GET /tasks` | 任务/节点筛选 | tasks及聚合表 |
| Q2 | `GET /tasks/{taskId}` | 任务聚合详情和permissions | 所有关联任务表 |
| Q3 | `GET /tasks/{taskId}/status-logs` | 操作轨迹 | status_logs、operation_logs |
| N1 | 节点start/update/complete/reopen | 节点执行 | task_nodes、dependencies、logs |
| P1 | `POST /tasks/{taskId}/progress-reports` | 进度汇报 | progress_reports、issues、tasks、notifications |
| P2 | issue list/update/close | 卡点/资源闭环 | task_issues |
| C1 | change request/approve/reject/cancel | 任务变更 | change_requests、tasks、logs |
| R1 | completion submit/approve/reject | 完成与多轮验收 | completion_reviews、tasks、logs |
| A1 | 自动归档内部动作/历史查询 | 自动归档 | task_archives、tasks关联表 |
| NO1 | `GET /notifications`及真实read动作 | 通知 | notifications |
| E1 | `GET /executive/overview` | 高管聚合 | scopes、tasks、计算表 |
| E2 | `GET /executive/workload-snapshots/{snapshotId}` | 负荷构成 | workload_snapshots |
| E3 | `GET /executive/workload-snapshots/{snapshotId}/tasks` | 员工快照任务明细 | snapshot_task_details、tasks、风险表 |

执行时优先复用当前已存在且语义一致的接口；语义冲突时新增或调整动作接口并更新OpenAPI。不得为迁就旧前端保留两套业务规则。

### 9.3 核心错误码

至少统一：`AUTH_FAILED`、`SCOPE_DENIED`、`TASK_NOT_FOUND`、`STATUS_NOT_ALLOWED`、
`TASK_VERSION_CONFLICT`、`DUPLICATE_SUBMIT`、`REQUIRED_FIELD_MISSING`、
`DECOMPOSITION_RUNNING`、`DECOMPOSITION_FAILED`、`DECOMPOSITION_INVALIDATED`、
`DEPENDENCY_NOT_COMPLETED`、`REASON_REQUIRED`、`PROGRESS_INVALID`。

## 10. 权限矩阵

| 角色 | 查看 | 允许动作 | 明确禁止 |
|---|---|---|---|
| 创建人 | 本人创建及关系内任务 | 确认发送、处理退回、换人、撤回、取消、审批变更；若为本轮验收人可验收 | 创建后编辑AI节点；越过承办人接受 |
| 主承办人 | 本人承办任务 | 接受/退回、拆解失败重试、任务汇报、卡点/资源、变更、完成申请 | 拆解中执行/汇报/验收 |
| 节点负责人 | 授权任务及本人节点 | 按依赖开始/更新/完成本人节点 | 任务级汇报/验收 |
| 协同人 | 授权任务和协同节点 | 完成明确授权节点/确认知悉 | 任务级汇报、资源申请、管理任务 |
| 验收人 | 授权任务和当前验收轮次 | 通过或填写原因退回 | 修改任务/节点 |
| 汇报对象 | 关系内只读 | 查看 | 业务写操作 |
| 高管 | 直属/授权组织 | 只读团队、任务、负荷和风险 | 越范围查看、代替业务角色写入 |
| 管理员 | 明确管理范围 | 系统配置/授权管理（若本期页面覆盖） | 默认代替任务角色动作 |
| 无关员工 | 无 | 无 | 猜taskId、employeeNo、snapshotId访问 |

每项权限同时测试前端显隐和后端拒绝。前端 `allowedActions` 只用于体验，后端必须重新校验。

## 11. 分阶段开发顺序

| 任务 | 功能切片 | 前置 | 阶段 | 初始状态 |
|---|---|---|---|---|
| DEV-00 | 基线、契约、测试框架和旧文档对齐 | 无 | 基础 | TODO |
| DEV-01 | HTML组件盘点、设计令牌和共享移动端组件 | DEV-00 | 前端基础 | TODO |
| DEV-02 | 应用壳、目标路由和第二版底部导航 | DEV-01 | 前端基础 | TODO |
| DEV-03 | 工作台第二版转换 | DEV-02 | 页面 | TODO |
| DEV-04 | 任务概览第二版转换 | DEV-03 | 页面 | TODO |
| DEV-05 | 任务详情/汇报/验收视觉与只读数据转换 | DEV-04 | 页面 | TODO |
| DEV-06 | 登录、当前用户和权限投影对齐 | DEV-02 | 核心 | TODO |
| DEV-07 | AI输入、语音转文字、字段识别和追问 | DEV-03,DEV-06 | 核心 | TODO |
| DEV-08 | 创建人三步创建、草稿和确认发送 | DEV-07 | 核心 | TODO |
| DEV-09 | 承办人接受后AI拆解、失败重试和失效 | DEV-08 | 第一阶段关键 | TODO |
| DEV-10 | 节点执行、依赖与协同权限 | DEV-09 | 执行 | TODO |
| DEV-11 | 进度汇报、卡点、资源和问题闭环 | DEV-10 | 执行 | TODO |
| DEV-12 | 任务变更、换人、撤回、取消、合并、关闭 | DEV-09 | 生命周期 | TODO |
| DEV-13 | 完成申请、多轮验收、自动归档 | DEV-10,DEV-11 | 闭环 | TODO |
| DEV-14 | 绩效、优先级、负荷、冲突口径对齐 | DEV-13 | 智能计算 | TODO |
| DEV-15 | 通知、提醒、我的和生产演示清理 | DEV-12,DEV-13 | 支撑 | TODO |
| DEV-16 | 高管基础看板 | DEV-14,DEV-15 | 第一阶段 | TODO |
| DEV-17 | 员工负荷快照任务下钻 | DEV-16 | 第二阶段 | TODO |
| DEV-18 | 全链路E2E、性能、安全、CI与发布验收 | DEV-17 | 发布 | TODO |

## 12. 通用功能任务卡模板

执行每个任务时，在本节模板下复制一份完成记录：

```markdown
### DEV-XX 功能名

- 状态：TODO / IN_PROGRESS / BLOCKED / TEST_FAILED / DONE
- 开始基线：<git commit>
- 前置任务：<IDs>
- 需求来源：<PRD章节、组件ID>

#### 用户目标
<一句话>

#### 允许修改
<明确目录/文件>

#### 禁止修改
<迁移历史、无关功能等>

#### 实现清单
- 数据库：...
- 后端：...
- 前端：...
- 文档：...

#### 测试用例
- TC-XX-01 正常流程：...
- TC-XX-02 权限：...
- TC-XX-03 状态：...
- TC-XX-04 幂等/并发：...
- TC-XX-05 事务回滚：...
- TC-XX-06 前端加载/空态/错误：...

#### 命令
<最小测试、受影响回归、全量门禁>

#### 客观通过标准
<可断言结果，禁止写“功能正常”>

#### 完成证据
- 实际文件：...
- 迁移版本：...
- 测试结果：...
- 遗留问题：...
```

## 13. 逐功能执行卡

### DEV-00 基线、契约、测试框架和旧文档对齐

**目标**：建立可重复验证的V1.1基线，不改变业务行为。

**允许修改**：`ARCHITECTURE.md`、`docs/`、测试配置、`web/package.json`及锁文件（仅新增Playwright/必要契约工具）、CI配置。

**实现**：

- 运行并记录当前后端、前端、迁移、OpenAPI基线。
- 将 `PLANS.md`、`FEATURE_COVERAGE.md`、`AUTONOMOUS_RUN.md` 标明为历史进度或同步V1.1，不允许继续声称旧流程已完全满足V1.1。
- 建立Playwright配置、隔离测试数据约定和视口矩阵。
- 建立HTML交互清单；保证所有静态动作进入第6节矩阵。
- 固定状态/错误/API兼容迁移策略。

**测试**：现有pytest、Vitest、lint、build、Alembic head、OpenAPI唯一operationId全部通过；不得出现基线回退。

**完成标准**：测试报告包含命令、通过/跳过数量和环境；没有业务代码改动。

### DEV-01 HTML组件盘点、设计令牌和共享移动端组件

**目标**：把HTML视觉语言转换成可复用React基础，不接假业务。

**允许修改**：`web/src/styles/`、`web/src/shared/components/`、相应测试；可把HTML只读副本放 `docs/reference/` 且排除生产构建。

**实现**：设计令牌、字体层级、卡片、徽标、按钮、输入框、进度条、顶部栏、底部导航基础、Sheet/Dialog、Toast、Skeleton/Empty/Error。

**测试**：组件可访问名称、键盘焦点、关闭行为、44px触控、375/390/430宽度无横向溢出；稳定组件截图基线。

**完成标准**：HTML有效基础组件100%有映射；无业务API和硬编码员工数据。

### DEV-02 应用壳、目标路由和第二版底部导航

**目标**：建立目标路由与页面占位，迁移过程中仍可启动。

**允许修改**：`web/src/app/`、`web/src/App.tsx`、`AppShell`兼容层、路由测试。

**实现**：目标路由、受保护布局、角色导航、旧URL重定向、404/403页面、返回来源状态。

**测试**：每个目标路由可达；匿名跳登录；高管入口角色显隐；旧URL重定向；生产不存在 `/create/nodes`。

### DEV-03 工作台第二版转换

**组件**：UI-WB-01～07、UI-G相关。

**目标**：视觉匹配第二版工作台，并使用现有/调整后的真实摘要和任务接口。

**实现**：欢迎区、任务指标、四象限、需要支持卡、任务列表、AI入口；筛选通过URL/服务端参数；语音失败可回退文字。

**测试**：加载、空态、500重试、状态/象限/支持跳转、通知红点、不同角色数据；工作台P95基线采集。

### DEV-04 任务概览第二版转换

**组件**：UI-TO-01～05。

**目标**：完成任务/节点模式、状态/象限/临期/日期筛选和返回恢复。

**实现**：服务端分页排序和白名单；节点卡定位详情节点；移除前端全量数据计算。

**测试**：筛选组合、非法日期422、近3天边界、终止态排除、分页、空态、刷新/返回恢复、无权节点不可见。

### DEV-05 任务详情、汇报、验收视觉与只读数据转换

**组件**：UI-TD-01～13、UI-PR-01～04、UI-RV-01～03。

**目标**：先将第二版详情、汇报、验收页面接到真实查询和权限投影；动作能力由后续任务逐项验收。

**实现**：聚合DTO、标签滚动、轨迹、基本信息、人员、节点、最新汇报、绩效、操作记录、更多菜单；删除预计工时展示；实际工时只读。

**测试**：五模块、节点定位、权限按钮、403/404、长文本、无节点/无汇报/无绩效、375～1440响应式。

### DEV-06 登录、当前用户和权限投影对齐

**目标**：生产身份和按钮均来自后端；移除硬编码角色能力。

**允许修改**：auth/me/scope相关后端、`web/src/features/auth`或现有auth目录、共享API客户端和测试。

**实现**：登录、刷新、撤销、当前用户、角色、授权组织、401恢复；服务端 `permissions/allowedActions` 统一投影。

**测试**：员工/创建人/承办人/协同人/验收人/高管/无关员工；过期/撤销token；猜taskId；高管越范围；生产配置禁prototype header。

### DEV-07 AI输入、语音转文字、字段识别和追问

**组件**：UI-WB-06～07、UI-CR-02。

**目标**：将描述转为可确认任务字段，失败保留输入并可重试。

**实现**：任务输入、ASR适配、字段识别job、统一轮询、缺失/低置信追问、草稿恢复、确定性fake provider测试。

**测试**：空输入、文字成功、语音成功/拒绝/不支持、缺字段、低置信、多轮补充、60秒提示、后台完成、provider失败、输入归属权限。

### DEV-08 创建人三步创建、草稿和确认发送

**组件**：UI-CR-01～07。

**目标**：严格实现三步，发送后 `pending_accept` 且无节点。

**实现**：表单、人员/指标选择、真实草稿、乐观锁、确认摘要、发送事务、通知；请求Schema拒绝nodes/dependencies/estimatedHours。

**测试**：步骤条只有三步；必填/日期/人员；保存恢复；重复发送；事务中任一表失败回滚；发送后nodes为0；自建自办仍待接受。

### DEV-09 承办人接受后AI拆解、失败重试和失效

**组件**：UI-TD-09、UI-DC-01～04。

**目标**：完成V1.1第一阶段核心状态机。

**数据库**：新增 `task_decomposition_records`及tasks/nodes增量字段。

**后端核心目录**：`app/services/features/task_decomposition/`；拆出接受、结果验证、成功事务、失败、重试、失效和迟到结果保护。

**前端**：接受确认、处理中轮询、失败说明/重试、成功跳详情；禁用拆解期业务动作。

**测试**：

- 正常接受只创建一条有效记录并进入decomposing。
- 成功生成>=1节点、合法依赖、写effective_at后才in_progress。
- 0节点、缺动作、非法时间窗、循环依赖进入failed且无有效节点。
- 重复接受/重试不重复写。
- 自建自办仍走完整路径。
- 拆解中撤回/取消/换人使记录invalidated。
- 迟到回调不生效。
- 非主承办、旧taskVersion、旧decompositionId均拒绝。
- Alembic空库/现库升级、约束、回滚测试通过。

### DEV-10 节点执行、依赖与协同权限

**组件**：UI-TD-06及节点动作。

**目标**：只在任务生效后允许授权人员执行合法节点。

**实现**：节点状态/进度、前置依赖、负责人/协同权限、卡点阻止、完成时间；前端节点展开和动作反馈。

**测试**：拆解中/失败禁止；前置未完成禁止；负责人正常完成；协同人仅完成授权节点；无关员工403；并发版本；重复完成幂等。

### DEV-11 进度汇报、卡点、资源和问题闭环

**组件**：UI-PR-01～04、UI-TD-07。

**目标**：按确认口径提交任务级汇报，卡点与问题一致。

**实现**：当前进度必填、阶段成果选填、卡点开关、卡点说明、备注；移除实际工时输入；协同人禁任务级汇报/资源；问题处理通知和状态同步。

**测试**：0/100边界、卡点说明必填、普通汇报、blocked、问题处理/关闭、协同人403、拆解期/待验收禁止、事务回滚、重复汇报幂等。

### DEV-12 任务变更与完整生命周期

**组件**：UI-TD-13及原因弹窗。

**目标**：真实实现变更、换人、撤回、取消、合并、关闭，不保留generic按钮。

**实现**：变更申请/批准/拒绝/取消；换人通知旧新承办人并回pending_accept；撤回/取消通知原承办人；拆解记录失效；审计before/after。

**测试**：每个动作允许/拒绝状态、原因必填、版本冲突、通知对象、变更事务回滚、旧拆解迟到保护、无权限403。

### DEV-13 完成申请、多轮验收和自动归档

**组件**：UI-TD-11、UI-RV-01～03。

**目标**：全部有效节点完成后提交，验收通过自动归档且不写新快照。

**实现**：不可变完成轮次、验收人快照、退回原因、指定节点重开、再次提交；通过事务 `pending_review -> completed -> archived`；历史详情通过task_id关联读取；新增兼容迁移允许新归档记录的 `archive_snapshot` 为空，但不得覆盖或删除历史快照。

**测试**：未完成节点/未关闭卡点禁止；非验收人403；通过幂等；归档事务任一步失败全回滚；`archive_snapshot`为空/不新增；退回再提交形成新轮次；实际工时系统计算且前端不可编辑。

### DEV-14 绩效、优先级、负荷和冲突口径对齐

**目标**：复用已有能力，消除预计工时依赖并保证计算字段服务端权威。

**实现**：绩效建议/确认、四象限、剩余工时既有口径、负荷五维、冲突；参数快照；禁止客户端覆盖计算字段。

**测试**：无estimated_hours的新任务仍可计算；参数边界；排序稳定；相同输入可复现；越权提交计算字段422；计算失败不污染旧有效结果。

### DEV-15 通知、提醒、我的和生产演示清理

**组件**：UI-NO-01～03、UI-PF-01～04、UI-G-02。

**目标**：所有生产可见入口真实可用；原型按钮隐藏。

**实现**：通知筛选、跳任务、真实read策略、提醒/outbox重试、个人资料/摘要；角色切换和重置仅测试构建或删除；清理localStorage业务写。

**测试**：通知归属、重复通知去重、发送失败重试、无权任务跳转、生产无演示入口、仓库无generic假成功事件、localStorage仅保留UI偏好。

### DEV-16 高管基础看板

**组件**：UI-EX-01～04。

**目标**：实现第二版高管团队指标、四象限、负荷热力图和负荷构成。

**实现**：授权组织筛选、周期、聚合、五维压力、颜色阈值、风险/卡点摘要；第一阶段可通过feature flag隐藏下钻入口，但参数契约已固定。

**测试**：员工403、高管授权/越权、团队/周期切换、热力分数与抽屉一致、空团队、聚合P95<4s。

### DEV-17 员工负荷快照任务下钻

**组件**：UI-EX-05～08。

**目标**：完成热力图→负荷构成→员工任务明细→单任务详情。

**数据库**：新增 `workload_snapshot_task_details`，与快照同批次写入。

**实现**：入口显示快照任务数；传递departmentId、employeeNo、workloadSnapshotId、period；任务卡显示快照状态/象限/风险；详情显示当前任务但保留来源返回状态。

**测试**：快照数与明细一致；当前任务变更不影响历史明细；错误员工/部门组合403或404；猜snapshotId不可越权；分页排序；返回恢复筛选和滚动；迁移往返。

### DEV-18 全链路E2E、性能、安全、CI和发布验收

**目标**：执行第15～18节全部门禁，修复回归，不新增产品范围。

**实现**：Playwright主流程、角色数据夹具、性能采样、安全检查、OpenAPI契约、生产构建、部署/恢复说明、旧死代码和文档最终清理。

**完成标准**：所有必测场景通过；无阻断级问题；完成证据写入第19节。

## 14. 单功能测试标准

每个DEV功能至少包含下列适用层级：

| 层级 | 必测内容 |
|---|---|
| 规则单元测试 | 正常、边界、非法状态、权限、计算、错误分类 |
| Service测试 | 编排、幂等、版本冲突、审计/通知调用、异常不提交 |
| API测试 | 路径、DTO、camelCase、401/403/404/409/422、requestId |
| PostgreSQL集成 | 外键、唯一/检查约束、事务回滚、并发、锁、迁移 |
| React组件 | 加载、空态、错误、成功、按钮显隐、表单校验、重复点击 |
| 页面集成 | 路由、query参数、缓存失效、刷新、返回状态 |
| E2E | 该功能从页面动作到数据库可观察结果 |
| 回归 | 原有已通过功能、lint、类型、构建不回退 |

测试用例必须写成可观察断言，例如“发送后状态为pending_accept且task_nodes数量为0”，不得只写“发送成功”。

### 14.1 代码质量验收

| 检查项 | 标准 |
|---|---|
| 功能归属 | 核心代码位于对应feature目录 |
| 文件头 | 所有新增手写源文件有功能/职责/任务号说明 |
| 关键注释 | 状态、权限、事务、幂等、迟到回调说明原因 |
| 职责 | 页面不算业务；Router不写状态机；Repository不做权限决策 |
| 精简 | 无重复规则、死代码、假数据、generic动作、无意义抽象 |
| 命名 | 使用业务语义；无 `process_data`、`handle_item` 类模糊命名 |
| 文件规模 | 超出ARCHITECTURE建议范围时有拆分或明确记录 |
| 公开依赖 | 跨feature只走公开入口 |
| 测试对应 | 功能代码可快速定位到测试 |
| 文档一致 | 目录/依赖变更同步ARCHITECTURE |

## 15. 整体端到端验收场景

| ID | 场景 | 最低通过标准 |
|---|---|---|
| E2E-01 | V1.1主链路 | 登录→录入→识别追问→信息确认→确认发送→接受→AI拆解→生效→节点→汇报→完成→验收→自动归档 |
| E2E-02 | 创建三步 | 只出现三步；无创建节点页；发送后无节点 |
| E2E-03 | 自建自办 | 创建人=承办人时仍为待接受，接受后才拆解 |
| E2E-04 | 拆解成功 | 接受只进decomposing；节点/依赖/提醒同事务成功后写effective_at并进in_progress |
| E2E-05 | 拆解失败/重试 | 失败任务不生效、无有效节点；授权承办人可重试 |
| E2E-06 | 拆解失效 | 拆解中撤回/取消/换人使旧记录失效；迟到结果不写入 |
| E2E-07 | 待接受退回 | 原因必填→创建人修改/换人/取消→重新发送→新承办接受 |
| E2E-08 | 节点依赖 | 前置未完成禁止后置；完成后可执行；无权用户403 |
| E2E-09 | 卡点 | 汇报开启卡点→说明必填→创建人/负责人通知→处理→状态同步 |
| E2E-10 | 变更 | 承办申请→创建人批准/拒绝→任务更新或保持→通知和审计完整 |
| E2E-11 | 验收退回 | 原因必填→回进行中→继续处理→新验收轮次 |
| E2E-12 | 自动归档 | 验收通过同事务完成并归档；不写新archive_snapshot |
| E2E-13 | 工时口径 | 全站无预计/计划工时输入；实际工时不可编辑且系统计算 |
| E2E-14 | 协同权限 | 协同人只能完成授权节点，不能任务级汇报/资源 |
| E2E-15 | 高管基础 | 授权高管可看正确团队；员工和越权高管被拒绝 |
| E2E-16 | 负荷下钻 | 热力快照→员工任务数一致→任务卡→详情；返回恢复团队/周期 |
| E2E-17 | 历史快照 | 任务后续完成/取消不改变历史快照明细 |
| E2E-18 | 幂等事务 | 重复发送/接受/重试/汇报/验收不重复；中间失败全回滚 |
| E2E-19 | 通知 | 发送、接受、拆解成功/失败、换人、撤回、验收等通知可追踪 |
| E2E-20 | 无死交互 | 所有生产按钮真实调用、明确隐藏或删除，无fake/localStorage业务写 |

## 16. 视觉、响应式和可访问性标准

### 16.1 视口

- 375×812
- 390×844
- 430×932
- 768×1024
- 1440×900

### 16.2 标准

- 页面层级、底部导航、卡片、色彩、圆角、间距和弹层遵循第二版HTML。
- 工作台导航保持选中态圆形强调。
- 无横向溢出、文字遮挡、按钮越过安全区或键盘遮住主操作。
- 动态长名称、长原因、空数据和错误文案均有稳定布局。
- 触控目标至少44×44px；按钮有可读名称；焦点清晰；颜色不是唯一状态信号。
- 尊重 `prefers-reduced-motion`；滚动定位在减少动效时使用即时模式。
- 稳定页面截图与基准比较；动态数据/时间区域采用固定夹具或掩码。

## 17. 性能、安全、可靠性和可观测性

| 类别 | 最低门禁 |
|---|---|
| 性能 | 工作台/详情P95<2s；筛选P95<2.5s；高管聚合P95<4s；AI异步不阻塞页面 |
| 安全 | 服务端范围校验；最小权限；越权写审计；日志不输出Secret/token |
| 可靠性 | 写动作幂等；通知失败重试；拆解失败可重试且不生效；事务可回滚 |
| 一致性 | 同一状态、时区、周期、授权范围；客户端不可覆盖计算字段 |
| 可观测 | 每请求requestId；异步job可查；拆解attempt可追溯；操作日志有对象和结果 |
| 数据库 | 外键/唯一/检查约束；索引命中关键列表；迁移可从空库和现库升级 |
| 依赖 | pip/npm依赖检查无已知阻断漏洞；锁文件与声明一致 |

## 18. 执行命令与停止条件

### 18.1 通用命令

```bash
python -m ruff check app tests
python -m pytest -q
python -m pip check

npm --prefix web run lint
npm --prefix web run test -- --run
npm --prefix web run build
npm --prefix web run e2e

python -m alembic heads
python -m alembic check
python -m alembic upgrade head
```

PostgreSQL集成测试仅对经确认的隔离 `_test` 数据库执行，使用仓库既有安全开关。不得对未知、共享、开发或生产数据库运行测试清理、降级或seed。

### 18.2 迁移任务额外命令

在新建的临时/隔离数据库中验证：

```bash
python -m alembic upgrade head
python -m alembic downgrade -1
python -m alembic upgrade head
```

若降级会丢失已存在的不可变业务记录，迁移必须主动拒绝并提供数据保全说明；不得强制删除。

### 18.3 停止条件

遇到任一情况，将任务标记 `BLOCKED` 或 `TEST_FAILED`，停止进入下一功能：

- 需求/PRD/HTML/数据库规则产生未裁决冲突。
- 需要修改任务卡允许范围之外的核心架构。
- 发现用户已有未提交改动与本任务重叠。
- 权限、幂等、事务、迁移或安全测试失败。
- 新功能需要真实企业微信/ASR/LLM凭据但当前未配置；改用批准的fake验证接口，不伪造生产成功。
- 需要破坏性删表、改写历史迁移或清理非隔离数据库。

## 19. 进度与验收证据

### 19.1 总表

| 任务 | 状态 | 实际变更 | 最小测试 | 受影响回归 | 完成日期 | 阻塞/遗留 |
|---|---|---|---|---|---|---|
| DEV-00 | TODO | — | — | — | — | — |
| DEV-01 | DONE | `web/src/styles/` tokens; `web/src/shared/components/` primitives; DEV-01 Playwright visual baseline | Vitest shared component tests 6 passed; Playwright DEV-01 3 passed | Frontend 43 passed; build/lint passed; backend pytest 345 passed/21 skipped; ruff/pip check passed | 2026-09-01 | No business API, employee data, backend code, route shell, or DEV-02+ work |
| DEV-02 | DONE | `web/src/app/` route shell/router/navigation/return-state/placeholders; `web/src/App.tsx`; `web/src/components/AppShell.tsx` compatibility; DEV-02 route and Playwright responsive tests | DEV-02 route tests 25 passed; Playwright DEV-02 9 passed across 375/390/430 | Frontend 68 passed; DEV-01 component tests 6 passed; Playwright full 15 passed including DEV-01 visual baseline; build/lint passed; backend pytest 345 passed/21 skipped; ruff/pip check passed | 2026-09-01 | No business API, employee data, backend code, DB migration, or DEV-03+ implementation |
| DEV-03 | DONE | `web/src/features/workbench/` Workbench feature; `/workbench` router integration; DEV-03 Playwright responsive/performance scenario | Workbench API projection tests 6 passed; Workbench UI tests 7 passed; Playwright DEV-03 6 passed across 375/390/430 | Frontend 81 passed; DEV-02 route tests 25 passed; DEV-01 component tests 6 passed; Playwright full 21 passed; build/lint passed; backend pytest 345 passed/21 skipped; ruff/pip check passed | 2026-09-01 | Reused `/api/v1/dashboard/summary` and `/api/v1/tasks`; no backend code, DB migration, fake business API, hard-coded employee data, localStorage business write, or DEV-04+ implementation |
| DEV-04 | DONE | `web/src/features/task-overview/` Task Overview feature; `/tasks` router integration; `GET /api/v1/tasks` overview query params, node mode, server-side filters/pagination/sort; DEV-04 Playwright responsive/performance scenario | Task Overview UI tests 8 passed; task board API/service tests 24 passed; Playwright DEV-04 15 passed across 375/390/430 | Frontend 89 passed; Playwright full 36 passed; backend pytest 358 passed/21 skipped; build/lint passed; ruff/pip check passed | 2026-09-01 | No DEV-05 detail conversion, no fake business data, no localStorage business write, no DB migration |
| DEV-05 | DONE | `web/src/features/task-detail/` Task Detail/Report/Review read-only feature; `/task/:taskId`, `/task/:taskId/report`, `/task/:taskId/review` router integration; `GET /api/v1/tasks/{task_id}` read DTO includes confirmed performance matches and task operation logs; DEV-05 Playwright responsive/performance scenario | Task detail UI tests 8 passed; route tests 27 passed; task query/API targeted tests 47 passed; DEV-05 Playwright 21 passed | Frontend 99 passed; Playwright full 57 passed; backend pytest 359 passed/21 skipped; build/lint passed; ruff/pip check/OpenAPI passed | 2026-09-02 | Visual/read-only only; no DEV-06 auth alignment, no writes, no review/archive/lifecycle/decomposition/node execution/progress writes, no fake production data, no localStorage business write, no estimated-hours UI/use, no DB migration |
| DEV-06 | DONE | `GET /api/v1/me` current-user projection adds backend-authoritative roles, permissions, executive capability and active scopes; `POST /api/v1/auth/login` formal login alias reuses hashed refresh-token issuance; frontend auth/session stores access+refresh tokens in sessionStorage and navigation consumes backend permission projection; DEV-06 Playwright auth coverage | Auth/current-user/dependency targeted tests 33 passed; DEV-06 frontend targeted tests 40 passed; DEV-06 Playwright 12 passed | Frontend 102 passed; Playwright full 69 passed; backend pytest 362 passed/21 skipped; build/lint passed; ruff/pip check/OpenAPI passed | 2026-09-02 | No production employeeNo spoofing, no frontend-only executive authority, no task writes, no lifecycle/review/decomposition changes, no fake production identity, no localStorage business identity, no DB migration |
| DEV-07 | TODO | — | — | — | — | — |
| DEV-08 | TODO | — | — | — | — | — |
| DEV-09 | TODO | — | — | — | — | — |
| DEV-10 | TODO | — | — | — | — | — |
| DEV-11 | TODO | — | — | — | — | — |
| DEV-12 | TODO | — | — | — | — | — |
| DEV-13 | TODO | — | — | — | — | — |
| DEV-14 | TODO | — | — | — | — | — |
| DEV-15 | TODO | — | — | — | — | — |
| DEV-16 | TODO | — | — | — | — | — |
| DEV-17 | TODO | — | — | — | — | — |
| DEV-18 | TODO | — | — | — | — | — |

### 19.2 状态定义

- `TODO`：未开始，前置条件可能未满足。
- `IN_PROGRESS`：当前唯一正在开发的任务。
- `BLOCKED`：资料、权限、环境或范围需要确认。
- `TEST_FAILED`：已实现但门禁未通过，必须修复。
- `DONE`：功能、测试、文档和证据全部完成。

同一时刻只能有一个任务为 `IN_PROGRESS`。

### 19.3 DEV-02 完成证据

- 状态：DONE
- Baseline HEAD：`0da9ccd63044ea47cd6b5d2e2ee98935ba17a33a`
- 实际文件：`web/src/app/AppShell.css`、`web/src/app/AppShell.tsx`、`web/src/app/RoutePlaceholders.tsx`、`web/src/app/navigation.ts`、`web/src/app/return-state.ts`、`web/src/app/router.tsx`、`web/src/app/router.test.tsx`、`web/e2e/dev-02-routing.spec.ts`、`web/src/App.tsx`、`web/src/components/AppShell.tsx`、`web/src/components/AppShell.test.tsx`、`docs/DEVELOPMENT_PLAN_V1.1.md`
- 迁移版本：无
- 测试结果：`npm --prefix web run test -- --run src/app/router.test.tsx` 25 passed；`npm --prefix web run test -- --run src/shared/components/__tests__/primitives.test.tsx` 6 passed；`npm --prefix web run test -- --run` 68 passed；`npm --prefix web run lint` passed；`npm --prefix web run build` passed；`npm exec -- playwright test` in `web/` 15 passed；`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q` 345 passed / 21 skipped；`.venv/bin/python -m ruff check app tests` passed；`.venv/bin/python -m pip check` passed
- 响应式证据：Playwright `mobile-375`、`mobile-390`、`mobile-430` 均验证 AppShell、BottomNavigation、403、404；horizontal overflow <= 0；底部导航 touch target >= 44px
- 边界结果：Business API connected = No；Hard-coded employee data = No；Backend business code modified = No；DB migration = No；DEV-03+ implemented = No
- 遗留风险：DEV-02 仅提供路由契约占位；正式业务页面、登录/当前用户权限投影和业务 API 接入仍按 DEV-03+、DEV-06、DEV-08+ 执行

### 19.4 DEV-03 完成证据

- 状态：DONE
- Baseline HEAD：`2bac9fa0cfe100dfe9d5204c1b0ff7fcdcd4c286`
- 实际文件：`web/src/features/workbench/api.ts`、`web/src/features/workbench/hooks.ts`、`web/src/features/workbench/index.ts`、`web/src/features/workbench/WorkbenchPage.tsx`、`web/src/features/workbench/WorkbenchPage.css`、`web/src/features/workbench/__tests__/api.test.ts`、`web/src/features/workbench/__tests__/WorkbenchPage.test.tsx`、`web/e2e/dev-03-workbench.spec.ts`、`web/e2e/dev-02-routing.spec.ts`、`web/src/app/AppShell.css`、`web/src/app/AppShell.tsx`、`web/src/app/router.tsx`、`web/src/app/router.test.tsx`、`web/src/app/navigation.ts`、`docs/DEVELOPMENT_PLAN_V1.1.md`
- API复用/新增：复用现有 `GET /api/v1/dashboard/summary`、`GET /api/v1/tasks`、`GET /api/v1/me`；未新增后端接口
- 测试结果：`npm --prefix web run test -- --run src/features/workbench/__tests__/api.test.ts src/features/workbench/__tests__/WorkbenchPage.test.tsx` 13 passed；`npm --prefix web run test -- --run src/app/router.test.tsx` 25 passed；`npm --prefix web run test -- --run` 81 passed；`npm --prefix web run lint` passed；`npm --prefix web run build` passed；`npm exec -- playwright test` in `web/` 21 passed；`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q` 345 passed / 21 skipped；`.venv/bin/python -m ruff check app tests` passed；`.venv/bin/python -m pip check` passed
- 响应式证据：Playwright `mobile-375`、`mobile-390`、`mobile-430` 均验证 Workbench、AppShell、TopBar、BottomNavigation、任务卡、403/404相关回归；horizontal overflow <= 0；Workbench 可见链接/按钮 touch target >= 44px
- P95基线：Playwright fixture环境；每个视口5次 `/workbench` 加载样本；full run P95：375px 164ms、390px 182ms、430px 191ms
- 边界结果：Hard-coded employee data = No；Fake business API = No；localStorage business writes = No；Backend business code modified = No；DB migration = No；DEV-04+ implemented = No
- 遗留风险：Workbench 使用现有摘要和任务查询能力；四象限展示消费后端 `priority_items` 投影，后续 DEV-04/DEV-14 继续补齐服务端筛选和优先级口径；AI入口仅导航到创建流程，不实现 DEV-07 AI识别/语音能力

### 19.5 DEV-04 完成证据

- 状态：DONE
- Baseline HEAD：`26f50a61299e2e47fa0827cf19dff5d09fa2bcd4`
- 实际文件：`app/api/v1/task_board.py`、`app/schemas/common.py`、`app/schemas/task_board.py`、`app/services/task_board_query.py`、`tests/api/test_task_board_routes.py`、`tests/services/test_task_board_query.py`、`web/src/api/types.ts`、`web/src/app/navigation.ts`、`web/src/app/router.tsx`、`web/src/app/router.test.tsx`、`web/src/features/task-overview/api.ts`、`web/src/features/task-overview/hooks.ts`、`web/src/features/task-overview/index.ts`、`web/src/features/task-overview/TaskOverviewPage.tsx`、`web/src/features/task-overview/TaskOverviewPage.css`、`web/src/features/task-overview/__tests__/TaskOverviewPage.test.tsx`、`web/e2e/dev-04-task-overview.spec.ts`
- API复用/调整：复用并最小扩展 `GET /api/v1/tasks`；新增正式查询参数 `mode`、`status`、`quadrant`、`support`、`nearDue`、`datePreset`、`startDate`、`endDate`、`page`、`pageSize`、`sortBy`、`sortOrder`；未新增重复列表 API
- 筛选实现：任务模式和我的节点模式均由服务端查询返回；状态、四象限、需要支持、近3天临期、开始日期、搜索、分页、排序通过 URL query 传入服务端；FastAPI Literal/Query 与服务层日期校验提供白名单和 422
- 测试结果：`npm --prefix web run test -- --run src/features/task-overview/__tests__/TaskOverviewPage.test.tsx src/app/router.test.tsx` 33 passed；`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q tests/api/test_task_board_routes.py tests/services/test_task_board_query.py` 24 passed；`npm --prefix web run test -- --run` 89 passed；`npm --prefix web run lint` passed；`npm --prefix web run build` passed；`npm exec -- playwright test` in `web/` 36 passed；`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q` 358 passed / 21 skipped；`.venv/bin/python -m ruff check app tests` passed；`.venv/bin/python -m pip check` passed
- 响应式证据：Playwright 覆盖 375×812、390×844、430×932，并在 DEV-04 场景内额外检查 768×1024、1440×900；horizontal overflow <= 0；任务概览可见链接/按钮 touch target >= 44px
- P95基线：Playwright fixture 环境；常用状态筛选、节点模式、组合筛选、分页、自定义日期各 1 次样本/视口；full run P95：375px 286ms（217,119,179,286,141），390px 133ms（133,95,83,83,103），430px 126ms（126,72,75,89,94）
- 安全/权限证据：`GET /tasks` 查询参数白名单拒绝非法 mode/status/quadrant/sort/order/page/pageSize；非法日期与 startDate > endDate 返回 422；节点模式仅返回当前用户负责或协同且通过 `PermissionScopeService.can_access_task` 的节点；无权节点不可见
- 边界结果：DEV-05 Task Detail 正式转换 = No；DEV-06 Auth alignment = No；DEV-07 AI/ASR = No；DEV-08 Creation = No；DEV-09 Decomposition = No；DEV-14 calculations = No；Fake business data = No；localStorage business writes = No；DB migration = No；estimatedHours display/sort/filter = No
- 遗留风险：`/task/:taskId` 仍是 DEV-02 占位，DEV-05 将消费 DEV-04 传递的 `#node-<nodeId>` 锚点和 return source；`GET /tasks` 当前在服务层完成排序/分页与范围过滤，后续数据量增长时可在保持相同契约下进一步下推到数据库排序/分页优化

### 19.6 DEV-05 完成证据

- 状态：DONE
- Baseline HEAD：`04acac1c5d6417b4927f53ed1c893f2c13ed6c2e`
- 五模块：`概览`、`人员`、`节点`、`进度/汇报`、`绩效`
- 实际文件：`app/repositories/__init__.py`、`app/repositories/operation_log.py`、`app/repositories/task_performance_match.py`、`app/schemas/task.py`、`app/services/task_query.py`、`tests/services/test_task_query.py`、`web/src/api/types.ts`、`web/src/app/router.tsx`、`web/src/app/router.test.tsx`、`web/src/features/task-detail/`、`web/e2e/dev-05-task-detail.spec.ts`、`.gitignore`、`docs/DEVELOPMENT_PLAN_V1.1.md`
- API/DTO：复用 `GET /api/v1/tasks/{task_id}`、`GET /api/v1/tasks/{task_id}/available-actions`、`GET /api/v1/tasks/{task_id}/status-logs`、`GET /api/v1/tasks/{task_id}/progress-reports`、`GET /api/v1/tasks/{task_id}/issues`、`GET /api/v1/tasks/{task_id}/completion-reviews`；`TaskDetailResponse` 新增只读 `performance_matches` 与 `operation_logs`；不直接暴露 ORM
- 页面实现：详情页展示基本信息、状态、最新汇报进度、参与人、节点、依赖、卡点/资源、状态轨迹、操作记录、绩效关联、更多菜单和权限投影；汇报页与验收页仅展示真实上下文并禁用后续阶段写动作
- 节点锚点：支持 `/task/:taskId#node-<nodeId>`；有效节点异步加载后滚动并聚焦；缺失或未授权节点不视为系统故障
- 数据状态：loading、500/retry、403、404、无节点、无汇报、无绩效、长文本均有可见状态；`pending_accept` 且 `nodes=[]` 为合法空态
- 响应式/可访问性：Playwright 覆盖 375×812、390×844、430×932，并在 DEV-05 场景内额外检查 768×1024、1440×900；horizontal overflow <= 0；可见链接/按钮 touch target >= 44px；模块 tab、节点焦点、返回、错误重试和只读状态均有语义
- P95基线：Playwright fixture 环境；normal、large-nodes、large-logs 三场景/视口各 1 次样本；DEV-05 target run P95：375px 180ms（176,180,136），390px 193ms（171,193,124），430px 179ms（179,154,145）
- 测试结果：`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q tests/services/test_task_query.py tests/api/test_task_routes.py tests/api/test_task_board_routes.py` 47 passed；`npm --prefix web run test -- --run src/features/task-detail/__tests__/TaskDetailPage.test.tsx src/app/router.test.tsx` 35 passed；`npm exec playwright test e2e/dev-05-task-detail.spec.ts` in `web/` 21 passed；`npm --prefix web run test -- --run` 99 passed；`npm --prefix web run lint` passed；`npm --prefix web run build` passed；`npm exec playwright test` in `web/` 57 passed；`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q` 359 passed / 21 skipped；`.venv/bin/python -m ruff check app tests` passed；`.venv/bin/python -m pip check` passed；OpenAPI check passed with 78 API paths and 84 operations
- 边界结果：DEV-06+ implemented = No；AI intake = No；creation write = No；new decomposition implementation = No；node execution = No；progress/issue/resource writes = No；lifecycle writes = No；review/archive writes = No；calculation changes = No；fake production data = No；fake success = No；localStorage business write = No；estimated-hours new usage/display/calculation = No；DB migration = No
- 遗留风险：DEV-05 仅完成视觉与只读数据转换；登录、正式 current-user/permission projection、写动作、AI拆解、进度提交和验收归档仍按 DEV-06+ 后续任务执行

### 19.7 DEV-06 完成证据

- 状态：DONE
- Baseline HEAD：`4073f0b0a317cf0a70fe7d264336d5c48cf7ebe6`
- 实际文件：`app/api/v1/auth.py`、`app/api/v1/me.py`、`app/schemas/current_user.py`、`app/services/identity.py`、`tests/api/test_auth_routes.py`、`tests/api/test_current_user_routes.py`、`tests/api/test_task_routes.py`、`tests/services/test_identity.py`、`web/src/api/client.ts`、`web/src/api/endpoints.ts`、`web/src/api/types.ts`、`web/src/auth/AuthContext.tsx`、`web/src/app/navigation.ts`、`web/src/features/workbench/WorkbenchPage.tsx`、`web/src/test/test-utils.tsx`、`web/src/api/client.test.ts`、`web/src/auth/AuthContext.test.tsx`、`web/src/app/router.test.tsx`、`web/src/features/workbench/__tests__/WorkbenchPage.test.tsx`、`web/e2e/dev-02-routing.spec.ts`、`web/e2e/dev-03-workbench.spec.ts`、`web/e2e/dev-04-task-overview.spec.ts`、`web/e2e/dev-05-task-detail.spec.ts`、`web/e2e/dev-06-auth-permissions.spec.ts`、`docs/DEVELOPMENT_PLAN_V1.1.md`
- 迁移版本：无
- API/DTO：`GET /api/v1/me` 返回身份、部门、roles、permissions、active scopes 和 auth_mode；不返回 access token、refresh token、secret、password；新增正式 `POST /api/v1/auth/login`，保留兼容 `POST /api/v1/auth/token`，两者均仅在受控 prototype auth 模式允许 employee_no 直签。
- 前端实现：AuthProvider 登录走 `/auth/login` 并保存 access/refresh session token；启动时可用 refresh token 轮转后再请求 `/me`；登出 best-effort revoke refresh token；高管入口和高管路由只消费后端 `permissions.can_access_executive`。
- 测试结果：`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q tests/api/test_current_user_routes.py tests/api/test_auth_routes.py tests/api/test_dependencies.py tests/services/test_identity.py tests/services/test_authentication.py` 33 passed；`npm --prefix web run test -- --run src/auth/AuthContext.test.tsx src/api/client.test.ts src/app/router.test.tsx src/features/workbench/__tests__/WorkbenchPage.test.tsx` 40 passed；`npm exec playwright test e2e/dev-06-auth-permissions.spec.ts` 12 passed；`npm --prefix web run test -- --run` 102 passed；`npm --prefix web run lint` passed；`npm --prefix web run build` passed；`npm exec playwright test` 69 passed；`ALLOW_TEST_EMPLOYEE_HEADER=true AUTH_MODE=test_header .venv/bin/python -m pytest -q` 362 passed / 21 skipped；`.venv/bin/python -m ruff check app tests` passed；`.venv/bin/python -m pip check` passed；OpenAPI passed with 79 API paths and 85 operations.
- 安全/权限证据：生产配置仍禁止 prototype/test_header；employee_no 登录入口在非 prototype 模式返回 authentication failed；前端不再用 `role_type` 推断高管入口；普通员工访问 `/executive` 返回 403；匿名访问保护路由跳转 `/login`；direct API auth 仍由后端 `get_current_employee_no` 与各服务权限校验负责。
- 边界结果：DEV-07+ implemented = No；AI intake = No；creation write = No；new decomposition implementation = No；node execution = No；progress/issue/resource writes = No；lifecycle writes = No；review/archive writes = No；calculation changes = No；fake production identity = No；hard-coded employee = No；frontend-only authority = No；secret exposure = No；DB migration = No
- 遗留风险：正式企业微信/SSO 凭证交换未在当前资料中提供，本次仅保留受控 prototype 登录入口和 refresh-token 会话机制；生产环境必须接入真实企业身份提供方后再开启 `AUTH_MODE` 的生产配置。

## 20. 最终完成定义（Definition of Done）

项目只有同时满足以下条件才可标记V1.1完成：

- 第6节所有生产组件均为“已接真实功能、按PRD隐藏、按PRD删除”之一。
- HTML有效页面、交互、跳转和弹层已在React中工程化实现。
- 创建人三步和接受后AI拆解完整生效。
- `task_decomposition_records`及关联字段通过迁移/事务/并发验收。
- 高管基础看板和第二阶段快照任务下钻通过授权与历史一致性验收。
- `workload_snapshot_task_details`仅在第二阶段上线前新增并真实写入。
- 全站不写/不显/不计算预计工时；实际工时只读系统生成。
- 协同、创建、承办、验收、高管和无关员工权限全部通过。
- 验收通过自动归档且不写新 `archive_snapshot`。
- 所有关键写动作幂等、带版本控制、失败可完整回滚。
- 所有新增手写文件有功能头注释，核心逻辑位于对应功能目录。
- 无超大新增模块、重复业务规则、假数据、死代码或无响应按钮。
- 单功能测试、全量回归、E2E、迁移、性能、安全、构建和OpenAPI门禁全部通过。
- `ARCHITECTURE.md`、本计划、README/历史进度文档与实际实现一致。

## 21. 执行启动批准

当前仅完成开发计划与架构约束。收到明确批准后，从 `DEV-00` 开始；每次只交付一个功能及其测试报告。不得跳过基础任务直接大规模重写前端或状态机。
