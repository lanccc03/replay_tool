# next_replay 架构与设计指导

本文是 `next_replay` 的工程指导文档，用来说明新回放工具的架构边界、设计原则、当前实现状态和后续演进顺序。它面向后续开发者和工程代理，目标是让实现工作始终围绕同一个产品架构推进，而不是回到旧项目里“控制器和引擎越堆越大”的形态。

## 1. 产品定位

`next_replay` 是一个全新的回放工具产品，不是对旧 `replay_platform` 的原地重构。旧项目可以作为能力参考和迁移来源，但新项目代码不应从 `src/replay_platform` import 任何模块。

新项目的核心目标是：

- 先做无界面的 headless 回放内核。
- 先把 Scenario 编译成不可变 ReplayPlan。
- Runtime 只负责执行计划，不在运行时临场解释场景含义。
- UI、同星、ZLG、DoIP、DBC、trace 导入都作为外层能力接入核心。
- 同星是首批硬件优先级，SDK 使用 `TSMaster/Windows/TSMasterApi`。

一句话：

```text
domain 定义“回放是什么”，planning 定义“这次怎么回放”，runtime 只负责“按计划执行”。
```

## 2. 当前目录与目标映射

当前项目采用 `src` layout，主包是 `replay_tool`。这和最初讨论中的多个顶层包是一一对应关系，只是落在一个主包下，便于 uv 管理和发布。

```text
next_replay/
├── pyproject.toml
├── uv.lock
├── README.md
├── docs/
│   └── architecture-design-guide.md
├── examples/
├── tests/
└── src/
    └── replay_tool/
        ├── domain/       # 领域模型
        ├── planning/     # Scenario -> ReplayPlan
        ├── runtime/      # 回放执行内核
        ├── ports/        # 外部能力接口
        ├── adapters/     # Mock / Tongxing 等接口实现
        ├── storage/      # trace 读取、未来 SQLite/cache/index
        ├── app/          # CLI/UI 调用的应用用例层
        └── cli.py        # headless 命令行入口
```

原始目标架构与当前实现的对应关系：

```text
replay_domain/      -> replay_tool/domain/
replay_plan/        -> replay_tool/planning/
replay_runtime/     -> replay_tool/runtime/
replay_ports/       -> replay_tool/ports/
replay_adapters/    -> replay_tool/adapters/
replay_storage/     -> replay_tool/storage/
replay_app/         -> replay_tool/app/
replay_cli/         -> replay_tool/cli.py
replay_ui_qt/       -> 暂未实现
```

## 3. 架构类型

`next_replay` 是一个模块化单体应用，内部采用 Ports and Adapters，也就是六边形架构。

核心依赖方向必须保持为：

```text
CLI / future Qt UI
    -> app
        -> planning + runtime + domain
            -> ports

adapters -> ports + domain
storage  -> ports + domain
```

禁止出现的依赖方向：

- `domain` 依赖 Qt、SQLite、TSMaster、ZLG 或 python-can。
- `runtime` 直接 import 同星/ZLG 具体 adapter。
- `planning` 直接调用硬件 SDK。
- UI 直接操作硬件 adapter 或直接拼装 runtime 内部状态。

如果需要接入外部世界，先定义 port，再写 adapter。

## 4. 分层职责

### 4.1 domain

位置：`src/replay_tool/domain/`

职责：

- 定义稳定领域对象。
- 表达回放工具里最基础的概念。
- 不依赖任何外部 SDK、文件系统、数据库或 UI。

当前核心对象：

- `BusType`
- `Frame`
- `ChannelConfig`
- `TraceConfig`
- `DeviceConfig`
- `ReplaySource`
- `ReplayTarget`
- `ReplayRoute`
- `TimelineConfig`
- `ReplayScenario`
- `ReplaySnapshot`

后续新增诊断、DBC、链路动作时，优先在 domain 层增加纯数据结构，但不要把解析、IO 或硬件调用放进 domain。

### 4.2 planning

