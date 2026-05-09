# Component Rules

## Command Bars and Toolbars

Toolbars should contain frequent, context-specific actions. Put destructive or rare actions behind confirmation or secondary menus.

Rules:

- Use one primary action per local context when possible.
- Use icon buttons for common tool actions when an established icon exists.
- Provide tooltips for icon-only buttons.
- Disable actions during incompatible busy states and show why when useful.
- Keep command order stable.

## Buttons and Controls

Choose controls by data type:

- Binary settings: checkbox, switch, or toggle.
- Mutually exclusive modes: segmented control or radio group.
- Known option set: select, combobox, menu, or autocomplete.
- Numeric values: number input, stepper, or slider when range matters.
- Paths and files: path field plus browse action.
- Repeated command groups: toolbar or menu.

Do not use a styled text pill when a standard control communicates the behavior better.

## Tables

Tables are the default for comparable operational data.

Rules:

- Keep column widths stable.
- Use fixed headers for long tables when available.
- Make sort, filter, selection, and row expansion states explicit.
- Use monospaced text for IDs, timestamps, addresses, paths, hashes, payloads, and numeric codes.
- Truncate long paths or values in the middle when needed, and expose the full value in an inspector, tooltip, or copy action.
- Keep row hover and selected states from changing row height.
- Include text or icons with status colors.

## Forms

Forms in tools should be compact and explicit.

Rules:

- Group fields by operational meaning, not by visual symmetry.
- Put validation errors near the relevant field.
- Use helper text only when it prevents mistakes.
- Mark required fields clearly.
- Keep read-only technical values copyable.
- Prevent invalid operations early when doing so is reliable.

## Inspectors

Inspectors should make the selected object understandable without opening a modal.

Use inspectors for:

- Object metadata.
- Validation and warnings.
- Small scoped edits.
- Source/target mappings.
- Copyable IDs and paths.
- Secondary actions tied to the selection.

Avoid using an inspector as a dumping ground for every field. Prioritize what helps the current workflow.

## Status Badges

Status badges should be semantic and restrained.

Rules:

- Use short text.
- Pair color with label or icon.
- Use neutral badges for metadata and semantic colors for state.
- Do not decorate ordinary labels with strong color.
- Keep badge dimensions stable.

## Dialogs

Use dialogs for confirmation, focused creation, and short tasks that block the current flow. Avoid large multi-step workflows in modals unless the rest of the UI must remain unchanged.

Danger confirmations should include:

- Action name.
- Affected object name or ID.
- Consequence.
- Explicit confirm button text.

## Tabs

Use tabs when views are peers over the same object or workflow. Do not use tabs to hide unrelated modules; use navigation for that.

Keep tab labels short. Preserve unsaved state when switching tabs unless the project has a clear reason not to.

## Charts and Visualizations

Use charts when they answer a specific operational question. Prefer precise axes, readable legends, direct labels, and useful hover or selection details.

Avoid decorative charts, unlabeled sparklines, and visualizations that obscure exact values users need for debugging or validation.
