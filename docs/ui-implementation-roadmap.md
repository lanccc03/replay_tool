# next_replay UI 实现路线图

本文记录 `next_replay` 从当前 PySide6 工作台壳层走向完整工程 UI 的长期实现路线。它用于指导 UI 进度规划、阶段验收和后续工程代理接手，不替代 `docs/ui-style-guide.md` 的视觉规则，也不替代复杂功能所需的 ExecPlan。

当前基线：

- 已有 `replay-ui` 启动入口。
- 已有默认浅色工程主题、左侧导航、顶部状态条、右侧 Inspector 和主工作区壳层。
- Trace Library 与 Scenarios 页面已能只读列出当前 workspace 中的真实记录。
- Replay Monitor、Devices 和 Settings 仍是结构化占位。
- 完整运行控制、设备枚举、Scenario 可视化编辑、DBC / Signal Override、Diagnostics、DoIP、ZLG 和 BLF UI 工作流尚未完成。

## 1. 实现原则

UI 继续遵守 ports-and-adapters 架构：

- View 只负责控件、布局和用户输入收集。
- ViewModel 负责展示状态、选择状态、命令绑定、busy / error / status message。
- 业务判断放在 `ReplayApplication`、`domain`、`planning` 或后续 app 层会话 API。
- UI 不直接 import Tongxing / ZLG adapter。
- UI 不直接发送硬件帧。
- UI 不直接修改 `ReplayRuntime` 内部字段。
- 未实现能力必须禁用、隐藏或明确标记为未接入，不能画成可用功能。

UI 草稿状态和运行模型必须分开。Scenario 编辑草稿可以留在 `replay_ui_qt` 的 ViewModel / draft model 中；只有通过校验后才转换成 `ReplayScenario` 或 `ReplayPlan`。

## 2. 阶段状态表

状态定义：

- `Done`：已交付并有自动化或手工验证证据。
- `In Progress`：正在实现，交付边界尚未完整满足。
- `Next`：下一阶段优先启动。
- `Planned`：已规划但不应抢在前置能力之前实现。
- `Blocked`：依赖 core、adapter、硬件或外部能力先落地。

| 阶段 | 状态 | 目标 | 主要依赖 | 验收摘要 |
| --- | --- | --- | --- | --- |
| M0 UI 壳层基线 | `Done` | 可启动工作台壳层，读取 Trace / Scenario 列表 | PySide6、现有 app 层列表 API | `replay-ui` 可启动，offscreen smoke test 和 ViewModel 单测通过 |
| M1 UI 底座加固 | `In Progress` | 异步任务、统一错误和通用组件 | 当前 UI 壳层 | 长任务不冻结 UI，busy/error/confirm 模式统一 |
| M2 Trace Library 完整工作流 | `Planned` | UI 完成 trace 导入、查看、重建、删除 | M1、TraceStore app 用例 | 不用 CLI 也能完成 Trace Library 常用闭环 |
| M3 Scenario Editor 可视化编辑闭环 | `Planned` | UI 编辑 schema v2 scenario 和 routes | M1、ProjectStore、planner 校验 | 不手写 JSON 也能保存并 validate scenario |
| M4 Replay Monitor 运行会话闭环 | `Planned` | UI 编译、运行、暂停、恢复、停止和监控 snapshot | M1、app 层非阻塞 replay session API | Mock scenario 可从 UI 运行到完成 |
| M5 Devices 设备枚举与配置闭环 | `Planned` | UI 枚举设备、展示通道和配置参数 | M1、app 层设备枚举 API | fake/Mock 自动化通过；同星 UI 真机验证有手工记录 |
| M6 Signal Override UI | `Blocked` | DBC 绑定和 signal override 操作界面 | DBC、SignalDatabase port、override plan | core 能力落地后才启用 |
| M7 Diagnostics UI | `Blocked` | CAN ISO-TP / UDS / DoIP 诊断动作界面 | DiagnosticClient port、diagnostic timeline item | 诊断动作进入 ReplayPlan 并由 runtime 分发 |
| M8 产品化收尾 | `Planned` | 高 DPI、可访问性、深色主题、打包与手工验证 | M2-M5 至少形成工作流闭环 | UI 验证记录完整，可用于日常工程使用 |

## 3. Milestones

### M0：UI 壳层基线

状态：`Done`

已交付：