位置：`src/replay_tool/planning/`

职责：

- 将用户写的 Scenario 编译成 Runtime 可直接执行的 ReplayPlan。
- 做引用检查、trace 映射、逻辑通道到物理通道映射。
- 未来负责能力匹配、降级策略、信号覆盖计划、诊断计划、链路动作计划。

原则：

- Scenario 是用户配置。
- ReplayPlan 是运行时配置。
- Runtime 只能执行 ReplayPlan，不应再解释 Scenario 原始字段。

未来 ReplayPlan 应包含：

- trace 事件流或 trace window reader。
- device start plan。
- logical channel -> physical endpoint route table。
- frame dispatch policy。
- signal override plan。
- diagnostic target plan。
- link action plan。
- startup sync policy。

### 4.3 runtime

位置：`src/replay_tool/runtime/`

职责：

- 执行 ReplayPlan。
- 管理 start、pause、resume、stop、loop。
- 按逻辑时间轴调度事件。
- 调用 BusDevice port 发送或读取帧。
- 维护 Runtime snapshot 和结构化日志。

当前实现的公开入口仍是 `ReplayRuntime`，但内部已经拆成多个可测试模块：

```text
runtime/
  kernel.py          # 生命周期
  scheduler.py       # 时间轴游标、批处理窗口、过期事件策略
  dispatcher.py      # frame / diagnostic / link 分发
  device_session.py  # 设备 open/start/stop/reconnect/close
  telemetry.py       # 状态快照、结构化日志、错误事件
```

继续扩展时要保证每个模块能单独测试。尤其是 pause/resume、loop、链路断开/恢复、过期帧策略，不能只能通过真硬件验证。

### 4.4 ports

位置：`src/replay_tool/ports/`

职责：

- 定义核心系统对外部能力的要求。
- 为硬件、trace、存储、诊断等外部能力提供接口。

当前已有：

- `BusDevice`
- `TraceReader`
- `DeviceRegistry`

后续应增加：

- `TraceStore`
- `TraceIndex`
- `DiagnosticClient`
- `SignalDatabase`
- `ProjectStore`

原则是核心层只知道 port，不知道 adapter 的具体类名。

### 4.5 adapters

位置：`src/replay_tool/adapters/`

职责：

- 实现 port。
- 隔离硬件 SDK、平台差异、DLL 加载、第三方库。

当前已有：

- `mock`
- `tongxing`

后续可增加：

- `zlg`
- `doip`
- `socketcan`
- `vector`

新增 adapter 时，优先补 contract tests。contract test 指同一组行为测试可以跑在 mock/fake adapter 上，用来保证所有 adapter 满足同一个 port 契约。

### 4.6 storage

位置：`src/replay_tool/storage/`

职责：

- 文件读取。
- trace 导入。
- SQLite 元数据。
- 标准化缓存。
- trace 索引。

当前已有 ASC reader 和 Trace Library v2 基线：

```text
storage/
  asc.py          # ASC 直读
  binary_cache.py # 标准化二进制 frame cache
  trace_store.py # SQLite 元数据 + 导入 / 查询 / 重建 / 删除
```

导入 trace 时：

- 复制原始文件。
- 生成标准化 `.frames.bin` 二进制 frame cache。
- 生成摘要给 CLI 和未来 UI 使用。

当前回放时：

- schema v2 可直接引用文件路径。
- schema v2 也可把 `traces[].path` 写成已导入 trace id，由 app 层解析到 cache。
- raw ASC 路径会先导入或复用 workspace 中的 `.frames.bin` cache。
- planner 只把 trace/source/route 编译成 planned frame source，不再把帧列表塞进 `ReplayPlan`。
- runtime 通过 cache-backed cursor 按 2 ms 窗口流式拉取下一批帧。
- Trace Store 已提供 source filter、时间窗口读取和轻量 block index；缺失 index 时可从 cache 重建。
- 目前仅支持 ASC；BLF 解析仍未实现。
- 第一版流式导入要求时间戳单调递增；乱序 ASC 的外部归并排序仍未实现。

