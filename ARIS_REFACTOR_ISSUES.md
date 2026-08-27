# ARIS Harness 按序修改清单

本文档是后续 AI Agent 修改 ARIS Harness 的唯一问题基准。必须从 P01 开始按编号顺序逐项修改；每轮只处理当前一项，提交修改日志并等待用户验收。当前项验收合格后，才能进入下一项。

核验与修改必须同时以以下内容为准：

- 科研流程：`../harness-design-notes/科研问题发现与创新方法设计方法论.txt`；
- Harness 约束：`AGENTS.md`、canonical `idea-workflow.yaml`、Controller、Hook、State、Artifact、Validator、Skill、模板和测试；
- 当前真实实现：不得默认本文描述正确，修改前仍须核对对应代码；若代码已变化，应以可复现事实修正当前项，不得扩张任务范围。

## 统一修改准则

1. 提示词简洁、准确、最小充分。
2. 修改必须遵循既定科研流程/科研方法论，同时遵循当前 Harness 的架构、写作规范和核心机制。
3. 按需使用 Gate、Hook、State、Artifact、Validator 或其他现有机制，不无故增加模块、状态、产物、审核层或复杂度。
4. 只做当前问题所需的最小修改，但必须自然融入现有 Harness；不顺带重构无关代码，不提前实现后续编号。
5. Type-A 结构、ID、hash、枚举和状态约束由现有机械机制负责；Reality、Importance、Unresolvedness、因果充分性、方法价值等 Type-B 科研判断仍由 Main、独立 Reviewer 或 Human 完成。
6. 修改后必须验证：当前问题确实解决、正常流程未损坏、负向和恢复路径可执行、没有引入新的硬伤或旁路。
7. 将本轮 Codex 修改日志交给用户验收；不合格继续修改当前项，合格后再进入下一项。
8. 每轮在 `ARIS_REFACTOR_PROGRESS.md` 末尾追加总体进度；本轮详细日志覆写 `CURRENT_REVISION.md`。

### P01 接通正式 Reviewer 的执行与 attestation 通道

**涉及位置**：`.codex/config.toml`、`.codex/hooks.json`、`.codex/hooks/subagent_attestation.py`、`arisctl/reviews.py`、相关 Controller 路由和测试。

**真实问题**：canonical workflow 要求 `independent_problem_reviewer`、`independent_novelty_reviewer`、`independent_root_cause_reviewer` 和 `independent_method_reviewer`，但当前只注册 `paper_reader`、`coverage_reviewer`，`SubagentStop` matcher 也只覆盖这两个角色。正式 Reviewer 无法稳定走完 routing → hook → attestation → Controller 消费链。Hook 还在模块顶层导入 `arisctl.reviews`，自身没有解析仓库根目录；当前机器依靠额外的 editable install 才能导入，未安装该包的 Hook Python 会在写证明前失败。

**修改要求**：接通上述现有 Reviewer role 与 Controller-issued review request；复用现有一次性 attestation 契约和消费入口。Hook 必须能从当前 checkout 稳定解析现有 `arisctl`，不能依赖未声明的 editable install。不得新增第二套 Reviewer、receipt、Gate 或审核服务。

**完成标准**：各正式 Reviewer Gate 都能由声明的角色产生并消费匹配当前 request 的 attestation；干净运行环境中的实际 Hook 命令可执行；错误角色、request、hash 或 verdict 仍被拒绝；现有 `paper_reader` 和 `coverage_reviewer` 流程不回归。

### P02 闭合 Reviewer 被审版本、attestation 与 verdict artifact

**涉及位置**：`arisctl/controller.py::_register_phase_outputs`、`accept_current_phase`、`tools/run_state.py::_assert_outputs`、`_assert_acceptance_matches_gate`，以及 problem quality、problem novelty、method refinement、final method novelty Gate。

**真实问题**：除 landscape 和 root-cause 外，Reviewer Gate 主要只检查输出文件存在；无法证明落盘 verdict 与 attestation 中的 reviewer、decision、request 和被审 hash 一致。尤其 method refinement request 没有绑定其输出的 `FINAL_PROPOSAL.md`，因此不能证明 method reviewer 审过最终版本。Final method novelty request 已绑定 `FINAL_PROPOSAL.md`，但 attestation 结论仍未与 `FINAL_METHOD_NOVELTY_VERDICT.md` 内容闭合。逐候选 verdict 与 phase-level decision 的汇总关系及相关 verdict 词汇也不统一。

