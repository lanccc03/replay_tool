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

## 2026-04-29 实测记录

本节记录本轮 `TC1014 真机闭环与 Runtime 拆分` 工作中的实际命令结果。自动化测试和 CLI 真机发送已经执行；外部总线监视器画面不在 Codex 可读取范围内，因此外部监视器确认项仍标为未由 Codex 观测。

### 环境

- 日期：2026-04-29
- Windows 版本：Microsoft Windows NT 10.0.26200.0
- Python 版本：Python 3.12.10
- TSMaster 版本：未确认
- 设备型号：TC1014
- 设备序列号：DF890401A01F0FBB
- 连接方式：USB / TSMaster SDK 枚举
- 被测分支 / commit：main / db2b61c，工作区含本轮未提交改动

### 自动化验证

执行：

    $env:PYTHONPYCACHEPREFIX=(Join-Path $PWD '.pycache_tmp_compile'); $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m compileall src tests

结果：通过。

执行：

    $env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m unittest discover -s tests -v

结果：

    Ran 21 tests in 0.169s
    OK

执行：

    $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m replay_tool.cli validate examples/tongxing_tc1014_four_channel_canfd.json

结果：

    OK: tongxing-tc1014-four-channel-canfd-smoke frames=4 devices=1 channels=4

### 设备枚举

执行：

    uv run replay-tool devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0

输出：

    tongxing:TC1014 serial=DF890401A01F0FBB channels=[0, 1, 2, 3]

结论：通过。TC1014 可枚举，SDK 报告四个 CAN/CANFD 通道。

### 当前单通道场景发送

执行：

    uv run replay-tool run examples/tongxing_tc1014_canfd.json

输出：

    Replay started.
    Replay completed.
    DONE: state=STOPPED sent=68 skipped=0 errors=0

结论：CLI 真机发送通过。当前场景使用用户提供的 `examples/canfd2.asc`，并将 ASC 源通道 2 解析为 source channel 1，再映射到 TC1014 physical channel 0；因此该场景发送 68 帧，而不是模板中最早描述的单帧样例。外部总线监视器确认：未由 Codex 观测。

### 四通道 CANFD 发送

执行：

    uv run replay-tool run examples/tongxing_tc1014_four_channel_canfd.json

首次执行时 `uv` 访问本机 cache 失败：

    error: Failed to initialize cache at `C:\Users\lancc\AppData\Local\uv\cache`
      Caused by: failed to open file `C:\Users\lancc\AppData\Local\uv\cache\sdists-v9\.git`: 拒绝访问。 (os error 5)

按权限流程提权后重跑，输出：

    Replay started.
    Replay completed.
    DONE: state=STOPPED sent=4 skipped=0 errors=0

结论：CLI 真机发送通过。新增四通道场景包含四帧 CANFD，ASC 源通道 1..4 分别映射到 logical channel 0..3，再发送到 TC1014 physical channel 0..3。预期外部监视器可见：

- CH0：ID `0x18DAF110`，DLC `0xC`，BRS=1，payload `00 01 ... 17`
- CH1：ID `0x18DAF111`，DLC `0xC`，BRS=1，payload `20 21 ... 37`
- CH2：ID `0x18DAF112`，DLC `0xC`，BRS=1，payload `40 41 ... 57`
- CH3：ID `0x18DAF113`，DLC `0xC`，BRS=1，payload `60 61 ... 77`

外部总线监视器确认：未由 Codex 观测。

### 多通道与 fallback 结论

- 多通道发送：CLI 真机四通道发送通过。
- FIFO 真机读取：未验证；fake TSMaster 自动化测试覆盖四通道 FIFO 读取路径。
- project_path fallback：本轮直接映射成功，未触发手工 fallback；fake TSMaster 自动化测试覆盖 fallback 逻辑。
- DBC / DoIP / ZLG / Qt UI：本轮未实现、未验证。
