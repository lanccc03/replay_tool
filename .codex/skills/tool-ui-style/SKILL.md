---
name: tool-ui-style
description: Medium-strength style guidance for team-internal tool UIs and workbench applications. Use when Codex designs, implements, modifies, or reviews UI/UX, layout, components, styling, states, accessibility, or UI documentation for engineering tools, debugging tools, data inspection tools, QA tools, operations consoles, developer dashboards, desktop workbenches, or similar internal tools. Do not use for marketing sites, consumer apps, brand pages, games, or purely visual artwork unless the user explicitly asks to apply internal-tool UI rules.
---

# Tool UI Style

## Overview

Use this skill to make internal tools feel calm, precise, dense, and reliable. Treat it as a shared style baseline, not a framework or brand system: project-local design docs, component libraries, screenshots, and user instructions override these defaults.

## Workflow

1. Inspect the current project before designing or editing UI.
   - Look for UI docs, design tokens, component libraries, screenshots, Storybook, visual tests, smoke tests, and existing screens.
   - Identify the platform: web, Qt, Electron, Tauri, native desktop, terminal UI, or another stack.
   - Preserve established local patterns unless they conflict with the user request or make the tool harder to use.

2. Choose the references needed for the task.
   - Read `references/tool-ui-principles.md` for product personality, state language, information density, and prohibited patterns.
   - Read `references/layout-patterns.md` when creating or changing screen structure, navigation, panels, inspectors, logs, or responsive behavior.
   - Read `references/component-rules.md` when implementing controls, tables, forms, dialogs, status badges, empty states, charts, or toolbars.
   - Read `references/visual-system.md` when choosing colors, typography, spacing, radius, icon treatment, or density.
   - Read `references/review-checklist.md` before final delivery or when performing a UI review.

3. Apply the style hierarchy.
   - User instructions and project-specific UI guidance take precedence.
   - Existing framework conventions take precedence over invented components.
   - Use this skill's defaults where the project has no stronger rule.
   - Keep the first screen focused on the actual tool, not a landing page or promotional hero.

4. Design for operational clarity.
   - Make current data, selection, workspace, connection, job, validation, and error states visible.
   - Prefer tables, split panes, inspectors, logs, timelines, trees, and compact controls over decorative cards.
   - Show unavailable capabilities as hidden, disabled, or clearly not connected; never make them look ready.
   - Confirm destructive actions with the affected object name or ID.

5. Verify before completion.
   - Run the project's relevant UI tests, type checks, lint checks, smoke tests, or visual checks.
   - For frontend or desktop UI changes, inspect the rendered result with the available browser, screenshot, offscreen, or manual verification workflow when feasible.
   - State what was verified and what remains unverified.

## Default Stance

Build the working surface first. Use restrained hierarchy, stable dimensions, clear affordances, and semantic state indicators. Avoid marketing composition, decorative gradient backgrounds, hero-scale typography, ornamental illustrations, nested cards, and status indicators that rely on color alone.

## Reference Map

- `references/tool-ui-principles.md`: core product qualities and anti-patterns.
- `references/layout-patterns.md`: screen structures for workbench-style tools.
- `references/component-rules.md`: practical component behavior and state rules.
- `references/visual-system.md`: default visual baseline and customization boundaries.
- `references/review-checklist.md`: final checks for implementation and review.
