# Implement Scenario v2 Without v1 Compatibility

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

This plan follows `.agents/PLANS.md` in this repository.

## Purpose / Big Picture

Users need a scenario file that separates replay resources from routing intent. After this change, a scenario uses `schema_version: 2` and clearly distinguishes trace files, trace sources, device targets, routes, and timeline settings. The visible result is that `replay-tool validate examples/mock_canfd.json` and the Tongxing examples accept v2 files, while old v1 files are rejected.

## Progress

- [x] (2026-04-30 00:00+08:00) Read the current v1 domain model, planner, app loader, runtime session, tests, examples, and PLANS.md.
- [x] (2026-04-30 00:00+08:00) Observed an existing worktree change in `examples/tongxing_tc1014_four_channel_canfd.asc` that removes duplicate smoke frames; keep it as part of this task.
- [x] (2026-04-30 00:00+08:00) Replace the v1 scenario domain shape with v2 traces, sources, targets, routes, and timeline config.
- [x] (2026-04-30 00:00+08:00) Update planner and runtime session to use planned channel configs directly instead of v1 channel bindings.
- [x] (2026-04-30 00:00+08:00) Migrate examples, docs, and tests to v2 and reject v1.
- [x] (2026-04-30 00:00+08:00) Run compile, unit, and CLI validation commands and record outcomes.

## Surprises & Discoveries

- Observation: The worktree already contains a change to `examples/tongxing_tc1014_four_channel_canfd.asc` removing the duplicate second set of four frames.
  Evidence: `git diff -- examples/tongxing_tc1014_four_channel_canfd.asc` shows the file shrinking from eight frame lines to four frame lines.

- Observation: `python -m compileall src tests` failed in the default sandbox while renaming `.pyc` files under a project-local `PYTHONPYCACHEPREFIX`, then passed when rerun with approved elevated permissions.
  Evidence: The sandbox error was `PermissionError: [WinError 5] 拒绝访问`; the elevated rerun listed and compiled all `src` and `tests` files without errors.

## Decision Log

- Decision: Do not implement a runtime v1-to-v2 migration path.
  Rationale: The user explicitly requested no v1 compatibility; migration means updating repository examples, tests, and docs to v2.
  Date/Author: 2026-04-30 / Codex.

- Decision: Keep the current headless replay behavior and only change the scenario shape used to compile frame replay.
  Rationale: DBC, diagnostics, link actions, BLF, ZLG, and Qt UI are out of scope for this implementation.
  Date/Author: 2026-04-30 / Codex.

## Outcomes & Retrospective

Completed. The repository now accepts `schema_version=2` scenarios with separated `traces`, `sources`, `targets`, `routes`, and `timeline`. Old v1 payloads are rejected. Existing replay behavior is preserved for Mock and Tongxing examples, and the four-channel smoke fixture now validates as four frames on four planned channels.

## Context and Orientation

The project root is `C:\code\next_replay`. The current `src/replay_tool/domain/model.py` defines v1 `ReplayScenario` with `traces`, `devices`, `channels`, and `replay`. A v1 channel mixes three concerns: which trace channel to read, which device channel to send to, and which logical replay channel to assign. The current `src/replay_tool/planning/plan.py` compiles those v1 channels into `ReplayPlan.frames` and `ReplayPlan.channels`. Runtime code in `src/replay_tool/runtime/device_session.py` only needs a compiled `ReplayPlan`, so it should remain unaware of Scenario v2.

Scenario v2 splits those concerns:

- `traces` names trace resources.
- `sources` names the trace channel and bus to read.
- `targets` names the device physical channel and bus configuration to send to.
- `routes` connect one source to one target through a logical replay channel.
- `timeline` carries replay settings such as `loop`.

## Plan of Work

First update `src/replay_tool/domain/model.py` by replacing `ChannelBinding` and `ReplayOptions` usage with v2 data classes: `ReplaySource`, `ReplayTarget`, `ReplayRoute`, and `TimelineConfig`. `ReplayScenario.from_dict()` must require `schema_version=2`, parse the v2 collections, and validate required collections, unique IDs, references, unique logical channels, source/target bus consistency, and unsupported non-empty `timeline.diagnostics` or `timeline.link_actions`.

Next update `src/replay_tool/planning/plan.py` so `PlannedChannel` contains `logical_channel`, `device_id`, `physical_channel`, and `config`. The planner must group work by source trace, read each trace once, map frames by source channel and bus, clone them to the route logical channel, and produce planned channels from route targets.

Then update `src/replay_tool/runtime/device_session.py` so channel startup uses `channel.config` instead of `channel.binding.config`. Update tests that build `PlannedChannel` manually.

Then update `src/replay_tool/app/service.py` so imported trace resolution rebuilds a v2 `ReplayScenario` with resolved `traces` and preserves `sources`, `targets`, `routes`, and `timeline`.

Finally migrate examples and tests to v2, update README and docs scenario examples/status text, and keep the four-channel ASC fixture at one frame per physical channel.

## Concrete Steps

From `C:\code\next_replay`, edit only repository files with scoped changes. After implementation, run:

    $env:PYTHONPYCACHEPREFIX=(Join-Path $PWD '.pycache_tmp_scenario_v2'); $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m compileall src tests
    $env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m unittest discover -s tests -v
    $env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m replay_tool.cli validate examples/mock_canfd.json
    $env:PYTHONDONTWRITEBYTECODE='1'; $env:PYTHONPATH=(Join-Path $PWD 'src'); python -m replay_tool.cli validate examples/tongxing_tc1014_four_channel_canfd.json

## Validation and Acceptance

Acceptance requires all automated tests to pass, the mock example to validate with one frame, and the four-channel Tongxing example to validate with four frames and four planned channels. A v1 payload must raise `ValueError` mentioning that only schema v2 is supported.

## Idempotence and Recovery

The changes are ordinary source, test, example, and documentation edits. If validation creates a temporary pycache directory, remove only that project-local directory after verifying its resolved path stays inside `C:\code\next_replay`.

## Artifacts and Notes

Validation output will be recorded in this file after commands are run.

Validation completed:

    python -m compileall src tests
    Result: passed after approved elevated rerun.

    python -m unittest discover -s tests -v
    Result: Ran 32 tests in 0.255s, OK.

    python -m replay_tool.cli validate examples/mock_canfd.json
    Result: OK: mock-canfd-demo frames=1 devices=1 channels=1

    python -m replay_tool.cli validate examples/tongxing_tc1014_four_channel_canfd.json
    Result: OK: tongxing-tc1014-four-channel-canfd-smoke frames=4 devices=1 channels=4

    python -m replay_tool.cli validate examples/tongxing_tc1014_canfd.json
    Result: OK: tongxing-tc1014-canfd-demo frames=68 devices=1 channels=1

## Interfaces and Dependencies

No third-party dependency is added. The public scenario JSON interface changes to v2. `ReplayRuntime` continues to depend only on `ReplayPlan`, not on `ReplayScenario`.
