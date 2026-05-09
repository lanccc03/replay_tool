# next_replay UI 风格指导

本文定义 PySide6 UI 的视觉风格、色彩、布局和组件使用规则。当前项目已有 `replay_ui_qt` 工作台、Trace Library 完整工作流和 Scenario 只读 draft preview；本指南继续约束后续页面设计，不表示完整 Qt 工作台已经完成。阶段状态以 `docs/ui-implementation-roadmap.md` 为准。

## 1. 设计定位

`next_replay` 的 UI 应是克制的工程工作台，而不是营销页面、炫技中控屏或单纯的 CLI 包装器。

核心气质：

- 精密：用户能快速判断 trace、scenario、设备和 runtime 的真实状态。
- 可靠：危险操作清楚、错误可定位、状态不暧昧。
- 安静：长时间查看表格、时间戳、报文 ID 和路径时不疲劳。
- 可扫描：信息密度高，但分组、对齐和层级必须清楚。

第一版 UI 优先服务这些工作流：

- 已完成：导入、查看、重建和删除 Trace Library 记录。
- 正在推进：以可视化方式查看并后续编辑 schema v2 scenario 的 trace、device、source、target 和 route。
- 后续闭环：编译、运行、暂停、恢复、停止回放并查看运行快照。

DBC / 信号覆盖、诊断、DoIP、ZLG 和 BLF 等未实现能力不得设计成可用状态。可以预留导航结构，但必须以禁用或未接入状态呈现。

## 2. 布局结构

推荐使用四区工作台结构：

```text
┌──────────────────────────────────────────────────────────────┐
│ Top Status Bar: workspace / device / scenario / runtime state │
├──────────────┬────────────────────────────────┬──────────────┤
│ Navigation   │ Main Workspace                 │ Inspector    │
│              │ table / route map / monitor    │ properties   │
└──────────────┴────────────────────────────────┴──────────────┘
```

布局规则：

- 左侧导航用于一级模块：Trace Library、Scenarios、Replay Monitor、Devices。
- 顶部状态条显示当前 workspace、当前 scenario、设备连接状态和 runtime 状态。
- 主工作区优先使用表格、分栏、路由映射和时间轴，不做大面积欢迎页。
- 右侧 Inspector 显示当前选中对象的属性、校验结果和可编辑字段。
- 不使用落地页、hero 区、装饰插画或营销式卡片布局。
- 不把页面区块做成层层嵌套的卡片；卡片只用于列表项、弹窗、小型摘要和独立工具块。

## 3. 颜色系统

默认主题使用浅色工程主题。深色主题可后续增加，但不作为第一版默认方案。

### 3.1 默认浅色主题

| 用途 | 色值 | 使用场景 |
| --- | --- | --- |
| App background | `#F6F7F9` | 主窗口背景、页面底色 |
| Surface | `#FFFFFF` | 表格、Inspector、弹窗主体 |
| Surface muted | `#EEF2F5` | 工具栏、表头、弱分组背景 |
| Border | `#D8DEE6` | 分隔线、表格线、输入框边框 |
| Text primary | `#1F2933` | 正文、表格主值、标题 |
| Text secondary | `#667085` | 辅助说明、路径、次要元数据 |
| Text disabled | `#98A2B3` | 禁用状态、不可用能力 |
| Primary | `#087F8C` | 主操作、当前选中、活动连接 |
| Primary hover | `#066C77` | 主按钮 hover、选中加深 |
| Primary subtle | `#DDF4F2` | 选中行背景、轻量提示 |
| Link / relation | `#3B5BDB` | trace/source/route 关联标记 |
| Success | `#178C55` | 在线、完成、cache 正常 |
| Warning | `#B7791F` | cache 缺失、需确认、部分跳过 |
| Danger | `#C2410C` | 错误、删除、运行失败 |
| Running | `#0E7490` | runtime running、进度强调 |
| Focus ring | `#7DD3FC` | 键盘焦点、可访问性焦点 |

使用规则：

- Teal 作为产品主强调色，只用于当前对象、主操作和活动状态。
- Blue 用于表达对象之间的关系，例如 trace source 到 route 的关联。
- Green / amber / red 仅用于语义状态，不用于装饰。
- 同一屏内避免大面积单一色相；背景和表格应以中性灰白为主。
- 不使用紫色渐变、暗蓝大背景、米色复古主题或装饰性光斑。

### 3.2 后续深色主题

深色主题需要单独验证高 DPI、表格可读性和状态色对比度。建议色值：

