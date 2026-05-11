# next_replay UI

## Architecture

The PySide6 workbench follows MVVM with a shared application context:

```
MainWindow
  ├── TopStatusBar        (workspace, page, runtime state, message)
  ├── NavigationPanel     (Trace Library / Scenarios / Replay Monitor / Devices)
  ├── QStackedWidget      (one page per module)
  │     ├── TraceLibraryView → TraceLibraryViewModel
  │     ├── ScenariosView    → ScenariosViewModel
  │     ├── ReplayMonitorView → ReplaySessionViewModel
  │     └── DevicesView      → DevicesViewModel
  └── InspectorPanel     (context-sensitive detail pane)
```

- **Views** own Qt widgets and layout. They collect user input and delegate to ViewModels.
- **ViewModels** extend `BaseViewModel`, own display state, selection state, and async command bindings. They call `ReplayApplication` methods and never import hardware adapters.
- **`AppContext`** holds the shared `ReplayApplication` and `TaskRunner` instances. It emits `statusChanged` to update the top status bar.
- **`TaskRunner`** wraps `QThreadPool` with duplicate-name guarding — only one task per name can run at a time. ViewModels call `task_runner.start(name, callable)` to offload blocking operations.
- **Theme** (`theme.py`) defines a light engineering color palette and a Fusion-based stylesheet. Fonts: `Segoe UI` for UI, `Consolas` for IDs/timestamps/hex payloads/channel numbers. Table row height ~32px, toolbar ~40px.
- The **inspector panel** is page-agnostic: each page emits `inspectorChanged(title, body)` and `MainWindow` routes the signal from the currently visible page to the panel.

### Style priority

When making UI decisions, apply rules in this order:

1. User's explicit instructions.
2. This document (project-specific UI rules).
3. Existing PySide6 and `replay_ui_qt` code conventions.

### Active pages

Trace Library, Scenarios, Replay Monitor, Devices. The following are **not implemented**: DBC/Signal Override, Diagnostics, DoIP, ZLG, BLF, dark theme, packaging. Never present these as completed.

## Domain component rules

### Trace Library

- Main view: trace table with columns for name, ID, frame count, time range, cache status.
- Inspector: source summary, message ID summary, cache path, original path, frame count, start/end time.
- Toolbar actions: Import, Refresh, Inspect, Rebuild Cache, Delete.
- Message IDs displayed in hex with monospace font.
- Delete requires confirmation with trace name or ID; show deleted library/cache file results.

### Scenario Editor

- Main view: scenario name, schema version, validation status, route mapping.
- Draft state lives in the UI/ViewModel layer. Before saving or running, the body must be validated by the app layer and compiled into a schema v2 scenario or replay plan.
- Source/target selection uses dropdowns of existing objects, not free-text ID entry.
- Save performs local validation first; compilation failures show structured error locations.
- Running locks route, device, and target configs that affect the compiled plan.

### Route Mapping

Routes are the core visual language of the editor. Preferred expression:

```text
Trace Source              Logical Channel       Device Target
sample.asc / CH0 CANFD -> 0                  -> tx0 / CAN1 CANFD
sample.asc / CH1 CANFD -> 1                  -> tx0 / CAN2 CANFD
```

Rules:
- Every route must show source, logical channel, and target simultaneously.
- When source and target bus types differ, flag the specific route and block run.
- Duplicate logical channels use Warning state, highlight the conflicting row.
- Lightweight arrows or connectors are fine; complex canvas rendering is not required.

### Replay Monitor

- Display: state, scenario name, progress, current timestamp, total duration, sent frames, skipped frames, errors, completed loops.
- Run uses Primary color; Pause/Resume use distinct icons; Stop avoids large danger-colored areas.
- Paused state must clearly communicate that device sessions remain open.
- After Stop, return to Stopped and preserve last counters.
- Runtime error panel is expandable and provides copyable error details.

### Devices

- Parameter editing: driver, SDK root, application, device type, device index.
- Enumeration results: table with device info, serial number, channel count, capabilities, health, and per-channel rows.
- Tongxing hardware capabilities must only be annotated as "Windows + TSMaster + physical device required"; if not verified, state this explicitly.

## State language

Status text must be short, stable, and accompanied by an icon or text label — never color alone.

### Trace states

| State | Meaning |
|-------|---------|
| Imported | Imported, metadata present |
| Cache Ready | Cache file exists |
| Cache Missing | Metadata present, cache absent |
| Rebuilding | Cache rebuild in progress |
| Unsupported | Format not supported |

### Device states

| State | Meaning |
|-------|---------|
| Online | Device opened or enumerated successfully |
| Offline | Device unavailable or disconnected |
| Unknown | Not yet detected |
| Channel Ready | Channel configured |
| Channel Error | Channel configuration failed |

### Runtime states

| State | Meaning |
|-------|---------|
| Stopped | Not running |
| Running | Replay in progress |
| Paused | Paused, device sessions still open |
| Completed | Natural end of timeline |
| Failed | Runtime error occurred |
