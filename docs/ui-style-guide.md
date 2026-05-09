# next_replay UI 专属补充规则

本文记录 `next_replay` 在通用团队工具 UI 风格之外的项目专属约束。通用的工具型 UI 原则、布局模式、组件规则、视觉基线和交付检查以 `.codex/skills/tool-ui-style` 为准；本文只补充 PySide6 工作台、回放领域、硬件边界和当前能力状态。

阶段状态和验收进度以 `docs/ui-implementation-roadmap.md` 为准。本文不表示完整 Qt 工作台已经完成。

## 1. 适用优先级

UI 任务按以下顺序应用规则：

1. 用户明确要求。
2. 本文和 `docs/ui-implementation-roadmap.md` 中的 `next_replay` 项目边界。
3. `.codex/skills/tool-ui-style` 的通用团队工具 UI 规则。
4. PySide6、现有 `replay_ui_qt` 代码和测试中的本地惯例。

如果某条规则适合多个团队工具，优先沉淀到 `.codex/skills/tool-ui-style`；如果只和 `next_replay` 的回放、trace、scenario、设备或同星验证有关，保留在本文。

## 2. 产品定位

`next_replay` 的 UI 是 PySide6 工程工作台，服务 trace 导入、scenario 编辑、设备配置和 replay 运行监控。它不是营销页、演示中控屏，也不是 CLI 的薄包装。

第一屏应直接呈现可工作的工程界面。当前核心模块为：

- Trace Library：导入、查看、重建 cache、删除和刷新 trace。
- Scenarios：创建、加载、编辑、保存、校验、删除 schema v2 scenario，并可通过 mock / app 层运行当前 draft。
- Replay Monitor：显示非阻塞 replay session 的状态、进度、counters、errors，并支持 Pause / Resume / Stop。
- Devices：编辑 driver / SDK / hardware 参数，枚举并展示 device info、capabilities、health 和 channels。

DBC / Signal Override、Diagnostics、DoIP、ZLG、BLF、深色主题、打包、高 DPI 手工验证、真实窗口点击和 Windows 硬件 UI 验证尚未完成或未验证时，不得呈现为已完成能力。

## 3. 工作台结构

`next_replay` 继续使用四区工作台结构：

```text
Top Status Bar: workspace / scenario / device / runtime state
Navigation: Trace Library / Scenarios / Replay Monitor / Devices
Main Workspace: table / editor / route map / monitor / device list
Inspector: selected object details / validation / metadata / actions
```

项目约束：

- 左侧导航只放一级模块；未接入能力隐藏、禁用或明确标记未接入。
- 顶部状态条显示当前 workspace、当前 scenario、设备连接状态和 runtime 状态。
- 主工作区优先使用表格、分栏、路由映射、时间轴和日志。
- 右侧 Inspector 显示当前选中对象的属性、校验结果、可编辑字段和结果详情。
- 原始 JSON 只能作为高级查看、导入或导出能力，不作为第一版主交互。

## 4. 项目视觉基线

本项目采用 `.codex/skills/tool-ui-style/references/visual-system.md` 的浅色工程主题作为基线，并固定以下项目角色：

| 用途 | 色值 | 项目含义 |
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
| Link / relation | `#3B5BDB` | trace / source / route 关联标记 |
| Success | `#178C55` | 在线、完成、cache 正常 |
| Warning | `#B7791F` | cache 缺失、需确认、部分跳过 |
| Danger | `#C2410C` | 错误、删除、运行失败 |
| Running | `#0E7490` | runtime running、进度强调 |
| Focus ring | `#7DD3FC` | 键盘焦点、可访问性焦点 |

字体和密度：

- UI 默认字体：`Segoe UI`, `Microsoft YaHei UI`, `Arial`, sans-serif。
- 等宽字体：`Consolas`, `Cascadia Mono`, monospace。
- 报文 ID、trace ID、scenario ID、路径、时间戳、通道号和十六进制 payload 使用等宽字体。
- 表格行高默认约 32px，紧凑模式可降到 28px。
- 工具栏高度约 40px，Inspector 字段行高约 32px 到 36px。