- `replay-ui [--workspace .replay_tool]` 启动入口。
- `src/replay_ui_qt` 包结构：`main.py`、`app_context.py`、`theme.py`、`main_window.py`、`views/`、`view_models/`、`widgets/`。
- 默认浅色工程主题。
- 左侧导航、顶部状态条、主工作区、右侧 Inspector。
- Trace Library 只读列表，调用 `ReplayApplication.list_traces()`。
- Scenarios 只读列表，调用 `ReplayApplication.list_scenarios()`。
- Replay Monitor、Devices、Settings 占位页。

验收证据：

- `tests/test_ui_view_models.py`
- `tests/test_ui_smoke.py`
- `uv run python -m unittest discover -s tests -v`
- `uv run replay-ui --help`

未完成边界：

- 未做真实窗口点击和高 DPI 手工验证。
- 未实现导入、删除、编辑、运行控制和设备枚举。

### M1：UI 底座加固

状态：`In Progress`

目标：

- 建立统一异步任务执行模式，避免 import / rebuild / validate / run 阻塞 Qt 主线程。
- 统一 busy、error、status message、确认对话框和危险操作反馈。
- 抽出可复用 table、toolbar、Inspector field、status badge、empty state 组件。
- 形成 ViewModel 命令测试模板。

主要交付：

- 后台任务 runner 或 worker 抽象。
- 可取消或至少可禁用重复触发的长任务状态。
- 统一错误显示策略：顶部短消息、Inspector / dialog 详细错误、可复制错误文本。
- 统一确认对话框：删除 trace、删除 scenario、停止运行等危险操作必须包含对象名或 ID。

第一批已交付：

- `TaskRunner`：基于 `QThreadPool + QRunnable` 的后台任务执行与重复任务名保护。
- `BaseViewModel` 公开命令生命周期方法：begin / complete / fail command。
- `StatusBadge`、危险操作确认 helper、可复制错误详情对话框。
- 对应任务框架、ViewModel 命令状态和 widget smoke 测试。

验收标准：

- 一个模拟长任务执行时，窗口仍能响应事件。
- ViewModel 单测覆盖成功、失败、重复触发禁用和错误清理。
- UI smoke test 覆盖至少一个 busy 状态和一个错误状态。

### M2：Trace Library 完整工作流

状态：`Planned`

目标：

- 在 UI 中完成 Trace Library 的常用闭环：Import ASC、Inspect、Rebuild Cache、Delete Trace、Refresh。

主要交付：

- Import ASC 文件选择与导入进度状态。
- Trace Inspector 展示 source summary、message ID summary、original path、library path、cache path、frame count、start/end time。
- Rebuild Cache 操作与结果反馈。
- Delete Trace 确认对话框与删除结果展示。
- Cache Ready / Cache Missing / Rebuilding / Unsupported 状态显示。

验收标准：

- 用户可通过 UI 导入 `examples/sample.asc` 并看到 trace 列表刷新。
- 用户可查看 source summary 和 message ID summary。
- 删除 trace 时有确认；删除后列表和 Inspector 状态同步。
- 对应操作仍通过 `ReplayApplication` 调用，不绕过 app 层。

### M3：Scenario Editor 可视化编辑闭环

状态：`Planned`

目标：

- 用户不手写 JSON，也能创建、编辑、保存和校验 schema v2 scenario。

主要交付：

- UI draft model，覆盖 traces、devices、sources、targets、routes、timeline。
- 路由映射表表达 `Trace Source -> Logical Channel -> Device Target`。
- source / target 选择使用下拉，不要求用户手输 ID。
- 支持加载保存的 scenario、保存新 scenario、validate、显示编译结果。
- JSON 查看、导入和导出作为高级能力，不作为主编辑入口。

验收标准：

- 从已导入 trace 和 mock device 创建 scenario，保存到 Scenario Store。
- 保存后的 scenario 可通过 `ReplayApplication.validate()` 编译。
- bus mismatch、重复 logical channel、缺失引用能定位到具体行或字段。
- 运行中禁止修改已编译 plan 的关键配置。

### M4：Replay Monitor 运行会话闭环

状态：`Planned`

目标：

- UI 支持非阻塞 replay session：compile、run、pause、resume、stop、snapshot polling 和错误日志。

主要依赖：

- app 层新增非阻塞 replay session API。
- UI 不直接持有或修改 runtime 内部字段。

主要交付：

- Replay session ViewModel。
- Run / Pause / Resume / Stop 控制。
- current timestamp、total duration、progress、sent frames、skipped frames、errors、completed loops。
- runtime error panel，可复制错误文本。
- 运行期间锁定关键 scenario、route、device 配置。

验收标准：

