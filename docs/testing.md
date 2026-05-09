# next_replay 测试说明

本文记录 `next_replay` 的最低验证命令和验证边界。所有命令默认在 `C:\code\next_replay` 执行。

## 自动化验证

PowerShell：

```powershell
$env:PYTHONPYCACHEPREFIX=(Join-Path $PWD ".pycache_tmp_compile")
$env:PYTHONPATH=(Join-Path $PWD "src")
python -m compileall src tests

$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONPATH=(Join-Path $PWD "src")
python -m unittest discover -s tests -v

$env:PYTHONPATH=(Join-Path $PWD "src")
python -m replay_tool.cli validate examples/mock_canfd.json
python -m replay_tool.cli save-scenario examples/mock_canfd.json
python -m replay_tool.cli scenarios
```

如果 `uv` 可用：

```powershell
uv sync
uv run python -m unittest discover -s tests -v
uv run replay-tool validate examples/mock_canfd.json
```

## 测试映射

- Scenario / planner：`tests/test_scenario_and_planner.py`
- runtime：`tests/test_runtime.py`
- CLI 输出和 Trace Library 命令：`tests/test_cli.py`
- Trace Library 存储：`tests/test_trace_store.py`，覆盖 ASC 流式导入、`.frames.bin` 二进制 cache、轻量 block index、source filter、时间窗口读取、cache rebuild 和 trace delete。
- Project / Scenario Store：`tests/test_project_store.py`，覆盖 schema v2 场景保存、更新、列出、查看、删除、base_dir 持久化，以及按保存 ID 编译 / 运行。
- PySide6 UI：`tests/test_ui_view_models.py`、`tests/test_ui_views.py`、`tests/test_ui_smoke.py`、`tests/test_ui_tasks.py` 和 `tests/test_ui_widgets.py`，覆盖 Trace / Scenario ViewModel 映射、Trace import / inspect / rebuild / delete、Scenario draft 编辑 / 保存 / Validate / Run、真实 `ReplayApplication` mock replay session、Replay Monitor 控制、真实 `ReplayApplication` mock device enumeration、Devices app 层枚举、页面 busy / error 反馈、命令状态、异步任务框架、基础 widget 和 offscreen 主窗口 smoke test。
- 同星 fake SDK：`tests/test_tongxing_adapter.py`

## 验证边界

- 自动化测试使用 Mock 设备和 fake TSMaster API，不代表 Windows 真机验证。
- 同星 TC1014 真机验证必须按 `docs/tongxing-hardware-validation.md` 记录。
- 当前 CLI 只接受 `schema_version=2` 场景文件，旧 v1 文件不会运行。
- `validate` / `run` 会把 raw ASC 场景 trace 导入或复用到 workspace cache，再通过 cursor 流式回放。
- ASC 流式导入要求时间戳单调递增；乱序 ASC 外部排序未实现。
- 当前 PySide6 UI 已覆盖 Trace Library 的 Import / Inspect / Rebuild / Delete 闭环、Scenario Store schema v2 draft 编辑 / 保存 / Validate / Run、Replay Monitor mock / app 层 session 控制，以及 Devices mock / app 层枚举；CLI / core 改动通常不需要 Qt 手工点击验证。
- 当前 MVP 未实现 BLF / DBC / DoIP / ZLG / Signal Override / Diagnostics / Settings 产品化；真实窗口点击、高 DPI、Windows 同星真机 UI 工作流未验证。相关能力不能在交付说明中写成已验证。
- offscreen UI smoke test 不能替代真实窗口点击、高 DPI 或同星真机 UI 验证。