### 4.7 app

位置：`src/replay_tool/app/`

职责：

- 编排应用用例。
- 为 CLI 和未来 Qt UI 提供稳定 API。
- 不包含 UI 控件逻辑。

当前已有：

- `load_scenario`
- `compile_plan`
- `validate`
- `run`
- `import_trace`
- `list_traces`
- `inspect_trace`
- `create_device`

未来 UI 只应调用 app 层，例如：

```python
app.import_trace(path)
app.validate_scenario(draft)
app.compile_replay_plan(scenario_id)
app.start_replay(plan_id)
app.pause_replay()
app.apply_signal_override(...)
```

### 4.8 CLI

位置：`src/replay_tool/cli.py`

职责：

- 提供 headless 调试入口。
- 优先保证自动化、硬件联调和回归测试好用。

当前命令：

```powershell
python -m replay_tool.cli validate examples/mock_canfd.json
python -m replay_tool.cli run examples/mock_canfd.json
python -m replay_tool.cli import examples/sample.asc
python -m replay_tool.cli traces
python -m replay_tool.cli inspect <trace-id>
python -m replay_tool.cli devices --driver tongxing
```

后续目标命令：

```powershell
replay-tool run scenario.json --driver mock
```

## 5. 数据流

当前 MVP 数据流：

```text
scenario JSON
    -> ReplayScenario.from_dict()
        -> ReplayPlanner.compile()
            -> app resolves raw ASC / imported trace id to managed cache
            -> planner emits planned frame sources
            -> ReplayPlan
                -> ReplayRuntime.configure()
                    -> timeline cursor opens managed cache streams
                    -> DeviceRegistry creates adapter
                    -> adapter.open/start_channel()
                    -> runtime dispatches each 2 ms frame batch
                    -> adapter.send()
```

目标数据流：

```text
trace import
    -> TraceStore
    -> binary cache + index + summaries

scenario
    -> schema v2 validation
    -> ReplayPlanner
    -> ReplayPlan

ReplayPlan
    -> RuntimeKernel
    -> Scheduler
    -> Dispatcher
    -> BusDevice / DiagnosticClient ports
    -> Telemetry snapshot and logs
```

## 6. Scenario 与 ReplayPlan

当前 Scenario 使用 JSON，`schema_version=2`。v2 不兼容旧 v1 文件；迁移是一次性更新仓库内 examples / tests / docs，不在运行时提供 v1 fallback。

当前最小形态：

```json
{
  "schema_version": 2,
  "name": "mock-canfd-demo",
  "traces": [{"id": "trace1", "path": "sample.asc"}],
  "devices": [{"id": "mock0", "driver": "mock"}],
  "sources": [{
    "id": "trace1-canfd0",
    "trace": "trace1",
    "channel": 0,
    "bus": "CANFD"
  }],
  "targets": [{
    "id": "mock0-canfd0",
    "device": "mock0",
    "physical_channel": 0,
    "bus": "CANFD"
  }],
  "routes": [{
    "logical_channel": 0,
    "source": "trace1-canfd0",
    "target": "mock0-canfd0"
  }],
  "timeline": {"loop": false}
}
```

v2 把 trace 资源、trace 来源、设备目标和路由拆开：

```yaml
schema_version: 2
name: demo replay

traces:
  - id: trace_1
    path: ./data/sample.asc

channels:
  - logical: can0
    source:
      trace: trace_1
      channel: 0
      bus: CANFD
    target:
      device: tx0
      physical_channel: 0

devices:
  - id: tx0
    driver: tongxing
    device_type: TC1014

sources:
  - id: trace_1_canfd0
    trace: trace_1
    channel: 0
    bus: CANFD

targets:
  - id: tx0_canfd0
    device: tx0
    physical_channel: 0
    bus: CANFD
    nominal_baud: 500000
    data_baud: 2000000

routes:
  - logical_channel: 0
    source: trace_1_canfd0
    target: tx0_canfd0

timeline:
  loop: false
```

