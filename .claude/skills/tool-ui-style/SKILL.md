---
name: tool-ui-style
description: Use when designing, implementing, or reviewing UI for internal tools — engineering workbenches, debug tools, data inspectors, desktop apps. Do not use for marketing sites, consumer apps, or brand pages.
---

# Tool UI Style

Team-shared baseline for internal tool UIs. Project-local rules (e.g. `docs/ui.md`) take precedence over this skill.

## Workflow

1. **Inspect the project first.** Look for existing UI docs, design tokens, theme files, component libraries, and current screens. Preserve established patterns unless they conflict with the user request.
2. **Read the references you need.** See the Reference Map below — not every task needs every file.
3. **Apply the priority hierarchy:**
   - User instructions (highest).
   - Project-specific UI docs (`docs/ui.md`).
   - This skill.
   - Framework conventions (PySide6/Qt, existing `replay_ui_qt` code).
4. **Design for operational clarity.** Current data, selection, job, and error states must be visible. Unavailable capabilities must be hidden, disabled, or clearly marked — never made to look ready.
5. **Verify before claiming done.** Run relevant UI tests. Inspect the rendered result when feasible. State what was verified and what was not.

## Default stance

Build the working surface first. Use restrained hierarchy, stable dimensions, clear affordances, and semantic state indicators. Avoid marketing composition, decorative gradients, hero typography, ornamental illustrations, nested cards, and color-only status indicators.

## Reference map

- `references/tool-ui-principles.md` — product personality, first-screen rules, state language, error handling, destructive actions, anti-patterns.
- `references/layout-patterns.md` — workbench shell, navigation, tables/editors/split-panes/timelines, inspector placement, empty states, responsive behavior.
- `references/component-rules.md` — toolbars, buttons, tables, forms, inspectors, status badges, dialogs, tabs.
- `references/visual-system.md` — color roles, typography, spacing/density, radius/borders/shadows, icons.
- `references/review-checklist.md` — pre-delivery checks organized by context, workflow, layout, components, visual, and verification.
