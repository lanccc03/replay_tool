# TC1014 真机闭环与 Runtime 拆分

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` from the repository root. A future engineer must be able to continue from this file alone, so this document repeats the relevant repository context and validation commands.

## Purpose / Big Picture

This work turns `next_replay` from a thin CAN/CANFD MVP into a verified TC1014 hardware baseline and a cleaner runtime foundation. After completion, a user can enumerate the connected TC1014, replay CANFD on all four physical channels, confirm frames on an external bus monitor, and still run the same CLI/API while the runtime internals are split into testable scheduler, dispatcher, device-session, and telemetry pieces.

The visible result is that the existing single-channel scenario and a new four-channel TC1014 scenario both run through `replay-tool`, while the automated tests prove that the runtime now batches frames in a 2 ms window, groups sends by device, and accounts for partial sends correctly.

## Progress

- [x] (2026-04-29 Asia/Shanghai) Planned combined scope: TC1014 hardware closure plus runtime refactor.
- [x] (2026-04-29 Asia/Shanghai) Chosen validation topology: external bus monitor.
- [x] (2026-04-29 Asia/Shanghai) Chosen channel scope: TC1014 CH0 through CH3.
- [x] (2026-04-29 Asia/Shanghai) Created this ExecPlan as `.agents/execplans/tc1014-runtime-foundation.md`.
- [x] (2026-04-29 Asia/Shanghai) Captured baseline tests and current hardware behavior.
- [x] (2026-04-29 Asia/Shanghai) Added four-channel TC1014 example assets and fake SDK tests.
- [x] (2026-04-29 Asia/Shanghai) Split runtime internals while preserving public `ReplayRuntime`.
- [x] (2026-04-29 Asia/Shanghai) Re-ran automated validation and TC1014 CLI hardware validation.
- [x] (2026-04-29 Asia/Shanghai) Updated `docs/tongxing-hardware-validation.md` with real command results.
- [ ] External bus monitor confirmation remains a user-side/manual observation because Codex cannot inspect that screen or device output directly.

## Surprises & Discoveries

- Observation: The working tree already has user changes in `examples/tongxing_tc1014_canfd.json` and an untracked `examples/canfd2.asc`.
  Evidence: `git status --short` showed those paths before implementation. Preserve them; do not revert.

- Observation: The current single-channel scenario maps source channel 1 from `examples/canfd2.asc` to TC1014 physical channel 0.
  Evidence: `examples/tongxing_tc1014_canfd.json` has `source_channel: 1`, `physical_channel: 0`, and `path: "canfd2.asc"`.

- Observation: Baseline TC1014 enumeration succeeds and reports four channels.
  Evidence: `uv run replay-tool devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0` returned `tongxing:TC1014 serial=DF890401A01F0FBB channels=[0, 1, 2, 3]`.

- Observation: Baseline single-channel TC1014 replay succeeds but sends 68 frames because the current user-provided trace contains many CANFD frames on source channel 1.
  Evidence: `uv run replay-tool run examples/tongxing_tc1014_canfd.json` returned `DONE: state=STOPPED sent=68 skipped=0 errors=0`.

- Observation: After the runtime split, automated coverage increased from 17 to 21 tests.
  Evidence: `python -m unittest discover -s tests -v` returned `Ran 21 tests in 0.169s` and `OK`.

- Observation: The first four-channel hardware run hit a local `uv` cache permission error, not a replay code failure.
  Evidence: `uv run replay-tool run examples/tongxing_tc1014_four_channel_canfd.json` first returned `Failed to initialize cache ... 拒绝访问`; the same command succeeded when rerun with approved escalation.

- Observation: The compatibility forwarding file `src/replay_tool/runtime/engine.py` was removed after the user decided the old import path was no longer needed.
  Evidence: `src/replay_tool/runtime/__init__.py` now imports `ReplayRuntime` directly from `replay_tool.runtime.kernel`.

## Decision Log

- Decision: Combine TC1014 hardware closure and runtime split in one ExecPlan.
  Rationale: Hardware evidence should anchor the runtime refactor and catch regressions immediately.
  Date/Author: 2026-04-29 / Codex with user selection.

- Decision: Validate using an external bus monitor across all four TC1014 channels.
  Rationale: External observation is stronger than same-process echo and covers channel mapping, bitrate, wiring, ACK, and close/reopen behavior.
  Date/Author: 2026-04-29 / Codex with user selection.

- Decision: Keep `ReplayRuntime` as the public API and split implementation behind it.
  Rationale: CLI, app service, and tests already use this class; preserving it avoids unrelated migration noise.
  Date/Author: 2026-04-29 / Codex.

- Decision: Keep scenario schema v1 unchanged for this plan.
  Rationale: The goal is hardware/runtime foundation work. Schema v2, migrations, DBC, DoIP, ZLG, and Qt UI are explicitly out of scope.
  Date/Author: 2026-04-29 / Codex.

- Decision: Leave the user-provided single-channel TC1014 scenario and `canfd2.asc` intact, even though it sends 68 frames.
  Rationale: Those files were already modified by the user before implementation and appear to be active hardware material. The new four-channel smoke scenario provides the deterministic 4-frame acceptance case.
  Date/Author: 2026-04-29 / Codex.

- Decision: Remove `src/replay_tool/runtime/engine.py` instead of keeping it as a compatibility forwarding module.
  Rationale: The user explicitly said the old door is not needed. New code should import `ReplayRuntime` from `replay_tool.runtime` or `replay_tool.runtime.kernel`.
  Date/Author: 2026-04-29 / Codex with user direction.

## Outcomes & Retrospective

The implementation added a deterministic four-channel TC1014 smoke trace and scenario, expanded fake TSMaster coverage for four-channel mapping/send/read/close, and split the runtime into `kernel`, `scheduler`, `dispatcher`, `device_session`, and `telemetry` modules. `ReplayRuntime` remains available from `replay_tool.runtime`; the old `replay_tool.runtime.engine` forwarding module has been removed.

Automated validation passed with 21 tests. TC1014 CLI hardware validation passed for device enumeration, the existing single-channel scenario, and the new four-channel scenario. External bus monitor confirmation remains unverified by Codex because the monitor output is outside the accessible workspace and terminal.

## Context and Orientation

`next_replay` is a new project under `C:\code\next_replay`. It must not import code from the old `C:\code\replay\src\replay_platform` package. Current core flow is: scenario JSON is parsed by `ReplayScenario`, compiled by `ReplayPlanner` into `ReplayPlan`, and executed by `ReplayRuntime`.

Before this plan, the runtime was concentrated in `src/replay_tool/runtime/engine.py`. After this plan, `ReplayRuntime` lives in `src/replay_tool/runtime/kernel.py` and is exported from `src/replay_tool/runtime/__init__.py`. The Tongxing adapter lives in `src/replay_tool/adapters/tongxing/device.py`. Hardware validation instructions live in `docs/tongxing-hardware-validation.md`. Automated tests use fake TSMaster API in `tests/test_tongxing_adapter.py`; those tests are required but do not prove real hardware behavior.

An adapter is a class that hides a hardware SDK behind the `BusDevice` protocol in `src/replay_tool/ports/device.py`. A replay plan is the immutable runtime input defined by `ReplayPlan` in `src/replay_tool/planning/plan.py`. A runtime snapshot is the immutable status object returned by `ReplayRuntime.snapshot()`.

## Plan of Work

First, establish the baseline. Run compile and unit tests, validate the mock scenario, then run TC1014 enumeration and the current single-channel CANFD scenario. Record exact command output and external monitor observations in `docs/tongxing-hardware-validation.md`. If hardware fails before code changes, document the failure first and only then patch the smallest adapter or scenario issue needed to make the baseline meaningful.

Next, add a committed four-channel TC1014 example: a small ASC trace with four CANFD frames on source channels 0 through 3, and a matching scenario mapping logical channels 0 through 3 to physical channels 0 through 3. Use 500 kbit/s nominal and 2 Mbit/s data bitrate unless the existing TC1014 setup proves otherwise. Add fake SDK tests that start all four channels, verify channel count growth to four, verify mappings and CANFD bitrate calls for each physical channel, send one frame per channel, read FIFO frames, and close cleanly.

Then split runtime internals without changing CLI behavior. Export `ReplayRuntime` from `replay_tool.runtime`, with implementation in `kernel.py` for lifecycle, `scheduler.py` for cursor, loop, batch timing, and pause/resume time-base math; `dispatcher.py` for frame grouping and partial-send accounting; `device_session.py` for open, start, close, and route lookup; and `telemetry.py` for snapshot counters and errors. Add Google-style docstrings to new public classes and methods. Do not add diagnostics, DBC, ZLG, Qt, schema v2, or old-project imports in this ExecPlan.

Runtime behavior must remain compatible, with two deliberate improvements: dispatch frames in 2 ms timestamp batches grouped by device, and count partial sends correctly as accepted frames plus skipped remainder. Clarify the `BusDevice.send()` contract as "number of frames accepted for transmission." Add optional `timeline_index` and `timeline_size` fields to `ReplaySnapshot` with defaults so existing callers keep working.

Finally, rerun all automated checks and hardware validation. The final hardware pass requires TC1014 enumeration showing four channels, single-channel CANFD replay with `sent=1 skipped=0 errors=0`, four-channel replay with `sent=4 skipped=0 errors=0`, and external monitor evidence for all expected IDs/payloads on CH0 through CH3.

## Concrete Steps

Run from `C:\code\next_replay`.

Baseline commands:

    $env:PYTHONPYCACHEPREFIX=(Join-Path $PWD ".pycache_tmp_compile")
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m compileall src tests

    $env:PYTHONDONTWRITEBYTECODE='1'
    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m unittest discover -s tests -v

    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m replay_tool.cli validate examples/mock_canfd.json

Hardware baseline commands:

    uv run replay-tool devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0
    uv run replay-tool run examples/tongxing_tc1014_canfd.json

If `uv` is unavailable, use:

    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m replay_tool.cli devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0
    python -m replay_tool.cli run examples/tongxing_tc1014_canfd.json

Expected single-channel output includes:

    Replay started.
    Replay completed.
    DONE: state=STOPPED sent=1 skipped=0 errors=0

Add four-channel assets and tests, then run:

    $env:PYTHONPATH=(Join-Path $PWD "src")
    python -m replay_tool.cli validate examples/tongxing_tc1014_four_channel_canfd.json
    uv run replay-tool run examples/tongxing_tc1014_four_channel_canfd.json

Expected four-channel output includes:

    DONE: state=STOPPED sent=4 skipped=0 errors=0

## Validation and Acceptance

Automated acceptance:

- `python -m compileall src tests` succeeds.
- `python -m unittest discover -s tests -v` succeeds.
- Existing CLI tests still pass unchanged.
- New runtime tests prove batching, grouping by device, partial send accounting, pause/resume, loop restart, and cleanup.
- New Tongxing fake SDK tests prove four-channel mapping/config/send/read/close behavior.

Hardware acceptance:

- `devices --driver tongxing` returns 0 and lists at least channels 0, 1, 2, and 3.
- Single-channel scenario sends the expected CANFD frame from the current scenario and trace.
- Four-channel scenario sends one expected CANFD frame on each physical channel CH0 through CH3.
- External monitor confirms actual bus traffic. CLI success alone is not enough.
- `docs/tongxing-hardware-validation.md` records environment, command output, monitor evidence, pass/fail status, and explicitly says DBC/DoIP/ZLG/Qt were not validated.

## Idempotence and Recovery

All committed example assets must be safe to rerun. Any temporary hardware scenarios with local `project_path` values go under `.replay_tool/hardware/`, which is ignored. Do not commit local TSMaster project files unless the user explicitly asks.

If direct TSMaster mapping fails, record the error code first. Then create or use a TSMaster project mapping and test `project_path` fallback with a temporary scenario. If fallback is not triggered because direct mapping succeeds, rely on fake SDK fallback tests and mark manual fallback as "not triggered" rather than "passed."

Preserve existing user changes in `examples/tongxing_tc1014_canfd.json` and `examples/canfd2.asc`. Read them before editing related examples.

## Artifacts and Notes

Baseline automated transcript:

    python -m compileall src tests
    Listing 'src'...
    Listing 'tests'...

    python -m unittest discover -s tests -v
    Ran 17 tests in 0.177s
    OK

    python -m replay_tool.cli validate examples/mock_canfd.json
    OK: mock-canfd-demo frames=1 devices=1 channels=1

Baseline hardware transcript:

    uv run replay-tool devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0
    tongxing:TC1014 serial=DF890401A01F0FBB channels=[0, 1, 2, 3]

    uv run replay-tool run examples/tongxing_tc1014_canfd.json
    Replay started.
    Replay completed.
    DONE: state=STOPPED sent=68 skipped=0 errors=0

Final automated transcript:

    python -m compileall src tests
    Listing 'src'...
    Listing 'tests'...

    python -m unittest discover -s tests -v
    Ran 21 tests in 0.169s
    OK

    python -m replay_tool.cli validate examples/tongxing_tc1014_four_channel_canfd.json
    OK: tongxing-tc1014-four-channel-canfd-smoke frames=4 devices=1 channels=4

Final hardware transcript:

    uv run replay-tool devices --driver tongxing --sdk-root TSMaster/Windows --device-type TC1014 --device-index 0
    tongxing:TC1014 serial=DF890401A01F0FBB channels=[0, 1, 2, 3]

    uv run replay-tool run examples/tongxing_tc1014_canfd.json
    Replay started.
    Replay completed.
    DONE: state=STOPPED sent=68 skipped=0 errors=0

    uv run replay-tool run examples/tongxing_tc1014_four_channel_canfd.json
    Replay started.
    Replay completed.
    DONE: state=STOPPED sent=4 skipped=0 errors=0

Keep the full hardware observations in `docs/tongxing-hardware-validation.md`.

## Interfaces and Dependencies

Public compatibility:

- Keep `replay_tool.runtime.ReplayRuntime` and its public methods: `configure`, `start`, `pause`, `resume`, `stop`, `wait`, and `snapshot`.
- Do not keep `replay_tool.runtime.engine`; it was removed by user direction after the split.
- Keep CLI commands and current scenario schema v1 behavior.
- Clarify `BusDevice.send(frames)` as returning the number of frames accepted.
- Add only backward-compatible fields to `ReplaySnapshot`: `timeline_index: int = 0` and `timeline_size: int = 0`.

Runtime modules to create:

- `runtime/kernel.py`: owns lifecycle and worker thread.
- `runtime/scheduler.py`: owns frame cursor, 2 ms batch selection, pause/resume time-base math, and loop reset.
- `runtime/dispatcher.py`: maps frames to devices, groups batches by device, sends, and reports sent/skipped counts.
- `runtime/device_session.py`: opens adapters, starts channels, maps logical to physical channels, and closes devices.
- `runtime/telemetry.py`: owns counters, errors, and immutable snapshot updates.

Assumptions:

- The machine is Windows with TSMaster installed and a TC1014 connected.
- External monitor wiring covers TC1014 CH0 through CH3 with correct termination and ACK-capable bus conditions.
- Default bitrates are 500 kbit/s nominal and 2 Mbit/s data.
- This ExecPlan does not implement DBC, DoIP, ZLG, Qt UI, schema v2, or diagnostics.

Revision note: Created initial living ExecPlan before implementation so future work can resume from this file alone.

Revision note: Updated after implementation with runtime split, four-channel TC1014 assets, automated test results, TC1014 CLI hardware results, and the remaining external-monitor verification gap.

Revision note: Updated after removing the old `runtime.engine` compatibility module by user request.
