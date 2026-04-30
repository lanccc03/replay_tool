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
- Trace Library 存储：`tests/test_trace_store.py`，覆盖 ASC `.frames.bin` 二进制 cache、source filter、时间窗口读取、cache rebuild 和 trace delete。
- 同星 fake SDK：`tests/test_tongxing_adapter.py`

## 验证边界

- 自动化测试使用 Mock 设备和 fake TSMaster API，不代表 Windows 真机验证。
- 同星 TC1014 真机验证必须按 `docs/tongxing-hardware-validation.md` 记录。
- 当前 CLI 只接受 `schema_version=2` 场景文件，旧 v1 文件不会运行。
- 当前项目没有 Qt UI，迁移或 CLI 改动不需要 Qt 手工点击验证。
- 当前 MVP 未实现 BLF / DBC / DoIP / ZLG / Qt UI；相关能力不能在交付说明中写成已验证。
