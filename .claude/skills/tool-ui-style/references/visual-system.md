# Visual System

## Use Project Tokens First

Use the project's existing design tokens, theme files, CSS variables, Qt palettes, component library, or screenshots before applying this default baseline. The defaults below are a fallback for projects without a local visual system.

## Default Theme Direction

Use a light, neutral engineering theme by default. Dark themes are useful for some tools, but they require separate validation for table readability, contrast, charts, code/log output, and high-DPI rendering.

Recommended default roles:

| Role | Default | Use |
| --- | --- | --- |
| App background | `#F6F7F9` | Window and page background |
| Surface | `#FFFFFF` | Tables, panels, dialogs |
| Surface muted | `#EEF2F5` | Headers, toolbars, grouped areas |
| Border | `#D8DEE6` | Dividers, table lines, input borders |
| Text primary | `#1F2933` | Body text and primary values |
| Text secondary | `#667085` | Metadata, helper text, paths |
| Text disabled | `#98A2B3` | Disabled labels and unavailable features |
| Primary | `#087F8C` | Current selection and main action |
| Primary hover | `#066C77` | Hover or active primary state |
| Primary subtle | `#DDF4F2` | Selected rows and subtle emphasis |
| Link/relation | `#3B5BDB` | Links and object relationships |
| Success | `#178C55` | Connected, passed, complete |
| Warning | `#B7791F` | Partial, missing, attention needed |
| Danger | `#C2410C` | Failed, invalid, destructive |
| Focus ring | `#7DD3FC` | Keyboard focus |

Use these as roles, not decoration. One primary accent is enough for most tools.

## Color Rules

- Keep large surfaces neutral.
- Use primary color for selected/current objects and the main action.
- Use semantic colors only for semantic states.
- Avoid single-hue UIs dominated by one color family.
- Avoid decorative purple gradients, dark blue dashboard backgrounds, beige editorial themes, and glow effects unless a project-specific design system requires them.
- Ensure text contrast is readable in tables, forms, badges, and disabled states.

## Typography

Use system UI fonts unless the project already defines typography.

Defaults:

- UI text: system sans-serif.
- Technical values: monospace for IDs, timestamps, paths, hashes, addresses, codes, and payloads.
- Body text: 13px or 14px equivalent.
- Dense tables: 12px or 13px equivalent.
- Panel titles: 15px or 16px equivalent.
- Page titles: 18px to 20px equivalent.

Avoid hero-scale type inside tools. Do not scale type with viewport width.

## Spacing and Density

Use an 8px spacing base. Internal tools benefit from predictable density:

- Toolbar height: about 36px to 44px.
- Table row height: about 28px to 36px.
- Inspector field height: about 32px to 36px.
- Panel padding: usually 8px, 12px, or 16px.
- Section gaps: large enough to separate groups, not so large that comparison is hard.

Use stable dimensions for toolbars, tables, controls, badges, and counters so hover states and dynamic values do not shift layout.

## Radius, Borders, and Shadows

Use restrained shaping:

- Radius: usually 4px to 8px.
- Borders: use clear separators for dense content.
- Shadows: use sparingly for dialogs, menus, popovers, and overlays.
- Cards: use only for repeated items, modals, summary blocks, or genuinely framed tools.

Do not put cards inside cards. Do not style every page section as a floating card.

## Icons

Use the project's existing icon library. Prefer familiar symbols for common commands: save, refresh, run, pause, stop, search, filter, settings, copy, delete, download, upload, expand, collapse.

Icon-only controls need accessible labels or tooltips. Icons must not be the only state indicator for critical information.
