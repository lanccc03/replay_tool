# UI Cohesion Design

## Motivation

The current UI's toolbar buttons, tables, and panels feel like disconnected pieces rather than a unified whole. The core issue: NavigationPanel and InspectorPanel are framed as surface containers (white background + border), but the main content area between them has no container, making toolbars and tables appear to float on the app background.

## Design

### Shell: ContentPanel container

Add a `QFrame#ContentPanel` wrapping `QStackedWidget` in `MainWindow._build_ui`, creating three visually equal surface panels:

```
root_layout
├── TopStatusBar
└── body (QHBoxLayout)
    ├── NavigationPanel   (white surface + border)
    ├── ContentPanel      (white surface + border, NEW)
    │   └── QStackedWidget
    └── InspectorPanel    (white surface + border)
```

`ContentPanel` uses the same surface styling as `NavigationPanel` and `InspectorPanel`: `background: #FFFFFF; border: 1px solid #D8DEE6;`.

### Toolbar: ToolbarHeader frame

Within each View, wrap the toolbar button row in a `QFrame#ToolbarHeader`:

- Background: `surface_muted` (`#EEF2F5`)
- Bottom border: `1px solid #D8DEE6`
- Height: stable ~40px
- StatusBadge stays in the toolbar row, separated from action buttons by `addStretch`

Visual result — each page becomes:

```
┌─ ContentPanel ──────────────────────────┐
│  [Refresh] [Import] ...          [Badge]│ ← ToolbarHeader
├─────────────────────────────────────────┤
│  table / editor content (white)         │
└─────────────────────────────────────────┘
```

### Editor: section labels and nested tables

Scenario Editor (`_build_editor_view`) keeps its section-based layout. Improvements:

- Section labels (Overview, Traces & Devices, Routes) use a shared inline style: `font-weight: 600; font-size: 13px; color: #667085`
- Sub-tables (Traces, Devices, Targets, Routes) keep their `maxHeight` for scroll isolation within the editor
- Editor top bar (`Back to list + Validate + Run`) uses the same `ToolbarHeader` frame

### Theme changes

Add to `_stylesheet()`:

```css
QFrame#ContentPanel {
    background: #FFFFFF;
    border: 1px solid #D8DEE6;
}
QFrame#ToolbarHeader {
    background: #EEF2F5;
    border: none;
    border-bottom: 1px solid #D8DEE6;
}
```

### Files changed

| File | Change |
|------|--------|
| `main_window.py` | Wrap `QStackedWidget` in `QFrame#ContentPanel` |
| `theme.py` | Add `QFrame#ContentPanel` and `QFrame#ToolbarHeader` CSS rules |
| `views/trace_library_view.py` | Wrap toolbar in `QFrame#ToolbarHeader` |
| `views/scenarios_view.py` | Wrap list toolbar in `QFrame#ToolbarHeader`; editor top bar uses `ToolbarHeader`; unify section label styles |

### Not changing

- NavigationPanel, InspectorPanel, TopStatusBar — unchanged
- Table styling (`QTableView` CSS) — unchanged
- Color tokens — unchanged
- Button styles — unchanged
- Margins and spacing — unchanged (8px all around, 10px in views)

## Scope

This is a visual-only change. No functional behavior, data flow, ViewModel, or model code is modified.