**修改要求**：复用现有 review request、attestation、artifact 和 Validator，补齐最小关联字段与解析规则，机械校验 request ID、Reviewer、decision、被审 artifact hash 和落盘 verdict 一致。Method review 必须绑定最终 proposal hash；逐候选 verdict 到 phase decision 只能有一套明确规则和词汇。不得新增第二套 verdict 文件或审核机制。

**完成标准**：Controller 能确定“哪个 Reviewer 对哪个 artifact 版本作出什么 verdict”；替换、篡改或错配任一版本、request、Reviewer 或 verdict 都不能被接受；现有正常审核链仍可通过。

### P03 修复一次性 Reviewer/Human 证明的不可恢复消费

**涉及位置**：`arisctl/approvals.py::consume_ui_approval_receipt`、`arisctl/reviews.py::consume_review_attestation`、`arisctl/state.py::_StateStore.mutate`，以及 Controller 中所有消费这些证明的动作。

**真实问题**：当前 `consume_*` 会立即把证明改名为 `.consumed.json`，而 run state 只在 mutation 正常退出后保存。Human receipt 会在进入 mutation 前消费；Reviewer acceptance/return 和 coverage review 也会在部分后置校验、归档或状态提交前消费。后续步骤失败时，run 仍停在原 request，但一次性证明已经丢失，无法安全重试。

**修改要求**：复用现有 request ID、receipt/attestation 和 consumed marker，调整校验、消费和状态提交语义，使失败后可安全重试同一 live request，成功后同一证明仍只能使用一次。不得新增第二套证明或通用事务系统。

**完成标准**：Human 产物缺失、Reviewer family 不合法、coverage audit 失败或状态保存失败等后置失败不会永久烧毁当前证明；重试能恢复；成功提交后重复使用仍被拒绝。

### P04 为正式 Reviewer 负向 verdict 配置可执行回退

**涉及位置**：canonical `idea-workflow.yaml`、`arisctl/controller.py::allowed_actions`、`return_current_phase` 和各 Reviewer Gate 合同。

**真实问题**：只有 `root_cause_gate` 声明 `return_targets`。Problem quality、problem novelty、method refinement 和 final method novelty 合同允许的必要负向结论没有 workflow mapping；Reviewer 给出非接受结论后，phase 可停在 `done`，但 Controller 无法合法回退。

**修改要求**：在 P02 统一 verdict 语义后，只为确实需要跨 phase 处理的负向 verdict 配置唯一、固定的已有 phase target，复用现有 `return_current_phase`、archive、artifact invalidation 和 problem-version 机制。Phase 内即可修订的情况不增加跨阶段回退。

**完成标准**：每个正式允许的负向 verdict 都有唯一合法行为；需要回退时能归档/失效正确的后代产物并恢复目标 phase；不存在死锁、自由选择 target 或平行 rollback 状态机。

### P05 为 Human Gate 配置拒绝和修订路径

**涉及位置**：`arisctl/controller.py::allowed_actions`、`human_approve`、canonical workflow 的 Human Gate，以及直接相关 Skill。

**真实问题**：scientific core 的 scope、problem acceptance、route selection 和 final method acceptance Gate 只暴露接受动作，`human_approve` 也强制 decision 为 `approve`。用户拒绝、要求重构问题、修改路线或修订最终方法时，没有可记录的正式迁移；`revise_problem` 又只能在问题已经接受后使用。

**修改要求**：为现有 Human Gate 声明必要且唯一的非接受 decision 及固定返回目标，继续复用 live request、artifact binding、selection、UI receipt、archive 和 invalidation。不得新增 Human Gate 或允许调用者自由指定 target。

**完成标准**：每个 Human Gate 的接受、拒绝或修订决定均可正式记录和执行；返回目标与失效范围固定且正确；旧 receipt、错误 selection 或已变化 artifact 仍不能通过。

### P06 为 scientific core 接入正式增量文献检索

**涉及位置**：`AGENTS.md`、canonical workflow、Controller 的 query/admission/read stage guard，`novelty-check`、`idea-creator`、`research-refine` 和 method design 合同。

**真实问题**：research-lit 到 `LANDSCAPE_ACCEPTED` 后，Controller 的 query、admission 和 full-text 动作仍只允许早期 research-lit stage，scientific core 没有合法文献动作。但问题查新、方法迁移/refinement 和最终方法查新都要求针对当前 claim 或 route 继续检索；相关 Skill 直接使用 `WebSearch/WebFetch` 又违反正式文献必须经 Controller gateway 的边界。

