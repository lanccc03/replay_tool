# 同星 TC1014 硬件验证记录

本文用于记录 `next_replay` 在 Windows + 同星 TSMaster + TC1014 设备上的手工验证。自动化测试只覆盖 fake TSMaster API，不等同于真机联调。

## 环境

- 日期：
- Windows 版本：
- Python 版本：
- TSMaster 版本：
- 设备型号：TC1014
- 设备序列号：
- 连接方式：
- 被测分支 / commit：

## 准备

在仓库根目录确认 SDK 目录存在：

    TSMaster/Windows/TSMasterApi

进入 `next_replay`：

    cd C:\code\next_replay

如果使用虚拟环境，先激活环境并安装包；如果 `uv` 可用，优先使用：

    uv sync

没有 `uv` 时可直接设置 `PYTHONPATH`：

    $env:PYTHONPATH = (Join-Path $PWD "src")

## 设备枚举

执行：

    uv run replay-tool devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0

或：

    python -m replay_tool.cli devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0

期望：

- 命令返回 0。
- 输出包含 `tongxing:TC1014` 或实际设备名。
- 输出 serial 与 TSMaster 中看到的设备一致。
- 输出 channels 至少包含待测 CAN/CANFD 物理通道。

记录：

- 输出：
- 是否通过：
- 异常 / 错误码：

## CANFD 发送闭环

执行：

    uv run replay-tool run examples/tongxing_tc1014_canfd.json

或：

    python -m replay_tool.cli run examples/tongxing_tc1014_canfd.json

期望：

- 命令返回 0。
- 输出包含 `Replay started.`、`Replay completed.`、`DONE: state=STOPPED sent=1 skipped=0 errors=0`。
- TSMaster 或外部总线监视器能看到一帧 CANFD：通道 0，ID `0x18DAF110`，DLC `0xC`，BRS 打开，payload 为 `00 01 ... 17`。
- 退出后设备连接释放，重复执行仍能成功。

外部录制端配置检查：

- 样例 trace 的 CANFD 控制字段是 `1 0 C 24`，表示 BRS=1、ESI=0、DLC=`0xC`、数据长度 24 字节。
- 录制端必须配置为 ISO CAN FD，仲裁速率 500 kbit/s，数据速率 2 Mbit/s，并启用 BRS 解码。
- 场景中的 `physical_channel: 0` 对应同星 SDK 的 0 基通道，通常是设备外壳 / TSMaster UI 中的 CAN1；如果线束接在 CAN2/CAN3/CAN4，需要同步修改场景中的 `physical_channel`。
- 确认总线上至少有一个节点会 ACK，或录制设备不是只听且不能 ACK 的配置；同时检查 120Ω 终端和 CANH/CANL 接线。
- 如果使用同一台电脑上的 TSMaster GUI 作为“录制端”，注意它不等同于外部总线分析仪；CLI 使用 application `ReplayTool` 建立自己的 SDK 会话，GUI 当前工程不一定能看到该 application 的 Tx 回显。

记录：

- 输出：
- 总线监视器截图 / 记录：
- 是否通过：
- 异常 / 错误码：

## 多通道与波特率检查

按实际接线复制一个临时场景，至少覆盖两个物理通道，并记录：

- 物理通道 0 nominal/data baud：
- 物理通道 1 nominal/data baud：
- TSMaster 映射是否匹配：
- FIFO 读取是否能看到预期通道：
- 关闭后重新运行是否成功：

## project_path fallback

如果直接映射失败，给场景中的同星设备配置 `project_path`，指向已在 TSMaster 中保存好映射的工程文件，然后重跑：

    python -m replay_tool.cli run <临时场景.json>

记录：

- 不带 project 的错误码：
- project_path：
- fallback 后是否成功：

## 结论

- 设备枚举：通过 / 未通过
- CANFD 发送：通过 / 未通过
- 多通道：通过 / 未通过 / 未验证
- project_path fallback：通过 / 未通过 / 未验证
- 仍需跟进的问题：
