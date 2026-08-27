# 科研 Agent 四阶段交接说明

本文件只覆盖：领域调研 → 好问题发现 → 根因分析 → 创新方法设计。默认每个模块独立执行，模块之间只通过稳定的机器交接物传递信息。

```text
/research-lit
  → 人工确认研究范围
  → /idea-creator mode: problem
  → 问题质量 Gate + 问题新颖性 Gate
  → 用户接受问题
  → /idea-creator mode: diagnosis（1a–2b）
  → 独立根因 Gate
  → /idea-creator mode: method
  → 用户选择方法路线
  → /research-refine
  → 最终方法新颖性 Gate
  → 用户接受最终方法
  → 等待用户显式发起验证
```

## 1. 领域调研：`/research-lit`

- 主动检索到的来源先做元数据筛选；只有满足项目批准的顶会或高引用阅读门槛，才可进入 decision-grade 阅读。该门槛只决定主动阅读资格，不证明相关性、正确性或证据等级。
- 用户明确提供的论文、条目或笔记标为 `USER_SUPPLIED_READ`，不受该阅读门槛限制；阅读后仍须单独记录其相关性、证据强度和边界，不能因用户提供而自动成为正式证据。
- 按“领域目的 → 典型任务 → 核心瓶颈 → 方法家族 → 假设/有效条件/失败条件 → 未解决矛盾”建立 Field Evidence Map。
- 关键产物：`idea-stage/SOURCE_ADMISSION_POLICY.yaml`、`idea-stage/ACTIVE_FIELD_MAP.md`、`idea-stage/EVIDENCE_REGISTRY.jsonl`、`idea-stage/SEARCH_LEDGER.jsonl`。
- `INSUFFICIENT` 阻止进入问题生成；`PARTIAL` 必须携带盲点和限制进入后续判断。

## 2. 好问题发现：`/idea-creator "mode: problem"`

- 只读取压缩后的 Field Evidence Map 和必要证据卡。
- 覆盖 community-open、failure/boundary/contradiction、problem migration 三类问题来源。
- 独立问题评审负责 Reality、Importance、Unresolvedness、Precision、Falsifiability、Answerability。
- `/novelty-check mode: problem` 只负责问题新颖性，不负责方法新颖性。
- 关键产物：`PROBLEM_CANDIDATES.*`、问题质量/新颖性 verdict、人工接受后的 `RESEARCH_CONTRACT.md` 和 `PROBLEM_EVIDENCE_CAPSULE.md`。
- 在用户接受问题前，禁止生成方法路线。

## 3. 根因分析：`/idea-creator "mode: diagnosis"`

- 1a–2b 放在同一个可回退的诊断阶段：1a 收集并描述能够直接表征该问题/失效的现象证据，1b 对现象分组，2a 深挖候选原因与替代解释，2b 形成有证据、有反证条件、有干预靶点的因果链。1a 的证据可来自已有实验、文献、数据、真实场景或必要的诊断性 pilot；失败实验不是强制前提。
- 关键产物为 `ROOT_CAUSE_ANALYSIS.json`、忠实的 Markdown 视图和独立评审生成的 `ROOT_CAUSE_VERDICT.json`。
- state 保存上游问题合同、证据胶囊、分析和 verdict 的 ID、SHA-256 与 provenance；任一绑定对象变化都会使交接失效。
- 根因 Gate 只有唯一映射：`DIAGNOSIS_READY → method_design`、`REVISE_DIAGNOSIS → root_cause_analysis`、`REOPEN_PROBLEM → problem_generation`。最后一种情况会重新生成或修订候选问题，并重新经过问题质量、新颖性与人工接受流程。
- 非接受 verdict 由 Controller 的 `return-phase` 按上述固定映射回退，Agent 不能选择目标；旧文件保留审计，但旧 artifact 注册失效，不能继续授权下游。
- 本阶段只定义需要改变的机制和干预靶点，禁止命名、搜索、排序或组合方法。

## 4. 创新方法设计：`/idea-creator "mode: method"`

- 前置条件：问题已由人工接受，并且根因 verdict 为 hash 匹配的 `DIAGNOSIS_READY`。
- 从已验收的 primary causal chains、替代解释和 intervention targets 推导 scientific mainline 与 Design Obligations，再选择一个 dominant method。
- 只搜索能够填补明确 obligation 的 supporting mechanisms；组合本身不是创新结论。
- 输出最多三个初始路线：`METHOD_ROUTES.md`、`METHOD_ROUTES.jsonl`。
- 用户选择路线后，写入 `SELECTED_ROUTE.yaml`；在此之前禁止进入 `/research-refine`。

## 5. Refinement 与最终判断

- `/research-refine` 只接受人工接受的问题、已验收的根因交接和 `SELECTED_ROUTE.yaml`。
- 必须产生 `FINAL_PROPOSAL.md`、`FINAL_BLIND_REVIEW.md` 和 refinement 状态文件。
- 最终方法新颖性必须基于 `FINAL_PROPOSAL.md`，不能用初始路线评审或迭代分数替代。
- `research-review` 是可选挑战，不是默认的重复 Gate。

## 6. 执行层硬约束

工作流定义位于 `skills/shared-references/idea-workflow.yaml`，正式状态转换由 `arisctl.controller.ARISController` 统一管理；`tools/run_state.py` 不是 Controller-managed run 的平行跳转通道：

- formal Gate 具有唯一 `gate_id` 和 `gate_owner`；
- 人工确认使用 `approve`，不能由模型 `accept --force` 冒充；
- 依赖未终止、必需输入缺失或必需交接物缺失时，阶段不能启动或完成；
- 根因分析与 verdict 必须通过 schema、引用完整性及 ID/hash 绑定校验，方法阶段会重验快照，不能靠 prompt 补造；
- 上下文默认使用路径和稳定 ID 传递，活动包约 24,000 字符、评审包约 32,000 字符，历史记录不整体注入。

`IDEA_REPORT.md` 仅是最终人类报告，不是模块之间的状态数据库。

最终方法经用户理解并确认后，状态停留在 `METHOD_CONFIRMED_AWAITING_USER_VALIDATION`。验证不会自动开始，只能由用户显式发起。
