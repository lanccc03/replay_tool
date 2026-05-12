# Repository Guidelines

## Start Here

Use this as the quick contributor and agent entry point. For detail, read [`docs/architecture.md`](docs/architecture.md) for runtime, storage, and scenario resolution; [`docs/testing.md`](docs/testing.md) for the test map; [`docs/ui.md`](docs/ui.md) for PySide6/MVVM rules; and [`README.md`](README.md) for CLI usage. Update those docs instead of expanding this file.

## Project Structure & Module Organization

This is a Python `uv` project with ports-and-adapters boundaries. Core replay code lives in `src/replay_tool/`: `domain`, `ports`, `planning`, `runtime`, `storage`, `adapters`, and `app`. The PySide6 workbench is in `src/replay_ui_qt/`: `views`, `view_models`, and `widgets`. Tests are in `tests/`, examples in `examples/`, docs in `docs/`, and vendor SDK material in `TSMaster/`.

## Build, Test, and Development Commands

- `uv sync`: install dependencies.
- `uv run replay validate examples/mock_canfd.json`: validate a scenario.
- `uv run replay run examples/mock_canfd.json`: run a scenario.
- `uv run replay-ui --help`: smoke-test the UI.
- `uv run python -m unittest discover -s tests -v`: run full test suite.
- `uv run python -m unittest tests.test_ui_views -v`: run one module.
- `uv run python -m compileall src tests`: check Python syntax.
- `uv run ruff check src tests`: lint source and tests.

Run commands from the repository root. Use `--workspace .replay_tool` when persisting traces or scenarios.

## Coding Style & Naming Conventions

Use Python 3.9+ and UTF-8 source files. New modules should include `from __future__ import annotations`. Ruff uses a 120-character line length. Public classes and functions need docstrings; use Google-style sections when helpful. Keep domain code free of filesystem, SQLite, Qt, and TSMaster imports. UI code follows [`docs/ui.md`](docs/ui.md).

## Testing Guidelines

Use `unittest`, not pytest. Name test files `tests/test_*.py`. Match the layers in [`docs/testing.md`](docs/testing.md): domain/planning, storage with temporary directories, runtime with mock devices, CLI integration, fake-SDK adapter, and offscreen Qt UI tests. Mock and fake TSMaster tests do not replace manual Windows hardware validation.
