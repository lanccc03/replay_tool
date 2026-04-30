# next_replay

`next_replay` is a new, parallel replay tool project. It does not import or modify the existing `replay_platform` package.

The first version is a CLI-first MVP with a ports-and-adapters architecture:

- `domain`: stable replay types.
- `ports`: interfaces for trace readers and bus devices.
- `planning`: compiles a scenario into a replay plan.
- `runtime`: executes the plan.
- `adapters`: mock and Tongxing implementations.
- `storage`: ASC trace parsing and Trace Library binary cache storage.
- `app`: CLI use cases.

The architecture and design guide is maintained in
[`docs/architecture-design-guide.md`](docs/architecture-design-guide.md).

## Commands

Install the local environment once:

```powershell
uv sync
```

After that, run the CLI with the short `replay` command:

```powershell
replay validate examples/mock_canfd.json
replay run examples/mock_canfd.json
replay import examples/sample.asc
replay traces
replay inspect <trace-id>
```

The longer `replay-tool` command is still available as a compatibility alias.
If `replay` is not found after editing `pyproject.toml`, run `uv sync` again
or activate the local `.venv`.

### CLI usage

General form:

```powershell
replay <command> [options]
```

Every subcommand currently accepts `--workspace <path>`. The default workspace
is `.replay_tool` under the current directory. It stores imported trace files,
metadata, and generated binary frame caches.

`validate` and `run` resolve scenario trace paths through the Trace Library.
When a scenario points at a raw `.asc` file, the application imports or reuses a
workspace cache first, then replays from the `.frames.bin` cache through a
streaming cursor instead of loading the full trace into `ReplayPlan`.

Validate a scenario without sending frames:

```powershell
replay validate [--workspace .replay_tool] <scenario.json>
```

Compile and run a scenario. Frames are sent through the devices configured in
the scenario file:

```powershell
replay run [--workspace .replay_tool] <scenario.json>
```

Scenario files use `schema_version=2`. The v2 shape separates trace resources,
trace sources, device targets, and routes:

```json
{
  "schema_version": 2,
  "name": "mock-canfd-demo",
  "traces": [{"id": "trace1", "path": "sample.asc"}],
  "devices": [{"id": "mock0", "driver": "mock"}],
  "sources": [{"id": "trace1-canfd0", "trace": "trace1", "channel": 0, "bus": "CANFD"}],
  "targets": [{"id": "mock0-canfd0", "device": "mock0", "physical_channel": 0, "bus": "CANFD"}],
  "routes": [{"logical_channel": 0, "source": "trace1-canfd0", "target": "mock0-canfd0"}],
  "timeline": {"loop": false}
}
```

Older `schema_version=1` scenario files are not accepted by the current CLI.

Import an ASC trace into the Trace Library:

```powershell
replay import [--workspace .replay_tool] <trace.asc>
```

List imported traces:

```powershell
replay traces [--workspace .replay_tool]
```

Inspect one imported trace, including source-channel and message-ID summaries:

```powershell
replay inspect [--workspace .replay_tool] <trace-id>
```

Rebuild an imported trace's binary frame cache from its copied source file:

```powershell
replay rebuild-cache [--workspace .replay_tool] <trace-id>
```

Delete an imported trace record and its managed library/cache files:

```powershell
replay delete-trace [--workspace .replay_tool] <trace-id>
```

Trace import streams ASC input into the binary cache and rejects out-of-order
timestamps. The first streaming implementation does not support external
sorting for unordered traces.

List device channels for a hardware adapter:

```powershell
replay devices [--workspace .replay_tool] [--driver tongxing] [--sdk-root TSMaster/Windows] [--application ReplayTool] [--device-type TC1014] [--device-index 0]
```

Device option defaults:

- `--driver`: device adapter name, default `tongxing`.
- `--sdk-root`: SDK root directory, default `TSMaster/Windows`.
- `--application`: TSMaster application name, default `ReplayTool`.
- `--device-type`: hardware model, default `TC1014`.
- `--device-index`: hardware index, default `0`.

Without uv or an installed script, use Python directly from this directory:

```powershell
$env:PYTHONPATH = (Join-Path $PWD "src")
python -m replay_tool.cli validate examples/mock_canfd.json
python -m replay_tool.cli run examples/mock_canfd.json
python -m replay_tool.cli import examples/sample.asc
python -m replay_tool.cli traces
python -m replay_tool.cli inspect <trace-id>
python -m unittest discover -s tests -v
```

## Tongxing / TSMaster

The Tongxing adapter loads the SDK from `TSMaster/Windows` by default. It imports `TSMasterApi.TSMasterAPI` from that directory and does not use the legacy `TSMasterApi/` package that remains in the old `replay` project.

Hardware validation must be done on Windows with TSMaster installed and a connected Tongxing device:

```powershell
replay devices --driver tongxing
replay run examples/tongxing_tc1014_canfd.json
```

Use [`docs/tongxing-hardware-validation.md`](docs/tongxing-hardware-validation.md)
to record Windows TC1014 validation results.