深色主题属于后续能力，必须单独验证高 DPI、表格可读性、状态色对比度和日志可读性。

## 5. 领域组件规则

### Trace Library

- 主视图使用 trace 表格。
- Inspector 显示 source summary、message ID summary、cache path、original path、frame count、start/end time。
- 顶部工具栏提供 Import、Refresh、Inspect、Rebuild Cache、Delete。
- message ID 使用十六进制等宽显示。
- 删除 trace 前必须确认 trace name 或 trace ID；成功后显示 library file / cache file 删除结果。

### Scenario Editor

- 主视图显示 scenario 名称、schema version、validation 状态和 route 映射。
- Draft 状态留在 UI / ViewModel 层；保存或运行前必须经 app 层校验并转换为 schema v2 scenario 或 replay plan。
- source / target 选择优先使用已有对象下拉，不要求用户手输 ID。
- 保存前必须执行本地校验；编译失败时显示结构化错误位置。
- 运行中锁定会影响已编译 plan 的 route、device、target 等关键配置。

### Route Mapping

路由映射是 `next_replay` 的核心识别语言，必须比 JSON 更直观。推荐表达：

```text
Trace Source              Logical Channel       Device Target
sample.asc / CH0 CANFD -> 0                  -> tx0 / CAN1 CANFD
sample.asc / CH1 CANFD -> 1                  -> tx0 / CAN2 CANFD
```

规则：

- 一条 route 必须同时显示 source、logical channel 和 target。
- source 和 target 的 bus 类型不一致时，定位到具体 route，并阻止运行。
- logical channel 重复时，使用 Warning 状态并定位到冲突行。
- 可以使用轻量箭头或连线，但不能依赖复杂画布才能理解。

### Replay Monitor

- 显示状态、scenario、进度、当前时间戳、总时长、sent frames、skipped frames、errors、completed loops。
- Run 使用播放图标和 Primary 色；Pause / Resume 使用暂停或继续图标；Stop 不使用大面积危险色。
- Pause 后设备 session 保持打开的事实必须通过状态表达清楚。
- Stop 后状态回到 Stopped，并保留最后一次 counters。
- runtime error panel 必须可展开并提供可复制错误详情。

### Devices

- 参数编辑包含 driver、SDK root、application、device type、device index。
- 枚举结果以表格显示 device info、serial number、channel count、capabilities、health 和 channel rows。
- 同星真机能力只能标注为 Windows + TSMaster + 实际设备可验证；未执行时交付说明必须明确。

## 6. 状态语言

状态文案保持短、稳定，并在 UI 中配合图标或文本，不只依赖颜色。

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

## 7. 架构边界

UI 实现必须遵守现有 ports-and-adapters 架构：

- View 只负责控件、布局和用户输入收集。
- ViewModel 负责展示状态、选择状态、命令绑定、busy / error / status message。
- 业务判断放在 `ReplayApplication`、`domain`、`planning` 或后续 app 层会话 API。
- UI 调用 `ReplayApplication` 用例，不直接 import Tongxing / ZLG adapter。
- UI 不直接发送硬件帧。
- UI 不直接修改 `ReplayRuntime` 内部字段。
- Runtime 监控通过 `ReplayRuntime.snapshot()` 或后续 app 层会话 API 获取。

建议目录仍为：

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

## 8. 交付检查

UI 改动交付前至少检查：

- 是否遵守 `.codex/skills/tool-ui-style/references/review-checklist.md`。
- 是否没有把 DBC、Signal Override、Diagnostics、DoIP、ZLG、BLF 或未验证 Qt 能力呈现为已完成。
- 是否没有绕过 `ReplayApplication` 直接访问硬件 adapter、发送硬件帧或修改 runtime 内部字段。
- Trace、Scenario、Route、Runtime、Device 状态是否可扫描、可定位、可复制关键错误。
- 危险操作确认是否包含对象名称、ID、路径或目标。
- 对应 UI smoke test、ViewModel 单测、app 层用例或手工截图验证是否已记录。
- Windows 高 DPI、真实窗口点击或同星真机验证未执行时，最终说明是否明确写出未验证。
