# next_replay Agent 指南

本文件记录工程代理进入 `next_replay` 前必须知道的约束。项目背景和架构细节请先看 `README.md`、`docs/README.md` 与 `docs/architecture-design-guide.md`。

## 1. 开始前先读

- 必读：
  - `README.md`
  - `docs/README.md`
  - `docs/architecture-design-guide.md`
  - `docs/testing.md`
  - `src/replay_tool/domain/model.py`
  - `src/replay_tool/planning/plan.py`
  - `src/replay_tool/runtime/engine.py`
  - `src/replay_tool/app/service.py`
  - `src/replay_tool/cli.py`
- 按任务补读：
  - 同星 / TSMaster：`src/replay_tool/adapters/tongxing/device.py`、`docs/tongxing-hardware-validation.md`
  - Trace Library：`src/replay_tool/storage/trace_store.py`、`src/replay_tool/ports/trace_store.py`
  - 执行计划：`.agents/PLANS.md`

## 2. 不要越界

- `next_replay` 是独立项目，不要从旧项目 `C:\code\replay\src\replay_platform` import 模块。
- 同星 SDK 已迁入本项目，默认路径是 `TSMaster/Windows`；不要再依赖旧项目根目录下的 `TSMasterApi/`。
- 同星真机能力只能在 Windows + TSMaster + 实际设备上验证；自动化 fake API 测试不等同于硬件联调。
- 当前 MVP 只覆盖 CLI、Mock、同星适配器、ASC 读取和 Trace Library v1；不要把 DBC、DoIP、ZLG 或 Qt UI 写成已完成能力。
- 源码、文档、配置文件默认 UTF-8 保存；中文文本不要转成 GBK / ANSI，也不要无意引入 UTF-8 BOM。
- 不要提交或依赖 `.venv`、`.replay_tool`、`__pycache__`、临时 pycache 目录。

## 3. 改动原则

- 先沿现有 ports-and-adapters 架构扩展，不平白增加新抽象层。
- `domain` 保持纯数据和纯逻辑，不依赖文件系统、SQLite、TSMaster、Qt 或外部 SDK。
- `runtime` 只执行 `ReplayPlan`，不要让运行时重新解释原始 Scenario。
- 设备能力先定义 port，再写 adapter；测试优先使用 fake SDK 或 mock device。
- 新增或修改公共函数 / 方法时，必须添加或维护 Google 风格 docstring，说明 Args、Returns、Raises 等适用信息。
- 涉及复杂功能、显著重构或高风险迁移时，遵守第 4 节 ExecPlans 规则。

## 4. ExecPlans

- When writing complex features or significant refactors, use an ExecPlan (as described in `.agents/PLANS.md`) from design to implementation.
- 涉及复杂功能、显著重构或高风险迁移时，必须从设计阶段开始编写并持续维护 ExecPlan；格式、必备章节和维护规则以 `.agents/PLANS.md` 为准。

## 5. 验证与交付

- 详细命令见 `docs/testing.md`。
- 运行时 / 解析 / 适配器 / Trace Library 改动至少运行：
  - `python -m compileall src tests`
  - `python -m unittest discover -s tests -v`
- 同星真机验证需按 `docs/tongxing-hardware-validation.md` 手工记录；未执行时必须在交付说明中明确未验证。
- 最终说明必须写清：
  - 已验证什么
  - 未验证什么
  - 是否未做 Windows 硬件验证
