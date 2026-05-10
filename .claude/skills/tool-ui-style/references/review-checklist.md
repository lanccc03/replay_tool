# Review Checklist

Use this checklist before completing a tool UI implementation or review.

## Context

- Project-local UI guidance, design tokens, screenshots, and component patterns were checked.
- The implementation follows the existing framework and component library.
- New abstractions are justified by repeated use or real complexity.

## Workflow

- The first screen is a working tool surface, not a marketing page.
- Primary workflows are reachable without unnecessary explanation.
- Busy, loading, empty, disabled, success, warning, and error states exist where needed.
- Unavailable features are hidden, disabled, or clearly marked as not connected.
- Destructive actions confirm the affected object name, ID, path, or environment.

## Layout

- Navigation, main workspace, inspector/details, and logs have clear roles.
- Tables, split panes, inspectors, or timelines are used where they fit better than card grids.
- Text does not overlap or spill out of buttons, fields, tables, badges, or panels.
- Dynamic values, hover states, and badges do not resize or shift core layout.
- Narrow or constrained layouts have a defined fallback.

## Components

- Icon-only buttons have tooltips or accessible labels.
- Status indicators use text or icons in addition to color.
- Long IDs, paths, timestamps, hashes, and technical values are readable and copyable where useful.
- Field validation appears near the relevant field.
- Dialogs are focused and include clear action labels.

## Visual System

- Colors are semantic and restrained.
- Large surfaces are neutral.
- The UI is not dominated by a decorative single-color palette.
- Typography is proportional to the component context.
- Spacing and row density support scanning and comparison.
- Focus states are visible.

## Verification

- Relevant unit, component, ViewModel, smoke, lint, type, or visual tests were run.
- Rendered UI was inspected with the available browser, screenshot, offscreen, or manual workflow when feasible.
- Known gaps are stated explicitly, including unverified high-DPI, keyboard, accessibility, browser, platform, or hardware behavior.