**修改要求**：让确有需要的 problem novelty、method search/refinement 和 final novelty 定向检索复用现有 Controller gateway、source policy、ledger、paper-reader 和 evidence registry，并把新增 evidence hash 绑定到相应 Gate request/产物。不得新增 provider、第二份 corpus/ledger、重复 coverage Gate 或平行 literature pipeline。

**完成标准**：scientific core 能通过正式 gateway 完成按需增量检索；未经准入的 hosted-web 内容不能成为正式证据；新增文献可追溯到同一 ledger、读取事件和 evidence registry；初始 research-lit 正常路径不回归。

### P07 统一 Problem Evidence Capsule 的正式产出契约

**涉及位置**：canonical `idea-workflow.yaml`、`skills/idea-creator/SKILL.md`、`skills/idea-discovery/SKILL.md`、`templates/RESEARCH_CONTRACT_TEMPLATE.md` 和直接消费者。

**真实问题**：workflow 要求 `problem_human_acceptance` 同时产生独立的 `RESEARCH_CONTRACT.md` 和 `PROBLEM_EVIDENCE_CAPSULE.md`，后续也分别绑定两者 hash；`idea-creator` 的 mode/输出说明却把 capsule 写成 Contract 内嵌内容或未列出独立文件，形成两个不一致的权威形式。

**修改要求**：以 workflow 已声明的独立 `PROBLEM_EVIDENCE_CAPSULE.md` 为唯一正式形式，同步相关 Skill、模板和消费者；复用现有两个 artifact、hash 注册和 active problem version。

**完成标准**：problem acceptance 必然产生且只认可独立 Contract 与 Capsule；后续 root-cause 和 method 阶段读取同一注册版本；不存在内嵌 capsule 与独立文件并存的双重权威。

### P08 闭合问题候选、verdict、Human selection 与 Contract/Capsule 引用

**涉及位置**：`tools/run_state.py::_assert_outputs`、`arisctl/validators.py`、`arisctl/controller.py::_accept_problem_version` 和 canonical workflow 的 problem phases。

**真实问题**：`PROBLEM_CANDIDATES.*`、quality/novelty verdict、Contract 和 Capsule 主要只检查文件存在。`selected_id` 只要求非空，没有确认它属于候选集合、通过必要审核，并与 Contract/Capsule 中的 problem ID 一致；候选、survivor、request/upstream hash 和状态词汇也没有完整闭合。

**修改要求**：在现有 Validator/phase output hook 中补齐下游消费所需的最小字段、来源枚举、唯一 problem ID、固定 verdict 枚举、候选/幸存者引用、request/upstream hash、Contract/Capsule problem ID 和最终 `selected_id` 归属校验。统一 artifact 字段与 Controller phase status 的命名边界。

**完成标准**：不存在的候选、未通过必要审核的候选、错配 Contract/Capsule 或悬空 selection 均不能推进；正确产物仍可通过；Reality、Importance、Unresolvedness 和 novelty 不被改成机械评分。

### P09 闭合 Root-Cause Analysis 与当前问题/证据的引用

**涉及位置**：`arisctl/validators.py::validate_root_cause_analysis`、`tools/run_state.py::_assert_outputs`、root-cause analysis contract 和现有 artifact registry。

**真实问题**：现有 validator 已检查 run ID、Contract/Capsule hash 和内部 observation/cluster/trace/chain 引用，独立 verdict validator 也已检查 analysis/hash 绑定；但 `problem_id` 未核对 active accepted problem，外部 `evidence_refs` 和 `source_artifact_ids` 只要求为非空字符串，没有解析到当前问题的正式证据集合。根因合同允许文献、既有实验、数据集、真实观察和 diagnostic pilot，不能把合法证据错误限定为论文 registry。

**修改要求**：读取 P08 确立的 canonical problem/Capsule 标识并核对 active accepted problem ID；所有外部证据引用必须解析到与该问题绑定的正式证据标识。文献复用 Evidence Capsule/Evidence Registry，其他证据复用现有 artifact registry；若现有 registry 不能登记某类必要证据，只扩展这一登记面，不另建证据体系。

**完成标准**：分析错误问题、引用不存在证据或引用其他问题证据时不能通过；论文、实验、数据集、真实观察和必要 diagnostic pilot 均可按同一可追溯原则合法引用；Validator 不判断因果解释是否科学充分。

### P10 闭合问题/根因到最终方法路线的引用

**涉及位置**：`tools/run_state.py::_assert_outputs`、`arisctl/validators.py`，以及 canonical workflow 的 `method_design`、`route_human_selection`、`method_refinement`。