- Mock scenario 可从 UI 运行到完成。
- Pause / Resume 后进度继续，状态与 `ReplayRuntime.snapshot()` 一致。
- Stop 后设备关闭，最后一次 counters 保留。
- runtime 出错时 UI 显示 Failed / errors，不静默失败。

### M5：Devices 设备枚举与配置闭环

状态：`Planned`

目标：

- UI 支持设备参数编辑、枚举、通道状态展示，并明确硬件验证边界。

主要交付：

- driver、SDK root、application、device type、device index 参数输入。
- 设备枚举动作通过 app 层 API 调用。
- 设备信息、serial number、channel count、capabilities、health 状态表。
- 同星真机操作明确标注 Windows + TSMaster + 实际设备要求。

验收标准：

- fake / mock 路径可自动化测试。
- 同星真机 UI 点击验证必须按手工验证模板记录。
- UI 不直接 import `replay_tool.adapters.tongxing`。

### M6：Signal Override UI

状态：`Blocked`

阻塞原因：

- DBC 解析、`SignalDatabase` port、planner signal override plan、runtime payload patch 尚未实现。

目标：

- core 能力落地后，UI 支持绑定 DBC、选择 message / signal、编辑 override 值，并在运行前生成可验证 plan。

验收标准：

- 未绑定 DBC 时 UI 保持禁用或未接入状态。
- 绑定 DBC 后可选择信号并预览影响的 frame / payload。
- override plan 由 planner 生成，runtime 发送前 patch payload。

### M7：Diagnostics UI

状态：`Blocked`

阻塞原因：

- `DiagnosticClient` port、diagnostic timeline item、CAN_ISOTP / DOIP adapter 尚未实现。

目标：

- core 能力落地后，UI 支持 CAN ISO-TP / UDS 和 DoIP 诊断动作配置、执行和结果查看。

原则：

- DoIP 是诊断传输，不等于 ETH 原始帧回放。
- 诊断动作进入 `ReplayPlan` 后，由 runtime dispatcher 分发给 diagnostic port。

验收标准：

- 未实现 core 前，Diagnostics UI 不显示为可用功能。
- core 实现后，至少有 fake diagnostic client 自动化测试覆盖 UI ViewModel。

### M8：产品化收尾

状态：`Planned`

目标：

- 完成 UI 作为日常工程工具所需的可靠性、可读性和交付检查。

主要交付：

- Windows 高 DPI 100% / 125% / 150% 验证。
- 深色主题，需验证表格可读性和状态色对比度。
- 键盘焦点、tooltip、禁用状态、错误复制等可访问性检查。
- 文本不重叠、不截断关键含义的截图或手工验证记录。
- UI 启动、依赖、打包和故障排查说明。

验收标准：

- UI smoke test 和 ViewModel 单测稳定。
- 关键页面有手工截图或验证记录。
- 硬件相关 UI 明确区分 fake SDK、CLI 真机和 UI 真机点击验证。

## 4. 阶段推进规则

- 每次推进 UI 里程碑时，必须更新本文的阶段状态表。
- 阶段完成必须写清自动化测试、手工验证和未验证项。
- 涉及复杂功能、显著重构或高风险迁移时，按 `.agents/PLANS.md` 编写 ExecPlan。
- 新增或修改 UI 类时，必须维护类级 docstring。
- 新增或修改公共函数 / 方法时，必须维护 Google 风格 docstring。
- UI 文案、颜色、布局和状态表达必须遵守 `docs/ui-style-guide.md`。
- 架构边界变更必须同步 `docs/architecture-design-guide.md`。

## 5. 验证要求

UI 改动的最低验证随风险增加：

- 纯文档路线图变更：`git diff --check`。
- ViewModel 或 UI 数据映射变更：对应 ViewModel 单测。
- 主窗口、导航、主题或页面创建变更：offscreen UI smoke test。
- Trace / Scenario / Replay / Devices 工作流变更：对应 app 层用例测试 + UI ViewModel 测试。
- 硬件相关 UI 变更：fake SDK 自动化测试 + Windows 真机手工验证记录；未执行时必须在交付说明中明确。

常用命令：

```powershell
uv run ruff check src tests
$env:PYTHONPYCACHEPREFIX=(Join-Path $env:TEMP "next_replay_pycache_ui")
uv run python -m compileall src tests
uv run python -m unittest discover -s tests -v
uv run replay-ui --help
```

完整 UI 点击、高 DPI 和同星真机验证不能被 offscreen smoke test 替代。
