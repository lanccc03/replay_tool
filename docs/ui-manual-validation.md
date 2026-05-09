# PySide6 UI 手工验证记录

本文用于记录 `next_replay` PySide6 工作台的真实窗口点击、高 DPI 和可读性检查。offscreen 自动化测试只能证明控件构建、ViewModel 映射和 mock / app 层路径，不等同于真实窗口、高 DPI 或同星真机 UI 验证。

同星硬件相关 UI 验证继续记录到 `docs/tongxing-hardware-validation.md`。如果同星设备、外部总线监视器或 Windows 缩放检查未执行，必须写成“未验证”。

## 环境

- 日期：
- Windows 版本：
- Python 版本：
- PySide6 版本：
- 被测分支 / commit：
- Workspace：
- 显示器分辨率：
- Windows 缩放：100% / 125% / 150% / 其他

## 启动

在仓库根目录执行：

    cd C:\code\next_replay
    uv run replay-ui --workspace .replay_tool

期望：

- 主窗口可见，标题为 `next_replay Workbench`。
- 左侧导航包含 Trace Library、Scenarios、Replay Monitor、Devices。
- 顶部状态条显示当前 workspace。
- 右侧 Inspector 随页面和选中对象更新。

记录：

- 是否通过：
- 截图 / 备注：
- 异常 / 错误详情：

## 页面点击检查

逐页点击导航并记录。

| 页面 | 期望 | 结果 | 备注 |
| --- | --- | --- | --- |
| Trace Library | Import / Refresh / Inspect / Rebuild / Delete 状态清楚，错误详情可复制 | 通过 / 未通过 / 未验证 | |
| Scenarios | Overview、Traces & Devices、Routes、JSON tab 可切换，运行中关键编辑入口会锁定 | 通过 / 未通过 / 未验证 | |
| Replay Monitor | 未运行时显示 Stopped；运行后显示 progress、counters、Pause / Resume / Stop | 通过 / 未通过 / 未验证 | |
| Devices | driver、SDK root、application、device type、device index 可编辑；同星真机边界可见 | 通过 / 未通过 / 未验证 | |

## 高 DPI 与可读性

分别在 Windows 缩放 100%、125%、150% 下检查。每个缩放级别都需要重启或重新打开 UI 后观察。

| 缩放 | 文本重叠 | 表格列可读 | 按钮文本完整 | Inspector 可读 | 结果 |
| --- | --- | --- | --- | --- | --- |
| 100% | 无 / 有 / 未验证 | 是 / 否 / 未验证 | 是 / 否 / 未验证 | 是 / 否 / 未验证 | 通过 / 未通过 / 未验证 |
| 125% | 无 / 有 / 未验证 | 是 / 否 / 未验证 | 是 / 否 / 未验证 | 是 / 否 / 未验证 | 通过 / 未通过 / 未验证 |
| 150% | 无 / 有 / 未验证 | 是 / 否 / 未验证 | 是 / 否 / 未验证 | 是 / 否 / 未验证 | 通过 / 未通过 / 未验证 |

记录：

- 问题页面：
- 截图 / 备注：
- 是否需要调整布局：

## 可访问性与状态表达

检查项：

- 所有图标或短按钮有 tooltip。
- 状态不只靠颜色表达，同时有文本。
- 禁用能力有明确文案或 tooltip 说明。
- 错误详情可复制。
- 危险操作确认文案包含对象名称或 ID。
- DBC、Signal Override、Diagnostics、DoIP、ZLG、BLF 未显示为可用功能。

记录：

- 是否通过：
- 问题：
- 跟进：

## 同星真机 UI 边界

本节只记录本轮是否执行。详细结果必须写入 `docs/tongxing-hardware-validation.md`。

- Devices 同星真机 UI 枚举：通过 / 未通过 / 未验证
- Scenario 同星真机 UI Run：通过 / 未通过 / 未验证
- Pause / Resume / Stop 真机路径：通过 / 未通过 / 未验证
- 外部总线监视器确认：通过 / 未通过 / 未验证 / 未由 Codex 观测

## 结论

- 真实窗口点击：通过 / 未通过 / 未验证
- 高 DPI：通过 / 未通过 / 未验证
- 可访问性与状态表达：通过 / 未通过 / 未验证
- 同星真机 UI：通过 / 未通过 / 未验证
- 未验证项：
- 仍需跟进的问题：
