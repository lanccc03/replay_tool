# next_replay 文档导航

本目录保存 `next_replay` 的工程说明、验证步骤和后续演进约束。

- `architecture-design-guide.md`：架构边界、分层职责、数据流和演进路线。
- `ui-style-guide.md`：PySide6 工作台的界面风格、色彩、布局和组件规则。
- `testing.md`：本项目的自动化测试、CLI 验证和硬件验证边界。
- `tongxing-hardware-validation.md`：Windows + TSMaster + TC1014 真机手工验证记录模板。

`next_replay` 已迁移为 `C:\code\next_replay` 下的独立项目。同星 SDK 随项目放在 `TSMaster/Windows`，默认不再引用旧 `replay` 项目的 `TSMasterApi/`。