| 用途 | 色值 |
| --- | --- |
| App background | `#111827` |
| Surface | `#18212F` |
| Surface muted | `#202B3A` |
| Border | `#344054` |
| Text primary | `#E5E7EB` |
| Text secondary | `#AAB4C3` |
| Primary | `#22A6B3` |
| Primary subtle | `#143C43` |
| Danger | `#F97066` |
| Warning | `#FDB022` |
| Success | `#32D583` |

深色主题不得牺牲表格密度和时间戳可读性。

## 4. 字体与尺寸

字体：

- UI 默认字体：`Segoe UI`, `Microsoft YaHei UI`, `Arial`, sans-serif。
- 等宽字体：`Consolas`, `Cascadia Mono`, monospace。
- 报文 ID、trace ID、scenario ID、路径、时间戳和十六进制 payload 使用等宽字体。

字号：

- 正文：13px 或 14px。
- 表格：12px 或 13px。
- 面板标题：15px 或 16px。
- 页面标题：18px 到 20px。
- 不使用 hero 级大标题。
- 不用 viewport width 缩放字体。

间距：

- 基准间距为 8px。
- 工具栏高度建议 40px。
- 表格行高建议 32px，紧凑模式可降到 28px。
- Inspector 字段行高建议 32px 到 36px。
- 分栏间隔和面板内边距优先使用 8px、12px、16px。

圆角：

- 输入框、按钮、标签、卡片圆角不超过 8px。
- 默认使用 4px 或 6px。

## 5. 组件规则

### 5.1 导航

- 一级导航使用图标加短文本。
- 当前模块使用 Primary 色左边条或背景强调。
- 禁用模块必须视觉弱化，并在 tooltip 中说明未接入。

### 5.2 工具栏

- 工具栏放当前页面的高频动作，例如导入、刷新、重建 cache、保存 scenario、验证、运行。
- 图标按钮必须有 tooltip。
- 文本按钮只用于明确命令，例如 Import Trace、Save Scenario、Validate、Run。
- 主操作每个页面最多一个，避免多个 primary 按钮争抢注意力。

### 5.3 表格

- 表格是 Trace Library、Scenario Library、消息摘要和设备通道列表的默认展示方式。
- 表头固定，列宽稳定，排序状态明确。
- ID、路径、时间戳、payload 使用等宽字体。
- 状态列同时使用图标、文本和颜色，不能只靠颜色表达。
- 长路径中间省略，hover 或 Inspector 中显示完整路径。
- 空状态只说明当前数据为空和可执行动作，不写大段教学文案。

### 5.4 Inspector

Inspector 用于显示和编辑当前选中对象。

字段控件规则：

- Bus 类型使用分段控件：CAN / CANFD。
- driver、device type、workspace 使用下拉或路径选择。
- `nominal_baud`、`data_baud`、`physical_channel` 使用数字输入。
- `listen_only`、`tx_echo`、`resistance_enabled` 使用 checkbox 或 toggle。
- 只读 ID 和路径使用可复制的等宽文本。
- 校验错误就近显示在字段下方，不集中堆在窗口底部。

### 5.5 路由映射

路由映射是 UI 的核心识别语言，必须比 JSON 编辑更直观。

推荐表达：

```text
Trace Source              Logical Channel       Device Target
sample.asc / CH0 CANFD -> 0                  -> tx0 / CAN1 CANFD
sample.asc / CH1 CANFD -> 1                  -> tx0 / CAN2 CANFD
```

规则：

- 一条 route 必须同时显示 source、logical channel 和 target。
- source 和 target 的 bus 类型不一致时，行内直接标红并阻止运行。
- logical channel 重复时，使用 Warning 状态并定位到冲突行。
- 可以使用轻量连线或箭头，但不要依赖复杂画布才能理解。
- 编辑 route 时，优先使用下拉选择已有 source / target，而不是手输 ID。

### 5.6 运行监控

Replay Monitor 应显示：

- 当前状态：STOPPED / RUNNING / PAUSED。
- 当前时间戳、总时长、进度。
- sent frames、skipped frames、errors。
- completed loops。
- 当前 scenario、设备、通道数量。

控制按钮：

- Run：播放图标，Primary 色。
- Pause / Resume：暂停或继续图标。
- Stop：停止图标，危险程度低于 Delete，不用大面积红色。
- 错误面板可展开，显示 runtime snapshot 中的错误消息。

## 6. 状态语言

状态必须短、稳定、可翻译。

Trace 状态：

- Imported：已导入且 metadata 存在。
- Cache Ready：cache 文件存在。
- Cache Missing：metadata 存在但 cache 缺失。
- Rebuilding：正在重建。
- Unsupported：格式不支持。

设备状态：

- Online：设备已打开或枚举成功。
- Offline：设备不可用或未连接。
- Unknown：尚未检测。
- Channel Ready：通道已配置。
- Channel Error：通道配置失败。

