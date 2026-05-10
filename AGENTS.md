# next_replay — Agent 指南

本文件是仓库的跨工具 Agent 指令集，面向 Claude Code、Copilot、Codex 等编码代理。人类文档见 `docs/README.md`。

## 命令

```bash
uv sync                                              # 安装依赖
uv run ruff check src tests                          # Lint
uv run python -m compileall src tests                # 语法检查
uv run python -m unittest discover -s tests -v       # 运行全部测试
uv run replay-ui --help                              # UI 入口冒烟测试
```

单文件测试：
```bash
uv run python -m unittest tests.test_ui_views -v
```

## 架构

六边形 / ports-and-adapters 单体。依赖方向：

```
CLI / PySide6 UI → app → planning + runtime + domain → ports（仅接口）
adapters → ports + domain
storage  → ports + domain
```

| 层 | 路径 | 职责 |
|---|------|------|
| domain | `src/replay_tool/domain/model.py` | 纯数据类：Frame, ReplayScenario, DeviceConfig 等 |
| planning | `src/replay_tool/planning/plan.py` | Scenario → ReplayPlan 编译 |
| runtime | `src/replay_tool/runtime/` | 执行 ReplayPlan（kernel/scheduler/dispatcher） |
| ports | `src/replay_tool/ports/` | 抽象接口：BusDevice, TraceStore, ProjectStore |
| adapters | `src/replay_tool/adapters/` | mock（假设备）、tongxing（TSMaster SDK） |
| storage | `src/replay_tool/storage/` | ASC 解析、二进制缓存、SQLite 存储 |
| app | `src/replay_tool/app/service.py` | ReplayApplication：CLI 和 UI 共用的用例门面 |

PySide6 UI：MVVM 模式，`views/`（Qt widgets）→ `view_models/`（BaseViewModel）→ `app_context.py`（ReplayApplication）。详细架构见 `docs/architecture-design-guide.md`。

## 边界

**始终执行：**
- 新增/修改公共类必须写类级 docstring；公共函数/方法必须写 Google 风格 docstring（Args, Returns, Raises）
- 源码、文档、配置文件默认 UTF-8 无 BOM
- domain 保持纯数据/纯逻辑，不依赖文件系统、SQLite、TSMaster、Qt
- runtime 只执行 ReplayPlan，不在运行时重新解释原始 Scenario
- 先沿现有 ports-and-adapters 架构扩展，不平白增加新抽象层

**先询问：**
- 新增依赖（修改 pyproject.toml）
- schema 变更（影响 Scenario 兼容性）
- 涉及 CI/CD 配置的修改

**绝不：**
- 从旧项目 `replay_platform` import 模块
- UI 中直接 import 硬件 adapter 或操作 ReplayRuntime 内部字段
- 提交 `.venv`、`.replay_tool`、`__pycache__`、临时 pycache 目录
- 把 Mock/Fake 测试结果当作 Windows 真机验证结果

## 代码风格

- 仅支持 `schema_version: 2` 场景文件，v1 拒绝且无迁移路径
- 同星 SDK 位于 `TSMaster/Windows/`，通过 `importlib` 动态导入
- ASC 解析要求时间戳单调递增，不对外部乱序文件排序
- 测试框架为 `unittest`（非 pytest），不使用 pytest 依赖
- 设备能力先定义 port，再写 adapter；测试优先使用 fake SDK 或 mock device

## 测试

详细命令见 `docs/testing.md`。最低验证范围：

| 改动范围 | 必须运行 |
|---------|---------|
| 运行时/解析/适配器/Trace Library | `ruff check` + `compileall` + 全量 unittest |
| PySide6 UI | 上述 + `replay-ui --help` + 对应 ViewModel/widget/smoke test |
| 纯文档 | `git diff --check` |

自动化测试使用 Mock 设备和 fake TSMaster API，不等同于 Windows 真机验证。同星真机验证必须按 `docs/tongxing-hardware-validation.md` 手工记录，未执行时必须在交付说明中明确标注。

## Git 工作流

- 分支命名：`feat/`、`fix/`、`refactor/`、`docs/`、`chore/`
- 提交信息：conventional commits（`feat:`, `fix:`, `refactor:`, `docs:` 等）
- 一个 PR 一个逻辑变更，squash merge
- 复杂功能、显著重构或高风险迁移必须先写 ExecPlan（格式见 `.agents/PLANS.md`），从设计到实现持续维护

## 领域指南

按需阅读，不随 AGENTS.md 加载到每次会话的上下文：

- `docs/architecture-design-guide.md` — 架构边界、分层职责、数据流和演进路线
- `docs/testing.md` — 自动化测试、CLI 验证和硬件验证边界
- `docs/ui-style-guide.md` — PySide6 工作台 UI 专属视觉规则
- `docs/ui-implementation-roadmap.md` — UI 长期实现路线和阶段验收
- `docs/tongxing-hardware-validation.md` — Windows + TSMaster 真机手工验证模板