演进要求：

- 保留 schema version。
- 当前不保留 v1 兼容入口。
- 后续如需重新支持历史文件，应单独增加 migration 模块。
- 后续校验错误要结构化，不要只抛字符串。
- UI 草稿格式与运行格式分开。
- Runtime 不直接读取 Scenario，只读取 ReplayPlan。

## 7. Tongxing / TSMaster 设计边界

同星 adapter 位置：

```text
src/replay_tool/adapters/tongxing/device.py
```

SDK 路径：

```text
TSMaster/Windows
```

实际 API 包：

```text
TSMaster/Windows/TSMasterApi
```

加载规则：

- 如果 `sdk_root` 指向 `TSMaster/Windows`，把该目录加入 `sys.path`。
- 如果 `sdk_root` 指向 `TSMaster/Windows/TSMasterApi`，把其父目录加入 `sys.path`。
- 使用 `importlib.import_module("TSMasterApi.TSMasterAPI")`。
- 不使用仓库根目录旧的 `TSMasterApi/`。

调用规则：

- 所有 DLL 调用通过 `TSMasterAPI.py` wrapper。
- wrapper 内部会 `byref`，adapter 调用 wrapper 时传 ctypes 对象本身。
- 结构体使用 `api.dll.TLIBCAN`、`api.dll.TLIBCANFD`、`api.dll.TLIBHWInfo`。
- 枚举优先从 `TSMasterApi.TSEnum` 私有 enum 类解析。
- 私有 enum 缺失时，使用同星 demo 中对应数值作为 fallback。

首批支持范围：

- CAN/CANFD 通道配置。
- 硬件枚举。
- 通道映射。
- 异步发送。
- FIFO 读取。
- 健康状态。
- project fallback。

暂不支持：

- CAN UDS。
- DoIP。
- TSMaster 在线回放配置。
- TSMaster 内置信号数据库读写。
- 原始以太网回放。

## 8. 诊断设计

诊断不要混进 BusType。

总线回放类型：

```text
CAN
CANFD
J1939
```

诊断传输类型：

```text
CAN_ISOTP
DOIP
```

DoIP 是诊断传输，不等于 ETH 原始帧回放。未来要支持原始以太网时，应单独设计 `EthernetFrameReplay` 或新的 bus frame 模型，不要把 DoIP 伪装成 ETH 回放。

建议新增：

```text
ports/diagnostic.py
adapters/diagnostics/can_isotp.py
adapters/diagnostics/doip.py
domain/diagnostics.py
```

诊断动作进入 ReplayPlan 后，由 runtime dispatcher 分发给 `DiagnosticClient` port。

## 9. UI 设计原则

UI 暂未实现。后续 PySide6 UI 应是工作台，不是业务中心。

建议结构：

```text
replay_ui_qt/
  main_window.py
  views/
    trace_library_view.py
    scenario_editor_view.py
    replay_monitor_view.py
    signal_override_view.py
    diagnostics_view.py
  view_models/
    trace_library_vm.py
    scenario_editor_vm.py
    replay_session_vm.py
```

原则：

- View 只负责控件。
- ViewModel 只负责展示状态和命令绑定。
- 业务判断放 app 或 domain/planning。
- UI 不直接 import Tongxing/ZLG adapter。
- UI 不直接拼硬件发送帧。
- UI 不直接修改 Runtime 内部字段。

## 10. 测试策略

测试目录：

```text
tests/
  test_scenario_and_planner.py
  test_runtime.py
  test_tongxing_adapter.py
```

当前验证命令：

```powershell
$env:PYTHONPATH = (Join-Path $PWD "src")
python -m unittest discover -s tests -v
python -m compileall src tests
```

uv 可用后：

```powershell
uv sync
uv run python -m unittest discover -s tests -v
uv run python -m compileall src tests
```

新增能力时的测试要求：

