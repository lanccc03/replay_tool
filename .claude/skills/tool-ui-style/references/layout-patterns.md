# Layout Patterns

## Workbench Shell

A reliable default for internal tools is a workbench shell:

```text
Top status or command bar: workspace, environment, selection, job state
Left navigation: primary modules or object groups
Main workspace: table, editor, graph, monitor, timeline, or logs
Inspector/details: selected object fields, validation, metadata, actions
Bottom panel: logs, output, job queue, console, or diagnostics when needed
```

Use this structure when users need to move between modules, compare records, inspect selection details, or monitor operations.

## Top Bar

Use the top bar for global state and global commands:

- Current workspace, project, tenant, environment, branch, device, scenario, or dataset.
- Connection and runtime state.
- Search, refresh, sync, validate, run, stop, or save when those commands are global.

Keep it compact. Avoid brand-heavy headers unless the tool has multiple products or tenants where identity matters.

## Navigation

Use persistent navigation for tools with multiple modules. Use tabs for closely related views within one module. Use segmented controls for mode switches that affect the same data view.

Rules:

- Keep labels short and stable.
- Mark the current location clearly.
- Disable or hide unavailable modules.
- Avoid deep menu nesting unless the tool has many specialized views.

## Main Workspace

Choose the main workspace by task:

- Tables for records, jobs, traces, devices, builds, files, events, and comparable rows.
- Editors for configuration, scenarios, policies, scripts, queries, mappings, or forms.
- Split panes when users need list-detail, source-target, input-output, or compare workflows.
- Timelines for ordered events, replay, logs, traces, and run progress.
- Graphs only when relationships matter and the graph is readable at realistic scale.
- Dashboards when users need monitoring and triage, not as a default decoration.

## Inspector or Details Panel

Use an inspector when selection details, validation, or secondary actions would overload the main table or editor.

The inspector should show:

- Selected object identity.
- Key metadata and source paths.
- Editable fields when editing is lightweight and scoped.
- Validation results tied to the selected object.
- Dangerous actions only when the selected object is clear.

Place inspectors on the right for wide desktop layouts. Use a bottom sheet, drawer, or separate details page when width is constrained.

## Logs and Output

Logs, consoles, and diagnostic output should be dense, monospaced where useful, filterable, and copyable.

Use a bottom panel when logs support the current workflow. Use a full page when logs are the primary artifact. Avoid putting logs in small cards that cannot be scanned.

## Empty and Setup States

Empty states should explain the immediate condition and offer the next valid action. Keep them brief.

Prefer:

- "No traces imported. Import an ASC or CSV trace to begin."
- "No jobs are running."
- "Device not configured. Select a driver and enumerate devices."

Avoid long tutorials, marketing copy, or decorative empty-state art.

## Responsive Behavior

Internal tools are usually optimized for desktop width. Still define stable behavior:

- Preserve table readability before adding decorative panels.
- Collapse inspectors before hiding primary data.
- Move secondary panels below the main workspace on narrow screens.
- Keep command bars reachable and avoid horizontal overflow.
- Do not scale font size with viewport width.