**真实问题**：`METHOD_ROUTES.*`、`SELECTED_ROUTE.yaml` 和 `FINAL_PROPOSAL.md` 主要只按文件存在注册。Controller 虽在外层附加 active problem version binding，但不核对文件内部的 problem/root-cause 版本与 hash，不检查 route ID 唯一性、Human `selected_id` 是否存在，也不确认 selected-route artifact 与最终 proposal 指向同一路线。

**修改要求**：对现有产物补最小机械校验：problem version/hash 与 root-cause analysis/hash 一致；causal-chain/obligation 引用可解析；route ID 唯一；Human `selected_id`、`SELECTED_ROUTE.yaml` 和 `FINAL_PROPOSAL.md` 指向同一现有 route。Reviewer 版本、attestation、verdict artifact 和 final novelty 证明只由 P02 负责。

**完成标准**：不存在的 route、错问题/错根因 route、selection 错配或偏离 selected route 的 final proposal 均不能推进；Validator 不评价方法质量，不新增 method-search artifact、Gate 或评分器。

### P11 将验证结果接回 canonical 科研状态与回退闭环

**涉及位置**：`arisctl/controller.py::validation_handoff`、`_advance_scientific_core`、`return_current_phase`、`research-pipeline` 和 `result-to-claim`。

**真实问题**：最终方法接受后，run 进入 `METHOD_CONFIRMED_AWAITING_USER_VALIDATION`，`current_phase=None` 且无可执行 action。`validation-handoff` 只读导出产物；`result-to-claim` 能给出结果判断，却没有绑定正式 run/workflow/handoff hash，也不能把方法失配、根因错误或问题前提被推翻正式反馈到 canonical phase。

**修改要求**：为 human-initiated validation 提供与现有 run 和 handoff hash 绑定的最小结果交接，并让受约束的验证结论能够复用现有 return、archive、invalidation 和 problem-version 逻辑返回已有 method、root-cause 或 problem phase。不得建立第二个 research state machine，也不为形式对称新增整组 validation Gate。

**完成标准**：成功验证可正式结束或保持等待状态；失败结果能按固定语义返回正确已有 phase 并失效后代产物；错误 run、旧 handoff 或未正式登记结果不能触发回退；validation 仍只能由用户显式启动。

### P12 补齐 research-lit 产物的唯一 ID 与交叉引用校验

**涉及位置**：`arisctl/validators.py::validate_evidence_card`、`validate_field_map` 和 `tools/literature_coverage_audit.py`。

**真实问题**：现有 Controller 已绑定 source admission、full-text read event、content hash、paper-reader attestation、ledger 和 coverage；这些无需重做。剩余缺口是 Evidence Card/Field Map 内部供下游使用的 method/evidence ID 未充分检查唯一性，矩阵等交叉引用也可能悬空。

**修改要求**：只在现有 Validator/audit 中补下游确实需要的非空标识、唯一 ID 和交叉引用解析；保持现有来源准入、读取、hash、attestation 和 coverage 机制不变。

**完成标准**：重复 ID、悬空引用或无法唯一解析的下游标识不能进入正式 Field Map；正确产物仍可通过；不新增 coverage Gate/Reviewer，不机械判断文献真实性、taxonomy 合理性或 coverage 充分性。

### P13 同步公开文档、Skill 目录与 canonical workflow

**涉及位置**：`AGENT_GUIDE.md`、`README.md`、`README_CN.md`、`docs/SKILLS_CATALOG.md`、`RESEARCH_HANDOFF_CN.md`、`tools/skill-groups.tsv` 和直接相关测试。

**真实问题**：公开说明仍把 idea discovery、实验和论文迭代描述为旧的自动端到端 pipeline；部分文档声称 `idea-discovery` 直接输出 `EXPERIMENT_PLAN.md`，Skill catalog 仍列出旧默认依赖，`SEARCH_LOG.md` 与正式 `SEARCH_LEDGER.jsonl` 名称不一致，source-admission 说明也与当前 canonical policy 不一致。Stale `research-pipeline -> auto-review-loop` catalog edge 已造成当前全量测试失败。

**修改要求**：在 P01–P12 均验收后，按最终 canonical 实现同步公开文档、必要镜像、Skill catalog、artifact 名称和 optional/required 依赖。不得借文档同步改变已验收的科研语义或新增 workflow。

**完成标准**：公开入口、阶段顺序、validation 启动条件、artifact 名称和 Skill 依赖与最终实现一致；catalog 测试及全量回归通过；不存在仍指向旧 pipeline 的直接说明。