运行状态：

- Stopped：未运行。
- Running：正在回放。
- Paused：已暂停。
- Completed：自然结束。
- Failed：运行中出现错误。

危险操作：

- 删除 trace、删除 scenario、停止正在运行的回放都需要明确确认。
- 确认文案必须包含对象名称或 ID。
- 删除成功后显示可追踪结果，例如 deleted library file / cache file。

## 7. 页面风格

### 7.1 Trace Library

主视图：

- 左侧或上方为 trace 表格。
- 右侧 Inspector 显示 source summary、message ID summary、cache path 和 original path。
- 顶部工具栏提供 Import、Refresh、Inspect、Rebuild Cache、Delete。

视觉重点：

- frame count、start/end time、source channel 和 bus 类型应易读。
- message ID 使用十六进制等宽显示。

### 7.2 Scenario Editor

主视图：

- 上方显示 scenario 名称、schema version、validation 状态。
- 中央为 route 映射表或三栏映射视图。
- 侧边 Inspector 编辑 trace、device、source、target 或 route。

规则：

- 默认隐藏原始 JSON，只作为高级查看或导入导出能力。
- 保存前必须执行本地校验。
- 编译失败时显示结构化错误位置。

### 7.3 Replay Monitor

主视图：

- 顶部为运行控制和进度条。
- 中部显示 counters、设备通道状态和当前 plan 摘要。
- 底部或右侧显示 runtime logs / errors。

规则：

- 运行中禁止修改已编译 plan 的关键路由和设备配置。
- Pause 后设备 session 保持打开的事实需要通过状态表达清楚。
- Stop 后状态回到 Stopped，并保留最后一次 counters。

### 7.4 Devices

主视图：

- 设备驱动选择、SDK root、application、device type、device index。
- 枚举结果以表格显示 device info 和 channel count。
- 同星真机能力必须标明只能在 Windows + TSMaster + 实际设备上验证。

## 8. 架构边界

UI 实现必须遵守现有 ports-and-adapters 架构：

- View 只负责控件和布局。
- ViewModel 负责展示状态、选择状态和命令绑定。
- 业务判断放在 `app`、`domain` 或 `planning`。
- UI 调用 `ReplayApplication` 用例，不直接 import Tongxing / ZLG adapter。
- UI 不直接发送硬件帧。
- UI 不直接修改 runtime 内部字段。
- Runtime 监控通过 `ReplayRuntime.snapshot()` 或后续 app 层会话 API 获取。

建议目录：

```text
src/replay_ui_qt/
  main_window.py
  views/
    trace_library_view.py
    scenario_editor_view.py
    replay_monitor_view.py
    devices_view.py
  view_models/
    trace_library_vm.py
    scenario_editor_vm.py
    replay_session_vm.py
    devices_vm.py
```

当 UI 草稿模型和运行模型不一致时，草稿模型应留在 UI/ViewModel 层；只有通过校验后才转换为 `ReplayScenario` 或 `ReplayPlan`。

## 9. 可访问性与本地化

- 所有图标按钮必须有 tooltip。
- 状态不能只靠颜色表达，必须同时使用图标或文本。
- 文本不得挤出按钮、标签、表格单元格或 Inspector 字段。
- 关键错误信息必须可复制。
- 中英文术语保持稳定：Trace Library、Scenario、Replay、Source、Target、Route 可以作为产品术语保留英文。
- Windows 高 DPI 下必须验证 100%、125%、150% 缩放。

## 10. 禁止项

- 不做营销式首页或 hero 页面。
- 不用大面积渐变、装饰光斑或纯视觉背景。
- 不把未实现能力画成可点击可用功能。
- 不让 UI 直接操作硬件 adapter 或 runtime 内部对象。
- 不把原始 JSON 编辑器作为第一版主要交互。
- 不使用只有颜色差异的状态表达。
- 不在表格和路由视图中使用会导致列宽频繁跳动的自适应布局。
- 不引入与工程工具气质冲突的高饱和装饰色。

## 11. UI 交付检查清单

未来任何 UI 改动交付前，应至少检查：

- 是否符合本指南的默认浅色主题和状态色。
- 是否遵守 View / ViewModel / app 分层边界。
- 是否没有宣称未实现的 DBC、诊断、DoIP、ZLG、BLF 或 Qt 功能已经可用。
- Trace、Scenario、Route、Runtime 状态是否可扫描。
- 所有危险操作是否有明确确认。
- 所有按钮、标签和表格文本在常见窗口尺寸下不重叠、不截断关键含义。
- Windows 高 DPI 下控件尺寸、表格行高和图标仍可读。
- 对应的 UI smoke test、ViewModel 单测或手工截图验证已记录。
