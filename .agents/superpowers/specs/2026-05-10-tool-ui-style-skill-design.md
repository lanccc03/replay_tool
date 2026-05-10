# Tool UI Style Skill Design

## Purpose

Create a reusable Codex skill for designing, implementing, and reviewing UI for team-internal tools. The skill should apply to engineering tools, debugging tools, data inspection tools, QA tools, test benches, operations consoles, and other workbench-style applications.

The skill should not be tied to `next_replay`, PySide6, or a single visual skin. It should provide a medium-strength style system: strong enough to shape layout, component choices, state language, and review criteria, but flexible enough for each project to keep its own framework, component library, and product-specific details.

## Scope

The skill covers:

- Tool UI personality: calm, reliable, dense, scannable, precise.
- Layout patterns for workbench-style tools.
- Component rules for navigation, toolbars, tables, forms, inspectors, logs, status badges, dialogs, and empty states.
- Visual-system defaults for color roles, typography, spacing, radius, and state colors.
- Review and delivery checklist for UI implementation tasks.

The skill does not provide framework-specific code templates in its first version. It should tell Codex to inspect the current project's existing UI docs, screenshots, component library, and tests before applying the default guidance.

## Recommended Shape

Use a compact `SKILL.md` plus focused reference files:

- `SKILL.md`: trigger description, workflow, project-context discovery, and required review steps.
- `references/tool-ui-principles.md`: personality, information density, state language, and prohibited patterns.
- `references/layout-patterns.md`: workbench layout patterns and when to use them.
- `references/component-rules.md`: practical rules for common tool UI components.
- `references/visual-system.md`: default visual baseline and customization boundaries.
- `references/review-checklist.md`: pre-delivery checks for implementation and review.

## Operating Rules

When the skill is used, Codex should:

1. Read project-local UI guidance first when it exists.
2. Preserve existing framework and design-system conventions.
3. Use the skill defaults only when the project has no stronger local rule.
4. Avoid marketing-page patterns, decorative hero sections, decorative gradients, and oversized typography for tool surfaces.
5. Keep unavailable capabilities disabled, hidden, or explicitly marked as not connected.
6. Verify that critical states, errors, and destructive actions are visible, understandable, and testable.

## Validation

Validate the skill structurally with `quick_validate.py`. Manual validation should include reading the skill as a fresh agent would and checking that the trigger description is broad enough for tool UI work but narrow enough to avoid general marketing sites or consumer apps.