- domain/planning 变更必须有纯单元测试。
- runtime 时序变更必须使用 fake clock 测试。
- adapter 变更必须有 fake SDK 测试。
- trace cache/index 变更必须有 round-trip 测试。
- 同星真机能力必须额外写手工验证步骤，但不能用手工验证替代单测。

## 11. 推荐演进路线

### Milestone 1：同星真机闭环

目标：

- `replay-tool devices --driver tongxing` 能枚举真实设备。
- `replay-tool run examples/tongxing_tc1014_canfd.json` 能发送 CANFD。
- 明确记录 TC1014 的通道映射、波特率配置、FIFO 读取和关闭行为。

必须补：

- 真机验证文档。
- 错误码展示改进。
- 多通道同星 fake 测试。
- `project_path` fallback 手工验证。

### Milestone 2：Trace Library

目标：

- 不再只直接读 ASC 文件。
- 支持导入、列出、查看 trace。
- 使用 ASC 二进制 frame cache 支撑后续大 trace 工作。

建议命令：

```powershell
replay-tool import examples/sample.asc
replay-tool traces
replay-tool inspect <trace-id>
replay-tool rebuild-cache <trace-id>
replay-tool delete-trace <trace-id>
```

必须补：

- SQLite 元数据。（已具备第一版）
- 标准化 cache。（已具备 ASC `.frames.bin` 二进制 frame cache）
- source summary。（已具备第一版）
- message id summary。（已具备第一版）
- trace id 引用。（已具备第一版）
- source filter / 时间窗口读取。（已具备第一版）
- cache rebuild / trace delete。（已具备第一版）

### Milestone 3：Runtime 拆分

目标：

- 已从单个 `ReplayRuntime` 拆出 kernel、scheduler、dispatcher、device_session、telemetry；后续继续完善链路动作和诊断动作。
- 为批处理、链路动作、诊断动作打基础。

必须补：

- 2ms frame batch 策略。（已具备第一版）
- 按 adapter 分组发送。（已具备第一版）
- partial send 统计。（已具备第一版）
- link action 计划。
- runtime snapshot 增强。

### Milestone 4：信号覆盖

目标：

- 支持 DBC 绑定和信号覆盖。

必须补：

- `SignalDatabase` port。
- DBC adapter。
- planner 中生成 signal override plan。
- runtime 发送前 patch payload。
- CLI 临时覆盖参数。

### Milestone 5：诊断

目标：

- 支持 CAN ISO-TP / UDS 和 DoIP 诊断动作。

必须补：

- `DiagnosticClient` port。
- diagnostic timeline item。
- CAN_ISOTP adapter。
- DOIP adapter。
- DTC parser。

### Milestone 6：Qt 工作台

目标：

- 在 headless core 稳定后提供 PySide6 UI。

必须补：

- trace library view。
- scenario editor view。
- replay monitor view。
- signal override view。
- diagnostics view。

## 12. 交付边界

当前 `next_replay` 已经是目标架构的 MVP 子集，不是完整产品。

已经具备：

- headless CLI。
- domain / planning / runtime / ports / adapters / storage / app 分层。
- Mock 回放。
- 同星 adapter。
- ASC reader。
- Trace Library v2：流式导入、列出、查看、重建 cache、删除 trace，SQLite 元数据，ASC 二进制 frame cache，source/message summary，source filter / 时间窗口读取，轻量 block index，schema v2 trace id 引用。
- cache-backed 流式回放：`ReplayPlan` 保存 planned frame source，runtime 通过 cursor 按 2 ms batch 读取。
- fake TSMaster 单测。

尚未具备：

- 历史 schema migration（本轮明确不支持 v1 运行兼容）。
- 乱序 ASC 的外部排序。
- DBC / 信号覆盖。
- CAN UDS / DoIP / DTC。
- BLF 解析。
- ZLG。
- Qt UI。
- Windows 同星真机验证结论。

后续实现时，请优先保持架构边界清晰。不要为了快速补功能，让 runtime 直接认识硬件 SDK，也不要让 UI 直接操作 adapter。
