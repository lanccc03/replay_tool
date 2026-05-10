@AGENTS.md

# Claude Code 专属指令

## ExecPlans

复杂功能、显著重构或高风险迁移必须从设计阶段开始编写并维护 ExecPlan。格式、必备章节和维护规则以 `.agents/PLANS.md` 为准。ExecPlan 必须自包含、持续更新、可供新手按步骤执行。

## 验证与交付

完成所有改动后必须运行对应范围的验证（具体命令见 AGENTS.md 测试章节），并在最终说明中写清：

- 已验证什么
- 未验证什么
- 是否未做 Windows 硬件验证

Mock/Fake 测试通过不等于真机验证通过。同星 TC1014 真机验证需按 `docs/tongxing-hardware-validation.md` 手工记录。
