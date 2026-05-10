# Tool UI Principles

## Product Personality

Internal tools should feel quiet, trustworthy, and fast to scan. They are used repeatedly by people trying to inspect data, operate systems, debug failures, validate work, or make careful changes. Optimize for clarity under pressure rather than novelty.

Use these qualities as the default:

- Precise: values, statuses, timestamps, IDs, paths, and selected objects are unambiguous.
- Reliable: errors, unavailable features, background work, and destructive actions are explicit.
- Quiet: color, motion, illustration, and shadows support comprehension instead of competing with the task.
- Dense: the UI shows enough context for comparison and repeated work without feeling cramped.
- Scannable: alignment, grouping, labels, and stable dimensions make important differences visible.

## First Screen

Show the real working surface as the first screen whenever possible. Prefer a table, inspector, query surface, job monitor, device list, trace view, log viewer, dashboard, editor, or configuration panel over a landing page.

Use onboarding or welcome content only when the tool cannot function until setup is complete. Even then, keep setup direct and action-oriented.

## State Language

Make states short, stable, and semantic. Prefer labels such as `Ready`, `Running`, `Paused`, `Failed`, `Missing`, `Disconnected`, `Valid`, `Invalid`, `Queued`, `Syncing`, or domain-specific equivalents.

Rules:

- Pair color with text or icons; never rely on color alone.
- Keep state labels consistent across pages.
- Show the cause or next action near failed, blocked, or invalid states.
- Separate user-facing state from implementation details unless the user needs the technical detail.
- Keep progress, busy, and disabled states visible during long-running operations.

## Unavailable Capabilities

Do not present unfinished or unsupported features as usable. Choose one of these treatments:

- Hide features that are not relevant yet.
- Disable features that users can see but cannot use, with a tooltip or short reason.
- Mark future integrations as `Not connected`, `Not configured`, or `Unavailable`.

Do not create clickable controls that lead only to dead ends.

## Error Handling

Errors should be visible where they affect the user's work:

- Field errors belong near the field.
- Row errors belong in the row and in the details panel.
- Job errors belong in the job monitor or log panel.
- System errors should include a copyable detail view when the message may be useful for debugging.

Avoid vague errors such as "Something went wrong" unless paired with a technical detail, recovery action, or traceable ID.

## Destructive Actions

Dangerous actions require confirmation when they delete, overwrite, disconnect, stop a run, clear state, or change external systems. Confirmation text must include the affected object name, ID, path, environment, or target.

Use danger color sparingly. A stop action can be serious without looking like delete. Reserve the strongest danger treatment for destructive or irreversible operations.

## Anti-Patterns

Avoid these patterns for internal tools:

- Marketing-style landing pages, hero sections, or product-pitch copy.
- Decorative gradients, glow effects, background blobs, and ornamental illustrations.
- Oversized typography inside panels, cards, toolbars, or dense controls.
- Card grids where a table, split view, tree, or inspector would work better.
- Nested cards inside cards.
- Status conveyed only through color.
- Layouts that shift when values, badges, or hover states change.
- Long instructional text inside the primary working surface.
- Unclear disabled states or disabled controls without a reason.
