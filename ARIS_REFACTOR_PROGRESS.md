# ARIS research-lit 架构重构进度

## 2026-08-14 — impedance-control policy correction

- 已撤回一次不符合最小充分原则的文献分层尝试：该尝试错误地将
  `HIGH_CITATION_BACKBONE` 改为不强制全文的地图标签，并把任务特异的
  近年论文选择理由泛化为 Harness 规则。
- 已恢复原有 Controller、Coverage Audit、`research-lit` Skill 和其 Codex
  镜像的一致语义：`HIGH_CITATION_BACKBONE` 仍为强制全文优先级；高引阈值
  仅由项目 Source Policy 在正常筛选时替换。
- 未保留任何新 State、Gate、Hook、Reviewer、回执、并行回补路径或通用
  “代表性”判定标准。既有 Coverage Review `CONTINUE → QUERY_PLANNING` 和
  phase-scoped incremental literature 仍是唯一的正式纠偏入口。
- 阻抗控制项目的 8 篇近年应用/旁支论文仅作为该项目 Field Map 的当前
  筛选判断记录在交接文件中；其依据是已覆盖的机制线和 Research Brief
  边界，不能外推为其他领域或其他任务的固定规则。

最后更新：2026-08-09（Version 6 source policy Human Gate revision path）

## 目标

将 `research-lit` 从“LLM 阅读 `SKILL.md` 后自行遵守流程”改为：程序 Controller 决定流程，Validator 强制机械规则，Gateway 管理检索与全文访问，LLM 只做科研判断，Human 只批准真正需要人工决定的 Gate。

## 已确认的最终设计

- Main Research Agent：负责 query planning、Field Map synthesis 和日常科研推理，但没有流程裁判权。
- `paper_reader`：只读取 Controller 已准入并提供的论文内容，输出 Evidence Card；用于隔离大体量论文上下文。
- `coverage_reviewer`：只在 `candidate_sufficient`、重大 taxonomy 变化或最终验收时独立复核；提供第二判断。
- 不再保留独立 `query_planner` 和 `field_synthesizer` Subagent。
- Controller/Validator/Gateway/Human Gate 的程序约束不因减少 Subagent 而削弱。
- Human Gate 使用 Codex 自带界面批准，不使用密码、外部 API 或付费服务。

## 当前进度

| 项目 | 状态 | 说明 |
|---|---|---|
| 现有实现复审 | 完成 | 已确认 Human Gate、唯一写入口、ledger 来源、角色证明和替代 workflow 存在缺口。 |
| 官方 Codex 机制核对 | 完成 | `PreToolUse permissionDecision: ask` 不受支持；改用 `approval_policy` 和 `prefix_rule(..., decision="prompt")`。 |
| Subagent 精简 | 完成 | 只保留 `paper_reader` 与 `coverage_reviewer`；规划和综合归 Main Agent。 |
| Human Gate 修复 | 完成 | Codex UI `prompt` + 沙箱外一次性回执；无回执时状态保持等待。 |
| Controller/ledger/预算修复 | 完成 | 正式 workflow 锁定；查询/全文事件与 Evidence 绑定；canonical 与 policy 有哈希复核。 |
| Subagent 来源验证 | 完成 | `SubagentStop` 为两个角色生成产物回执；字符串冒充不再被 Controller 接受。 |
| bypass tests | 完成 | 当前 Controller 专项 `17 passed`。 |
| 旧项目迁移 | 完成 | 两个项目历史产物已带哈希归档，并各启动 `formal-research-lit-v2`，停在真实 Human Gate。 |
| Windows/Bash 测试 | 完成必要修复 | 自动发现 Git Bash、补 `python3` shim、统一 UTF-8；无原生 symlink 权限的测试按能力跳过，不再误称编码失败。 |
| 全量测试与验收 | 完成 | `519 passed, 66 skipped, 4 subtests passed`；零失败。66 项均为当前平台/原生 symlink 能力型 skip。 |

## 版本 1（上一版）：Controller 架构重构

- 从四个 Subagent 精简为两个，未削弱程序裁判权。
- Human Gate 从失效的 Hook `ask` 改为 Codex UI prompt + 一次性回执。
- 查询必须来自已验收计划；第 81 次仍在工具调用前失败。
- metadata、全文读取、Evidence 和 Reviewer 输出均绑定真实事件/角色回执。
- Source Policy、canonical artifacts 和 ledger 增加哈希与最终复核。
- 替代 workflow、旧 run 就地伪迁移、直接 metadata 伪造和任意 user-supplied 重标均被阻止。
- 两个旧项目已完成可恢复归档，并启动新的正式 run；旧历史没有被伪造成系统行为。

## 版本 2：research-lit 文献检索来源选择与 fallback

完成日期：2026-08-09

### 本版唯一目标

只修改 `research-lit` 的文献检索来源选择、provider failure 判定和 fallback；不修改论文筛选、准入、阅读、证据、领域认知、query refinement、预算、Human Gate 或其他 Harness 流程。

### 修改前的真实实现

- 真正控制检索调用的位置是 `arisctl/__main__.py` 与 `arisctl/gateways.py`，不是 `research-lit/SKILL.md`。
- 修改前 `arisctl query` 只允许 `--provider crossref`，并固定调用 Crossref。
- Controller 的 `execute_query` 只负责 query plan 校验、预算、状态、metadata 登记和 ledger，不负责 provider 选择。
- 当时文档虽提到 Google Scholar 或 Semantic Scholar，但运行路径没有实现 Google Scholar 优先和确定性 fallback。

### 修改后的固定检索顺序

```text
SerpApi Google Scholar
        ↓ unavailable
scholar.google.hk
        ↓ unavailable / blocked
arXiv + IEEE Xplore
        ↓ both unavailable
HUMAN_SEARCH_REQUIRED → STOP
```

1. 默认使用 SerpApi Google Scholar，固定 `engine=google_scholar`，API Key 只从环境变量 `SERPAPI_KEY` 读取，不硬编码。
2. SerpApi 路径支持关键词、年份上下限、精确标题、分页、citation count 和 `Cited by`/citation-cluster 查询。
3. 只有 key 缺失、认证/额度/429、网络、服务异常或 timeout 等 provider failure 才进入下一层。正常响应中的少结果、低相关性或 0 result 不触发 fallback，仍由原有 query refinement 继续处理。
4. SerpApi 不可用后才直连 `https://scholar.google.hk/`；查询串行执行，默认至少保守间隔 10 秒，并通过 run 内状态避免再次快速调用已经 unavailable/blocked 的来源。
5. `scholar.google.hk` 出现 CAPTCHA、`We're sorry`、unusual traffic、403、429 或无法操作结果页时立即停用；没有 CAPTCHA 绕过、代理/IP 轮换、反检测或 `site:scholar.google.*` 替代路径。
6. 两条 Scholar 路径均不可用后，才调用 arXiv 与 IEEE Xplore；两路结果按 DOI、arXiv ID 和规范化标题合并去重。任一路不可用时保留另一路，且明确标记为非 Google Scholar coverage。
7. 四级自动路径都不可用时，Controller 进入 `HUMAN_SEARCH_REQUIRED` 并 STOP，输出当前计划中的 `query`、`purpose` 与 `evidence_gaps`，优先请求人工 Google Scholar 检索。
8. 用户提交人工检索结果后，通过 `submit-human-search-results` 回到 `METADATA_RETRIEVAL`，继续原有 research-lit 流程。

### 直接相关文件

- 运行逻辑：`arisctl/gateways.py`、`arisctl/controller.py`、`arisctl/__main__.py`、`arisctl/workflow.py`
- research-lit 约束：`skills/research-lit/SKILL.md` 及 Codex 镜像
- 直接相关共享契约：`idea-workflow.yaml`、`fan-out-pattern.md`、`problem-discovery-contract.md`、`integration-contract.md` 及 Codex 镜像
- 测试：`tests/test_research_lit_gateways.py`、`tests/test_aris_controller.py`、`tests/test_scientific_core_contract.py`、`tests/test_codex_skill_mirror.py`

### 配置与当前环境

- 当前环境未配置 `SERPAPI_KEY`；要启用默认第一优先级，需要用户配置该环境变量。
- IEEE Xplore 使用官方 API 时从 `IEEE_XPLORE_API_KEY` 读取 key；缺失时该来源判为 unavailable，arXiv 仍可单独完成第三级 fallback。
- 本次实际直连 `https://scholar.google.hk/` 返回 `403 Forbidden`，因此当前 Codex 环境不具备可用的 Scholar 直连/操作能力，会进入 arXiv + IEEE Xplore fallback。

### 测试与范围复核

- 直接相关测试：`67 passed`。
- 全量回归：`528 passed, 66 skipped, 4 subtests passed`，零失败。
- scoped `git diff --check` 通过。
- 仓库原有其他未提交改动未被清理、覆盖或顺带修改；本版本新增变更限于上述检索路由及其直接必要配置、契约和测试。

## 版本 3：research-lit fallback 最终核查与修正

完成日期：2026-08-09

- 删除版本 2 中通过 `urllib` 和 `HTMLParser` 直接抓取 `scholar.google.hk` 的实现。当前 gateway 只接受显式注入的真实 browser/computer interaction adapter；CLI 当前没有该能力，因此将此 route 直接记为 unavailable。没有 requests、curl、HTML scraper 或普通 Web Search 替代路径。
- 第三级不再只以“arXiv 与 IEEE Xplore 是否可访问”决定是否进入人工检索。两路可访问时，仍沿用既有准入与 coverage 判断：若没有结果通过现有准入，立即进入 `HUMAN_SEARCH_REQUIRED`；若 Field Map 为 `PARTIAL`/`INSUFFICIENT`，或既有 coverage reviewer 返回 `CONTINUE`，Main 仍先按原逻辑生成下一轮 refinement plan，再将该计划交给人工 Google Scholar 检索并 STOP。
- 没有新增 coverage 标准、评分或另一套充分性判断，也没有修改论文筛选、Evidence、Gate、Subagent 或其他 workflow 行为。
- 复核 `arisctl/workflow.py`、两份 `idea-workflow.yaml`、两份 `problem-discovery-contract.md` 和两份 `fan-out-pattern.md`：其中本任务变更均直接用于固定 provider 顺序、`HUMAN_SEARCH_REQUIRED` 状态或检索来源说明；未发现需要回滚的无关逻辑。
- 直接相关测试：`69 passed`。
- 全量回归：`530 passed, 66 skipped, 4 subtests passed`，零失败。

## 版本 4：真实 E2E 修改审计

审计日期：2026-08-09

### 审计基线与范围

- Version 1–3 冻结。本轮没有改变 Main Research Agent + `paper_reader` + `coverage_reviewer` 的两 Subagent 架构、原 research-lit 科研方法、Source Admission Policy、Evidence / Field Map / coverage / stopping、Human Gate 或既定 discovery provider 顺序。
- 唯一规范来源是当前 ARIS 仓库的 `AGENTS.md`、`skills/research-lit/SKILL.md`、workflow/contracts、Controller、policy 与 tests。Academic Research Suite 未用于解释或裁决本轮修改。
- E2E 已暂停：没有继续检索、没有新建 workflow/run、没有整体回滚，也没有手工修改 attestation、ledger 或 state。

### 逐项裁决

#### 1. initial-Human-Gate canonical workflow upgrade — REMOVE

- 原始问题：旧 run 的 workflow hash 与后来 canonical workflow 不同，Controller 因 immutable hash 正确拒绝继续。
- 不修改的后果：该旧 run 不能原地继续；需要停止它并从 canonical workflow 开始合法正式 run。
- 最小性：现有 upgrade classmethod + CLI 是为一次旧 run 延续引入的迁移协议，不是长期最小方案。停止未真正开始的旧 run 更简单。
- 科研逻辑：它不直接改论文判断，但削弱了“run 启动后 workflow 不可变”的机械边界。
- bypass/复杂度：新增了 workflow 重绑定权限、兼容性判断、状态迁移记录和长期维护面；风险高于收益。
- 回归：原先有“仅 initial gate 可升级”的测试，但测试通过不构成长久保留理由。现改为验证 hash mismatch fail closed，且 Controller/CLI 均不存在 upgrade 路径。
- 实施：删除 `upgrade_workflow_at_initial_gate` 与 `upgrade-workflow` CLI；不触碰历史 run 中已有的 provenance 字段。

#### 2. runtime provider recovery — KEEP

- 原始问题：运行中补充 `SERPAPI_KEY` 后，run 仍把该 provider 永久视为 unavailable。
- 不修改的后果：同一 pending query 只能滞留 Human Search，即使原 provider 的明确故障已消失。
- 最小性：仅对当前 pending query、用户明确指定且凭据现在存在的既有 provider 清除 unavailable 标记并重新置为 planned；不增加 provider、不改变顺序。
- 科研逻辑：只恢复机械执行能力，不更改检索问题、准入、coverage 或 stopping 判断。
- bypass/复杂度：新增面很小；不能跳过 query plan、预算、provider cascade 或 Human Search 状态，也不记录/回显密钥。
- 回归：`test_added_provider_credential_resumes_pending_query_without_state_edit` 覆盖无凭据拒绝、恢复、预算事件和 secret 不入 ledger。

#### 3. SerpAPI metadata → Crossref identity verification — KEEP

- 原始问题：SerpAPI 发现的条目可能停在 `verify_pending`，缺少 DOI/完整 identity，无法进入既有准入判断。
- 不修改的后果：合法 discovery 结果会因身份字段不完整而无法准入，或诱导人工改 metadata。
- 最小性：仅在 `decide_admission` 需要时，对已经发现的 paper 以 Crossref 精确规范化标题匹配，并记录独立 identity event。
- 科研逻辑：没有改变 Source Admission Gate，只补足 Gate 所需身份；Crossref 不是 discovery source。
- bypass/复杂度：不能自行创建 paper、不能把验证结果直接准入；`source_origin` 和 `discovery_provider` 保留。长期复杂度限于单一 verifier adapter 与 ledger event。
- 回归：identity gateway、精确标题、ledger、discovery provenance 保留均有定向测试。

#### 4. year preservation — KEEP

- 原始问题：Crossref 精确匹配可能返回空年份，覆盖 Scholar 已知年份。
- 不修改的后果：paper identity 变得不完整，且按年份分段的既有 citation threshold 可能得到错误结果。
- 最小性：只接受 Crossref 的整数年份；否则保留 discovery year；两者均无时才从 venue 文本恢复。
- 科研逻辑：不改阈值和准入规则，只防止 identity enrichment 丢失已有事实。
- bypass/复杂度：无新权限面；是局部三段 fallback。
- 回归：新增“Crossref null year 保留已知 year”测试，并保留“无已知 year 时从 venue 恢复”测试。

#### 5. OA full-text retrieval（Crossref → OpenAlex → Semantic Scholar）— KEEP

- 原始问题：正式 Controller 只有本地 `read-text`，对已准入但本地无全文的 discovery paper 没有受控 OA 获取路径。
- 不修改的后果：paper_reader 无法取得多数已准入论文内容，Evidence 流程停滞或绕过 Gateway。
- 最小性：三个已有服务职责单一、顺序固定，只接受已准入 paper identity，返回 PDF bytes + provenance；没有增加 discovery provider。
- 科研逻辑：只解决内容获取，不更改发现、身份、准入、Evidence 标准或 coverage。
- bypass/复杂度：Controller 在调用前仍验证 admission；每个 resolver 验证 DOI/真实 PDF，read event 绑定 hash。复杂度为必要的三个小 adapter，无新调度机制。
- 回归：各 resolver、真实 PDF、DOI 匹配、固定调用顺序、未准入时网关零调用均有测试。

#### 6. `ADMIT_READ_UNAVAILABLE` — SIMPLIFY

- 原始问题：一个已准入 paper 的所有 OA 路径均失败时，`finish_reading` 会永久要求该 paper 的 Evidence，形成死锁。
- 不修改的后果：即使其他 paper 已有合格 Evidence，也无法进入 synthesis。
- 最小性：新增 admission status 不是最小方案；它把 retrieval failure 混入 Source Admission decision，并扩大了准入状态集合。
- 科研逻辑：原实现会改变既有 admission 语义，并可能让暂时失败的 paper 失去自然重试资格。
- bypass/复杂度：新 status 是额外 bypass surface，所有可读状态判断均需同步维护。
- 回归：已有“部分不可用不死锁”和“全部不可用不得空 synthesis”测试；现更新断言以保证 admission 不变。
- 实施：删除该 status。保留原 `admission_status`，只记录 `fulltext_failure`；成功重试会清除 failure。synthesis 只忽略尚无成功 read event 的 operationally unavailable paper，且零 accepted Evidence guard 始终优先执行。

#### 7. zero accepted Evidence 禁止 Field Synthesis — KEEP

- 原始问题：所有 read 均 unavailable 时，旧状态处理可使 missing-Evidence 列表为空。
- 不修改的后果：没有任何 accepted Evidence Card 也可能进入 Field Synthesis，生成证据为空的 Field Map。
- 最小性：`finish_reading` 中一个独立 `any(evidence:*)` fail-closed guard 即可。
- 科研逻辑：不增加研究标准，只程序化执行既有 Evidence → synthesis 前置关系。
- bypass/复杂度：无新绕过面；反而关闭空证据路径，复杂度为单一 guard。
- 回归：`test_all_unavailable_reads_cannot_create_evidence_free_field_map` 覆盖零 Evidence 拒绝。

### formal-run preflight（已回退，仅保留决策历史）

- Version 4 曾尝试用 permission profile、项目 hook receipt、thread/root/profile/TTL/hook hash 和 admission-denial probe，在真实 gateway 前证明当前 Codex 会话已加载项目 hook。
- 真实 E2E 证明这会把 Harness 正常运行错误地绑定到 Codex App 的 permission profile、session 加载状态和额外人工重载；即使用户切换到 workspace-write/on-request，仍可能因没有 live receipt 被拒绝。
- 该机制现已完整删除，不再是 formal run 的当前要求。当前保持简单执行链：真实 `paper_reader`/`coverage_reviewer` 结束时由 `SubagentStop` 生成 attestation，Controller 在提交 Evidence/coverage review 时验证；没有 attestation 就拒绝。

### discovery / identity / full-text 边界

真实 CLI 调用链保持为三条不同路径：

1. `query` → `research_literature_search` → SerpAPI Google Scholar → browser Scholar → arXiv + IEEE；
2. 已发现 paper 的 `admit` → 必要时 `crossref_verify_metadata` → 原 Source Admission Gate；
3. 已准入 paper 的 `fetch-fulltext` → Crossref declared link → OpenAlex OA → Semantic Scholar OA。

Crossref/OpenAlex/Semantic Scholar 不在 discovery cascade 中；identity enrichment 保留 `source_origin=gateway_discovery` 和原 `discovery_provider`；full-text resolver 无法注册 paper 或改变 admission。定向测试显式将 identity/full-text gateways 设为 forbidden 后执行 discovery，并验证零调用。

### budget 来源核查

- 当前 canonical `idea-workflow.yaml` 唯一 runtime budget 是 80 queries / 80 full texts / 8 search cycles；Controller 从该 snapshot 初始化并以 hash 锁定。
- 80 queries 来自先前用户明确指令“预算 40 可以上调到 80”，不是 Version 4 自行扩张。本轮不修改 budget。
- 历史 40 来自已归档 legacy impedance-control Source Admission Policy（40 queries / 80 full texts / 8 cycles）；该旧 Field Map 还记录实际事后核算 60 queries、超过批准 40 后停止。legacy 文件只作 provenance，不是当前 runtime policy。
- 当前 validator 禁止 Source Admission Policy 再定义第二套 runtime budget；测试中的 40 是 policy-drift fixture。因此未发现未经用户批准的 policy drift，不提出修改。

### 修改文件与测试

- `arisctl/controller.py`：删除 workflow upgrade；移除 environment preflight 调用；简化全文失败状态；保留零 Evidence gate、state/workflow/hash/budget/Gateway/attestation enforcement。
- `arisctl/__main__.py`：删除 `upgrade-workflow` CLI。
- `arisctl/project_setup.py`：保留项目 Codex layer 安装与 manifest hash；删除仅服务 environment preflight 的 validator、receipt/path/profile/TTL/hook-hash 校验。
- `.codex/hooks/pre_tool_use_policy.py`：保留普通 Controller/Gateway/Human Gate 防绕过；删除 preflight receipt 写入和 receipt 路径保护。
- `tests/test_aris_controller.py`、`tests/test_research_lit_gateways.py`：删除旧 preflight tests，新增 Full Access/no-receipt 与 attestation 仍强制的 rollback regression。
- formal-preflight rollback regression：`2 passed, 27 deselected`。
- Controller bypass regression：`16 passed, 13 deselected`。
- research-lit Controller/gateway/admission/evidence/attestation：`43 passed`。
- 全量 regression：`545 passed, 66 skipped, 4 subtests passed`；零失败。沙箱内首次运行的 9 个 Windows installer 失败仅因禁止写入 `C:\Users\user\.aris`；按要求在沙箱外重跑后全部通过。

### 正式 E2E 当前事实与恢复结论

- `formal-research-lit-v2` 仍停在 `PAPER_READING`：2/80 queries，8 个 full-text event（1 complete、7 failed），0 accepted Evidence，未开始 Field Map；本轮未改变其 state/ledger/attestation。
- 该 run 保留为 integration-debugging E2E 记录。本轮未继续它，也未创建新 run，未手工修改其 state、ledger、attestation 或历史 provenance。
- Full Access 不再被 Harness 基于 permission profile 拒绝；不再要求 live project-hook receipt、session handshake 或 admission-denial probe。
- 当前没有已知未关闭的代码 P0。rollback 完成后继续保持 E2E 暂停，等待用户审核；经用户确认后可以另行开始 fresh clean E2E。

## Version 4 formal-run preflight rollback

完成日期：2026-08-09

1. **为什么回退**：真实 E2E 证明 preflight 会把科研 Harness 运行错误地依赖 Codex App permission profile、live hook receipt、thread/root/profile/TTL 与会话重载状态，并增加用户切换权限和重载项目的人工步骤；它不是原 research-lit 科研逻辑，也不是必要的程序 enforcement。
2. **删除内容**：删除 workspace-write/on-request permission gate、Full Access/unrestricted rejection、live project-hook receipt、`.aris/formal-preflight` receipt 路径、PreToolUse receipt 生成、thread/root/profile/TTL/hook-hash 校验、admission-denial probe、`project_setup.py` 专用 validator、旧 tests 和一次性恢复 handoff。没有留下无调用方 preflight code。
3. **保留的 Version 4 修复**：workflow upgrade 仍已删除；runtime provider recovery；SerpAPI metadata → Crossref identity verification；year preservation；Crossref → OpenAlex → Semantic Scholar OA full-text retrieval；admission 不变且只记录 operational `fulltext_failure`；零 accepted Evidence 禁止 Field Synthesis；discovery / identity / full-text source role 分离。
4. **Full Access**：重新支持。Controller 不读取或判定 `CODEX_PERMISSION_PROFILE`/`CODEX_THREAD_ID`，不因 `danger-full-access`、`unrestricted` 或缺少 receipt 拒绝 formal action。
5. **真实 enforcement 保留**：Controller workflow/state、canonical workflow hash、query/full-text budget、Source Admission Gate、Gateway、artifact hashes/canonical validation、Human Gate、Subagent attestation、Evidence validation 和 ledger 均未削弱。无真实 attestation 的 Evidence 仍拒绝；Main 仍不能自批 Human Gate 或冒充 reviewer。
6. **Regression**：rollback 2/2、Controller bypass 16/16、research-lit focused 43/43、全量 `545 passed, 66 skipped, 4 subtests passed`；零失败。
7. **剩余 P0 / 下一步**：当前无已知 P0。可以在用户审核本 rollback 后开始 fresh clean E2E；本轮按要求 STOP，不继续 `formal-research-lit-v2`。

## 已知边界

- 项目级 Codex config/rules 只有在项目被用户信任并重新载入后才生效。
- Harness 不再依据 Codex permission profile 接受或拒绝 formal run；硬约束由 Controller/Gateway/Validator/Human Gate/Subagent attestation/ledger 在实际动作处执行。
- Windows 有 Git Bash，但当前用户没有创建原生 symlink 的权限；纯 Bash/审计测试执行，依赖原生 POSIX symlink 语义的旧安装器测试按能力跳过。
- 两个迁移项目仍需用户在各自 Codex 项目重新载入并信任项目级 `.codex` 配置，然后确认 `source_policy_approval`；本次没有代替用户批准。

## 用户可纠正的事项

如需调整方向，请优先检查“最终设计”和“已知边界”。本文件会在每个修复阶段完成后更新，而不是只在最终交付时补写。

## Version 5：fresh Source Admission Policy P0 死锁修复

完成日期：2026-08-09

### 问题与 L0 裁决

- fresh research project 没有 `idea-stage/SOURCE_ADMISSION_POLICY.yaml` 时，旧 Controller 仍在 `start()` 中无条件进入 `WAITING_FOR_HUMAN → source_policy_approval`。
- canonical workflow 在 `WAITING_FOR_HUMAN` 禁止所有 Agent，且只允许 `human_approve`；审批校验又要求 policy 文件已经存在。因此用户没有真实内容可审、Main Agent 也没有合法动作可起草，形成 P0 流程死锁。
- L0 正确顺序是：Main Research Agent 起草项目候选 policy → 现有 `validate_source_admission_policy` 验证 → Controller 为该候选哈希创建 `source_policy_approval` → 用户通过现有 Codex UI 回执真实批准 → 才进入 `QUERY_PLANNING`。Main 只负责候选内容，不拥有 Gate 审批权。

### 最小修复

- canonical workflow 及 Codex 镜像新增唯一前置阶段 `SOURCE_POLICY_DRAFTING`；该阶段只允许 Main Research Agent 调用 `submit_source_admission_policy`。真正的 `WAITING_FOR_HUMAN` 仍为零 Agent、仅 `human_approve`。
- `ARISController.start()` 对 fresh project 进入 policy drafting；对已有 policy 先运行现有 validator，只有验证通过才创建 Human Gate。无效的已有 policy 不会产生可审批 Gate。
- 新增 `submit_source_admission_policy` Controller/CLI 入口。候选先进入 staging，经现有 schema/validator 通过后才写入 manifest 指定的 canonical policy 路径，并记录待审批哈希；未通过时不生成 canonical policy，也不推进状态。
- Human Gate 与已验证候选哈希绑定；审批前再次复核候选未改变。无一次性 Codex UI receipt 时 Main 调用审批仍失败；批准后才登记 `accepted_artifacts.source_admission_policy` 并进入 `QUERY_PLANNING`。
- `skills/research-lit/SKILL.md` 及 Codex 镜像只补充上述执行边界。没有修改 `source-admission-policy.md` 的准入标准，也没有修改 provider、budget、Evidence、Field Map、coverage、stopping、Subagent 架构或后续科研逻辑。

### Regression 与结果

- 新增 `test_fresh_project_drafts_validates_and_human_approves_policy_before_query`，覆盖：fresh start、Main 合法起草、无效 policy 不进 Gate、有效 policy 后才进 Gate、批准前 query 网关零调用、Main 无 UI receipt 不能自批、用户批准后 query 正常继续。
- P0 定向 regression：`3 passed, 27 deselected`。
- research-lit Controller / gateway / scientific contract / Codex mirror：`85 passed`。
- Controller 全套（含现有 bypass tests）：`30 passed`。
- 全量 regression：`546 passed, 66 skipped, 4 subtests passed`；零失败。
- scoped `git diff --check` 通过。

### 范围与 STOP

- 本轮修改仅位于 ARIS 仓库；没有修改 `research-projects/impedance-control`。
- 没有继续或新建 E2E run，没有修改任何现有 E2E state、ledger 或 attestation。
- 本次 P0 修复和回归已完成；按用户要求 STOP，不继续 E2E。

## Version 6：source policy Human Gate revision 路径

- **问题确认**：已有有效 `SOURCE_ADMISSION_POLICY.yaml` 进入
  `source_policy_approval` 后，原 Controller 只支持批准，不能在不绕过
  Human Gate 的前提下退回 Main 修改候选。
- **最小修复**：仅为 `source_policy_approval` 增加 Human 可调用的
  `request_source_policy_revision`。它消费一次 Codex UI 回执、审计旧候选
  hash，清除 pending request/candidate，并返回 `SOURCE_POLICY_DRAFTING`；
  `WAITING_FOR_HUMAN` 仍为零 Agent。Main 只能通过既有
  `submit_source_admission_policy` 重写候选，再经原 validator 生成新 hash
  和新的 Human Gate；批准后才进入 `QUERY_PLANNING`。
- **边界**：未修改 Source Admission 标准、provider、budget、Evidence、Field
  Map、coverage、stopping 或 Subagent 架构；未继续 E2E。
- **Regression**：Controller 定向回归 `32 passed`；包含 bypass 与 Human Gate
  路径的定向集 `4 passed, 28 deselected`；Controller/gateway/scientific-contract
  相关回归 `67 passed`。全量回归结果为 `542 passed, 66
  skipped, 4 subtests passed`，但有 6 个既有 Windows PowerShell installer
  测试失败：其子进程以本机代码页输出而测试按 UTF-8 解码，导致
  `result.stdout/stderr` 为 `None`。失败均位于
  `tests/test_install_aris_ps1.py`，与本次 Controller/source-policy 改动无关，
  因遵守最小范围未修改。
- **收尾验证**：在同一 Windows PowerShell 5.1 环境下，仅将这 6 项子进程的
  解码设为本机 `cp936` 后单独重跑，6/6 通过。这确认失败是测试的 UTF-8
  解码假设与 PowerShell 5.1 本机代码页不匹配，而非 Version 6 行为回归。

## Version 7：Scholar 可见浏览器 fallback 跑通

完成日期：2026-08-10

### 修改目标

保持既有 discovery provider 顺序不变：

```text
SerpApi Google Scholar
        → unavailable
scholar.google.hk（可见 Chrome，单页人工式检索）
        → unavailable / blocked
arXiv + IEEE Xplore（并行、合并去重）
        → 均不可用或既有 admission/coverage 仍不满足
HUMAN_SEARCH_REQUIRED
```

此前 `scholar.google.hk` 仅接受外部注入的 browser adapter；CLI 没有默认 adapter 时会直接把该层记为 unavailable。本版本将已实测成功的可见 Chrome CDP 读取实现为正式 adapter，而非 HTML/requests 抓取。

### 实现与边界

- 新增 `arisctl/browser_scholar.py`。每次调用启动独立、可见的 Chrome 临时 profile，只导航并读取**一个**用户请求的 Scholar 结果页；默认使用 Scholar 正常的 10 条/页和 `start=(page-1)*10` 翻页语义。
- 适配器从可见结果卡读取 `title`、`year`、`venue`（保留页面可见值）、标题链接、Google Scholar `citation_count`、`Cited by` URL/cluster id 和 snippet；结果标记 `citation_source=google_scholar` 与 `discovery_provider=scholar_google_hk`。
- 不使用 headless 模式，不登录或读取用户现有浏览器 cookie，不自动连续翻页，不做批量查询、快速重试、代理/IP 轮换、CAPTCHA 求解或反检测规避。适配器用进程内互斥锁串行化会话，并在每次会话完成后实际执行至少 10 秒冷却；页面显示 block/CAPTCHA、Chrome 不存在或规定等待时间内无结果时，立即返回既有 `ProviderUnavailable`，由原有 cascade 继续处理。
- Scholar 页面将期刊名以省略号截断时，只把可见值作为 discovery metadata；既有 Crossref identity verification 仍负责后续 DOI/完整 venue 校验，且不覆盖 Scholar 引用计数。
- `arisctl/gateways.py::scholar_google_hk_search` 现在默认调用该 adapter；测试或其他运行时仍可显式注入替代 browser adapter。
- `tools/scholar_cdp_probe.py` 保留为单页诊断入口，但复用正式 adapter，不保留第二套实现。

### 实测与回归

- 在 Windows 本机可见 Chrome 中，查询 `impedance learning` 成功读取第 1 页和 `start=10` 的第 2 页；每页各得到 10 条 Scholar 结果，未出现 block/CAPTCHA。
- 新增浏览器卡片归一化、Unicode 不间断空格 metadata 行解析、默认 adapter 调用、10 秒冷却和 block→`ProviderUnavailable` 定向测试。
- 本版本不创建或继续 formal research run，不修改 Source Admission、coverage、Human Gate、预算、Evidence 或 Field Map 逻辑。

## Version 8：IEEE Xplore 可见浏览器 fallback

完成日期：2026-08-10

### 修改目标

保留既有第三级 `arXiv + IEEE Xplore` 合并去重的来源顺序和语义；仅把 IEEE Xplore 自身的获取方式扩展为：官方 API 可用时优先使用 API，未配置 Key 或 API 不可用时，尝试一次受限的可见浏览器公开结果页读取。

### 实现与边界

- 新增 `arisctl/browser_ieee.py`。实现与 Scholar adapter 一致的边界：临时、可见 Chrome profile；每次调用只访问一个用户指定的 IEEE Xplore 结果页；默认使用站点的 `pageNumber` 翻页语义；同源会话串行化并在会话间至少冷却 15 秒。
- 只从页面可见的结果卡读取标题、页面链接、可见年份、可见 IEEE venue、可见 citation 文本（如果页面实际显示）及 snippet。不可见的 DOI 或 citation count 保持空值，仍由既有 identity verification/准入流程决定后续处理；不会逐条进入论文页补抓字段。
- 不登录、不读取用户 cookie、不使用 headless、不自动连翻页、不批量检索、不快速重试、不轮换代理/IP、不处理 CAPTCHA 或绕过反自动化机制。block/CAPTCHA 或浏览器不可用均映射为既有 `ProviderUnavailable`，由原有 fallback/HUMAN_SEARCH_REQUIRED 规则处理。
- `arisctl/gateways.py::ieee_xplore_search` 现在先调用官方 API；仅当 API Key 缺失或 API 返回 `ProviderUnavailable` 时再调用该浏览器 adapter。结果仍保留 `discovery_provider=ieee_xplore`，并以 `retrieval_method=visible_browser` 区分来源方式。

### 验证与当前环境限制

- 新增 IEEE 可见卡片归一化、年份/venue 解析、15 秒冷却、缺 API Key 时浏览器 fallback 以及 block→`ProviderUnavailable` 定向测试；与 Scholar adapter 和 research-lit gateway 的 scoped 测试共 `23 passed`。
- 本机此前可见 Chrome 已用于 Scholar 实测；但本次受限会话中 Chrome 无法创建本地调试端口（启动时权限受限）。真实 IEEE 调用因此正确返回 `ProviderUnavailable("visible Chrome did not expose its local debugging endpoint")`，并非 IEEE 站点的 block/CAPTCHA，也没有产生任何规避或隐藏抓取行为。
- 在可运行可见 Chrome 的正常桌面会话中，仍需用单页 `impedance learning` 查询做一次最终页面选择器验证后，才可把 IEEE browser fallback 视为 live-verified。

## Version 9：撤销 IEEE API 路径，改为纯人工式浏览器检索

完成日期：2026-08-10

用户明确指定 IEEE Xplore 与 `scholar.google.hk` 一样按正常科研人员的浏览器操作处理，而不是使用或依赖官方 API。故撤销 Version 8 的“API 优先”设计：

- 删除 IEEE API 请求实现、`IEEE_XPLORE_API_KEY` 依赖、`research_literature_search` 的 `ieee_api_key` 参数，以及 Controller 中 IEEE 凭证恢复分支。
- `ieee_xplore_search` 现在只调用 `arisctl/browser_ieee.py` 的单页可见 Chrome adapter；即使环境中存在 IEEE Key 也不会读取或使用它。
- 保持与 Scholar 一致的安全边界：临时 profile、可见窗口、单页、15 秒同源冷却、无登录/Cookie 复用/自动翻页/批量/快速重试/代理/CAPTCHA 处理；页面拦截、渲染超时或浏览器错误均安全映射为 `ProviderUnavailable`。
- 对真实 `impedance learning` 第一页的初次读取曾得到可见卡片文本；据此修正了 IEEE 页面中的 `Papers (n)` 引用链接误判为结果条目，以及会议 venue 位于 `Year:` 行上一行的解析规则。当前短时重复访问出现 IEEE 前端渲染超时，未出现 CAPTCHA；按边界不再继续重试。
- 定向测试覆盖纯浏览器默认路由、环境中存在 IEEE Key 时仍不走 API、block 映射、可见卡片归一化、期刊/会议 venue 解析和冷却；本轮 scoped 测试 `23 passed`。本版本不改动 discovery 级联顺序、Source Admission、coverage、Human Gate、预算、Evidence 或 Field Map。

## Version 10：检索覆盖完整性与全文批量人工接管

完成日期：2026-08-10

### 已确认的问题

1. `unavailable_providers` 被跨 query 持久化，并由 CLI 传回 gateway。一次瞬时网络故障、浏览器渲染失败或 Scholar block 会让同一 run 后续 query 永久跳过该来源，直接降低可检索覆盖。
2. 声明为 `arXiv + IEEE Xplore（并行）` 的第三级 fallback 实际按顺序调用，既增加等待，也不符合既定流程。
3. 直连 Scholar / IEEE 路径此前静默忽略部分 query constraints；人工补检请求也只给出一个 query，迫使用户逐条操作。
4. 一个已准入论文的 OA full-text 获取失败后，旧 `finish_reading()` 可以忽略该论文、在其他 Evidence 已存在时继续进入 Field Synthesis。这会把“无法阅读”误当成“可安全省略”。

### 实施

- Provider failure 现在只记录在对应 query 的 ledger / `provider_attempts` 中；已移除 run-wide provider suppression 输入。下一条正常 query 会重新按 `SerpApi → Scholar HK → arXiv + IEEE` 尝试，绝不因旧 incident 静默跳过来源。
- arXiv 与 IEEE Xplore 使用两个 worker 并行执行，随后按固定 provider 顺序记录 attempts、合并和去重，保持可审计性与结果确定性。
- Scholar HK 的单页可见浏览器路由传递年份、精确短语、`Cited by` cluster 和页码；IEEE 对精确标题使用正常的带引号查询，并对页面可见的标题/年份做保守本地筛选。`cited_by` 无法由 arXiv 或 IEEE 满足时明确标记为不可用，而不是静默丢弃该限制。arXiv 将年份窗口加入 API 查询并保留本地复核。
- 只要自动检索因某 provider failure 转到低优先级来源（即使已有 metadata），Controller 会保留自动结果、立即 STOP，并创建一次 `metadata_search_batch`。其中包含所有受影响的 planned queries、purpose、filters/constraints、provider attempts 和 evidence gaps。用户以一个 batch 提交结果后才回到 `METADATA_RETRIEVAL`。
- 当所有自动结果都未达到既有 admission 要求时，同样产生该 batch，而非让流程继续到无可读论文的状态。
- OA full-text 路径失败时，Controller 将一次性收集所有尚未有 Evidence 且没有本地文件的已准入论文，进入 `HUMAN_FULLTEXT_REQUIRED`，输出标题、作者、年份、venue、DOI/稳定链接及 `source-materials/` 目标目录。新增 `submit-human-fulltext-batch`：只有用户为请求中的每篇论文提交一个本地文件和 hash 可验证的 manifest 后，才恢复 `PAPER_READING`。新增 `read-user-fulltext` 仍经正常 read receipt / Evidence Card / attestation 链路读取，不能借此跳过 Evidence。
- `finish_reading()` 现在对每一篇已准入论文 fail-closed：缺少 accepted Evidence 就不能进入 Field Synthesis；不再以 `fulltext_failure` 作为省略依据。
- 同步更新主线和 Codex 镜像 `research-lit/SKILL.md` 以及两份 canonical workflow 的允许动作，避免运行说明与 Controller 行为不一致。

### 验证

- 新增/更新的定向回归覆盖：source incident 不跨 query 跳过、arXiv/IEEE 并行、约束传递和拒绝静默降级、自动部分结果的批量人工检索、批量人工全文导入、读取本地全文后仍须 Evidence，以及全文失败时的 stop。
- 定向回归：`60 passed`。
- 全量回归：`562 passed, 66 skipped, 4 subtests passed`，零失败（`python -m pytest -q --cache-clear`）。
- `git diff --check` 通过。未继续或修改任何已有 formal research run、state、ledger 或 attestation。

## Version 11：修复领域认知后的正式流程中断

完成日期：2026-08-10

### 问题与人工验证边界

- 原 Controller 在用户批准研究范围后只把 `research_lit.current_stage` 设为
  `LANDSCAPE_ACCEPTED`；问题发现至最终方法确认虽然写在 workflow phase 列表中，
  但没有 Controller transition、allowed action、正式 Gate 或可核验的跨阶段 hook，
  因而正式流程在领域认知后中断。
- 本次按用户纠正确认：最终方法通过新颖性 Gate 后，必须先由用户理解并确认；
  验证不会自动运行。正式流程终点是
  `METHOD_CONFIRMED_AWAITING_USER_VALIDATION`，后续验证只能由用户另行显式发起。

### 最小修复

- 在 canonical workflow 及 Codex 镜像中增加 `scientific_core` Controller 合同，
  声明当前 post-landscape execution plan、阶段允许角色、artifact hook 策略、
  完成状态和 human-initiated validation entry policy；没有新增第二套状态机。
  该 phase 列表是可随科研方法论修订的 canonical 快照，不是冻结在 Python 中的
  永久阶段数量或顺序。
- 扩展 `ARISController`：范围批准后自动激活 `problem_generation`；非 Gate 阶段
  使用 `start-phase → complete-phase`，独立评审 Gate 使用 `accept-phase`，三个人工
  决策点继续复用现有 Codex UI receipt-backed `human-approve`。形式 Gate 未接受、
  Human Gate 未批准或依赖不满足时均不能推进。
- 每个正式交接物由 Controller 登记 path、SHA-256、size、producer phase、
  provenance 和 upstream hash snapshot。评审 Gate 接受后再把 verdict ID、reviewer、
  reviewer family、independence 和 accepted timestamp 写回被接受的 artifact record；
  下游启动前同时校验依赖状态、登记身份和当前 hash，不能依赖 prompt 补造输入。
- 范围批准生成带 scope approval receipt 和全部 landscape artifact hashes 的
  `landscape_handoff`。三个后续 Human Gate 将 selected ID（如适用）、批准 request
  ID、UI receipt 和输出 artifact hashes 登记到 state。Main 只可准备 Human Gate
  声明的交接物，不能自行批准或推进。
- 最终 `method_acceptance` 只创建 `validation_entry.status =
  AWAITING_USER_INITIATION`，保存方法确认回执和已接受方法产物；不暴露自动验证
  action 或 agent。
- 同步更新 `AGENTS.md`、`RESEARCH_HANDOFF_CN.md`、主线与 Codex adapter 的
  `idea-discovery/SKILL.md`。既有 `tools/run_state.py` 对 Controller-managed run 的
  bypass 禁令保持不变；现有 hook/rules 已覆盖新增 Human Gate 命令，无需新增平行 hook。

### 验证

- 新增完整 post-landscape Controller 回归，覆盖当前声明的全部 phase、独立评审接受、
  三个人工 Gate、缺少 selected ID 拒绝、artifact provenance/upstream snapshot、
  最终等待用户验证以及终点无自动 action/agent。
- Controller、scientific contract、legacy state guard 与 Codex mirror 定向回归：
  `98 passed`。
- 全量回归：`563 passed, 66 skipped, 4 subtests passed`，零失败
  （`python -m pytest -q --cache-clear`）。
- `python -m compileall -q arisctl` 与 `git diff --check` 通过。

### Version 11 阶段清单冻结纠正

- 后续复核确认 `arisctl/workflow.py` 曾用
  `REQUIRED_SCIENTIFIC_CORE_PHASES` 对整份 phase 列表做精确相等校验；这会让
  canonical YAML 即使按科研方法论正确新增、删除或调整阶段，也因 Python 常量
  未同步而被拒绝，属于真实的错误冻结。
- 已删除具体阶段清单常量。loader 现在只强制可执行结构不变量：phase plan 非空、
  名称唯一、均有 workflow 声明、`allowed_agents` 覆盖、顺序满足声明的依赖拓扑、
  终点仍是正式 Human Gate，并保留 artifact hook 与人工发起验证策略。
- Controller 接管、state/gate/artifact/provenance hook、回退机制和
  `METHOD_CONFIRMED_AWAITING_USER_VALIDATION` 均保持不变。本次不新增、删除或重排
  当前 canonical phase；仓库中后续已加入的独立根因分析阶段也不受影响。
- 新增可扩展 execution plan 回归：合法插入未来阶段无需修改 Python 常量，违反
  声明依赖拓扑的重排仍 fail closed。相关定向回归 `101 passed`；全量回归
  `566 passed, 66 skipped, 4 subtests passed`，零失败；compileall 与
  `git diff --check` 通过。

## Version 12：增加独立、可验收的根因分析阶段

完成日期：2026-08-10

### 科研阶段定位

- 确认 1a–2b 应位于人工接受问题之后、方法设计之前，作为同一个可回退的
  `root_cause_analysis` 阶段内部的四个推理操作，而不是拆成四个 workflow phase
  或四个平行 skill：1a 收集并描述能够直接表征该问题/失效的现象证据，1b 对
  现象分组，2a 深挖候选原因与替代解释，2b 形成证据校准、可证伪、可干预的
  因果链。1a 证据可来自已有实验、文献、数据、真实场景或必要的诊断性 pilot；
  失败实验不是强制前提。
- 正式顺序改为
  `problem_human_acceptance → root_cause_analysis → root_cause_gate → method_design`。
  `root_cause_gate` 是独立 Type-B 科研判断；只有 `DIAGNOSIS_READY` 可进入方法设计。
- 本版本没有实现 3a–4b 的方法—根因机制验证，也没有提前扩展实验规划或执行；
  只为后续验证保留稳定的 causal-chain ID、falsifier 和 intervention-target 接口。

### Artifact、hook 与确定性约束

- 新增共享合同 `root-cause-analysis-contract.md` 及 Codex 镜像，定义 1a–2b、
  JSON schema、独立 Gate 标准和返回路径。复用 `idea-creator`，增加
  `mode: diagnosis`，没有新增平行 skill。
- 新增 canonical artifacts：`ROOT_CAUSE_ANALYSIS.json`、忠实的
  `ROOT_CAUSE_ANALYSIS.md` 视图和 `ROOT_CAUSE_VERDICT.json`。分析绑定 run ID、
  analysis ID、problem ID、问题合同 hash、证据胶囊 hash、provenance、观察/分组/
  trace/chain ID 与 primary causal-chain IDs；verdict 绑定 reviewer、verdict ID、
  analysis ID 及三个被评审对象的 SHA-256。
- `arisctl.validators` 新增 Type-A schema、枚举、唯一 ID、跨对象引用、上游 hash、
  verdict provenance 及 Markdown 关键 ID/hash 可见性校验。科学因果是否成立仍由
  fresh independent reviewer 判断，未被机械 validator 越权替代。
- `tools/run_state.py` 与 Controller 都保存 validated artifact snapshot；根因 Gate、
  方法设计和方法精炼启动前重验当前文件 hash。文件存在但未验证、hash 被改动、
  verdict 非 `DIAGNOSIS_READY`、verdict ID/reviewer 不匹配时均 fail closed。
- 新增 workflow-declared `return_targets` 和 Controller `return-phase`，并收敛为
  唯一 verdict 映射：`DIAGNOSIS_READY → method_design`、
  `REVISE_DIAGNOSIS → root_cause_analysis`、
  `REOPEN_PROBLEM → problem_generation`。根因 Gate 不使用
  `HOLD/BLOCKED` 决定回退，也不增加 reason code；Agent 不能选择回退目标。
  旧文件保留审计，但被回退阶段的 artifact 注册失效，不能继续授权下游；没有
  引入第二套状态机。

### 同步范围

- 同步更新 canonical/Codex workflow、Controller phase order、`idea-creator`、
  `idea-discovery`、problem/method/refinement contracts、`research-refine`、
  `research-refine-pipeline`、Research Contract template、输出 composition 规则、
  `RESEARCH_HANDOFF_CN.md` 和 `AGENT_GUIDE.md`。
- 方法阶段不再重新发明 competing explanations；它必须从已验收的 primary causal
  chains、mechanism failures 与 intervention targets 推导 Scientific Mainline 和
  Design Obligations。若方法推理暴露诊断矛盾，正式返回诊断阶段。
- canonical workflow 内容发生变化，workflow hash 也随之变化。既有 formal run 不会
  被静默迁移或改写；需要按新 workflow 开启新 run，现有 state/ledger 未被修改。

### 验证

- 新增/更新回归覆盖：阶段顺序、manifest、1a–2b schema 与引用完整性、Markdown
  hook、非 READY verdict 拒绝、Controller 正式回退、verdict provenance 匹配、
  analysis 篡改阻断 method design、root-cause handoff 阻断 refinement、模板与主线/
  Codex 镜像一致性。
- 定向回归：`100 passed`。
- 全量回归：`565 passed, 66 skipped, 4 subtests passed`，零失败
  （`python -m pytest -q --cache-clear`）。
- `python -m compileall -q arisctl tools/run_state.py` 与 `git diff --check` 通过。

### Version 12 定向语义修订

- 按人工确认修正 1a 定义与根因 Gate verdict；Version 12 的独立阶段、artifact、
  hash/provenance hook、独立 Gate 和下游阻断主体设计保持不变。
- `failure_observations` 为兼容既有 schema 名称继续保留；每条现象证据新增必需的
  `evidence_source_type`，限定为 `existing_experiment | literature | dataset |
  real_world | diagnostic_pilot`。
- 新增可覆盖或删除、且不参与执行的说明文件
  `ROOT_CAUSE_STAGE_REVISION.md`。没有新增 Gate、Hook、State、Artifact、validator
  体系或平行架构。
- 定向回归覆盖五类 1a evidence source、旧 `HOLD` verdict 拒绝、两个固定回退和
  `DIAGNOSIS_READY` 前进路径：`100 passed`。
- 全量回归：`565 passed, 66 skipped, 4 subtests passed`，零失败；
  `python -m compileall -q arisctl tools/run_state.py` 与 `git diff --check` 通过。

### Version 12 `REOPEN_PROBLEM` 回退入口修正

- 将 `REOPEN_PROBLEM` 的唯一目标从仅重新确认原问题的
  `problem_human_acceptance` 修正为既有 `problem_generation`。
- Controller 继续复用现有 `return-phase`：清除问题生成至根因 Gate 区间的旧
  artifact 注册后，重新执行问题生成/修订、质量 Gate、新颖性 Gate 和人工接受；
  未新增阶段、Gate 或状态机。
- 定向回归：`55 passed`；全量回归：
  `565 passed, 66 skipped, 4 subtests passed`，零失败。

### Version 13：P0-3 正式实验链补齐机制验证闭环

- 复用既有 `/experiment-plan → /result-to-claim` 链路；未新增 3a/3b/4a/4b
  独立 phase、Gate、Subagent、Controller transition 或 state。
- `/experiment-plan` 在正式方法路由中读取已验收的
  `ROOT_CAUSE_ANALYSIS.json`、`ROOT_CAUSE_VERDICT.json` 和方法验证义务，输出
  `Mechanism Validation Map`：每个核心改动须关联因果链/义务、目标问题机制或
  失败现象、预期可观测变化、机制实验/指标及最终性能评价。只有需区分可独立主张
  的核心改动时才要求最小必要消融或受控比较。
- `/result-to-claim` 将机制证据表并入既有 reviewer 输入与规范化输出，并对每个
  核心改动记录性能状态、机制状态、证据路径与下一诊断动作。性能提升且机制符合才
  可支持原机制解释；性能提升而机制不符/未测只保留性能正结果；性能不佳则利用
  机制观测区分方法、实现/测量或前序分析问题。异常观测必须进入 `findings.md`
  作为后续科研证据。
- 同步更新 mainline/Codex skill、英文/中文实验模板及静态契约测试；没有改变既有
  artifact manifest、Gate 或正式流程终态。
- 回归：`python -m pytest -q -p no:cacheprovider tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py tests/test_aris_controller.py tests/test_run_state.py`
  → `102 passed`；`git diff --check` 通过。

### Version 14：P0-4 正式 Gate 请求、产物与审批绑定

- 正式 reviewer Gate 在 phase 启动时由 `ARISController` 发出当前 request，绑定
  run ID、phase/gate、允许 reviewer role、固定 verdict enum 和已注册 required input
  的 SHA-256。接受或回退前会重验 request、artifact bindings、输出 hash、reviewer
  role/模型独立性，并一次性消费工作区外的 reviewer attestation。
- coverage review 同步使用上述 request/外部 attestation 语义；review payload 必须
  带当前 run、request、reviewer/verdict、固定 decision 与精确 artifact-hash map。
  因此任意 workspace 文本、旧 request、伪造 reviewer 字符串或漂移 hash 均不能推进。
- 所有 formal Human Gate request/receipt 现在绑定当前输入 artifact hash map、request
  ID、明确 `approve` decision 和所需 selected ID；receipt 消费前后均复核 live request。
- `tools.run_state.accept(force=True)` 仅保留给无 workflow 的非结构化 legacy/development
  run；任何 declared workflow 或 Controller-managed formal run 都不能用 `force` 获得
  accepted 状态。未新增 stage、Gate、Subagent 或审批层。
- 回归：`python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py tests/test_run_state.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py`
  → `105 passed`；`python -m compileall -q arisctl tools/run_state.py` 与
  `git diff --check` 通过。

### Version 15：P0-5 下游禁止补造正式上游科研契约

- P0-5 经当前实现复核为真实问题：`experiment-plan` 曾在缺少文件时从 prompt
  推导，两个 `experiment-bridge` 镜像曾允许从计划/旧 idea 创建
  `idea-stage/docs/research_contract.md`。若运行上下文被视作正式流程，这会绕开
  已有的 Controller 上游验收与 provenance。
- 新增只读 `python -m arisctl validation-handoff <run_id>`；它不是 stage、Gate 或
  状态迁移，而是复用当前 Controller state、artifact registry、producer phase、run
  provenance、终态和 SHA-256，逐项验收当前 run 的问题合同、根因分析/裁决、最终
  方法、方法新颖性裁决和人工确认。任一缺失、来源错误、状态不合法或 hash 漂移即
  fail closed，并报告具体 artifact。
- 正式 `/experiment-plan` 和 `/experiment-bridge` 必须先消费该 handoff；计划记录
  run/workflow/artifact hash bindings，Bridge 再次核对。prompt、旧报告、兼容目录和
  模板均不能补写 `FINAL_PROPOSAL`、canonical `RESEARCH_CONTRACT` 或其他正式前置
  产物，也不能启动正式实验。
- 独立实验能力保留：没有 Controller-managed run 的明确用户请求可使用
  `NON_CANONICAL_AD_HOC`；旧 claims source 仅可作为带来源标识的
  `idea-stage/docs/research_contract.md`，不能注册进 Controller、写 `.aris` 状态、
  满足 formal handoff 或获得 canonical accepted。
- 回归：`python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py tests/test_run_state.py`
  → `107 passed`；`python -m compileall -q arisctl` 与 `git diff --check` 通过。
+
### Version 16：P0-6 收敛旧 `research-pipeline` 到 canonical 下游入口
- 旧 pipeline 曾以研究方向自主启动 idea discovery、维护独立 `run_state`、通过
  `AUTO_PROCEED`/超时自动选 idea，并直接进入 pilot、实验计划和实现；这会绕过
  Controller 的问题、根因、方法 Gate 与用户显式启动验证的边界。
- `research-pipeline` 及 Codex 镜像现在只接收 canonical `run_id`，先执行既有只读
  `validation-handoff`；仅消费其已验证的 run/workflow/artifact hash bindings，
  再依次交给 `/experiment-plan`、`/experiment-bridge` 和 `/result-to-claim`。
- handoff 失败即停止并回报 Controller `status`、`allowed-actions` 与
  `allowed-agents`；禁止自行补造上游产物、启动/恢复独立 `run_state`、自动选择 idea、
  超时批准、生成 pilot 或提前实现。该 skill 不支持 `NON_CANONICAL_AD_HOC`，也不再
  自动评审或自动写作。
- 同步调整 inventory 的陈旧断言：不再要求该 skill 接入旧 heartbeat/state 旁路，改为
  验证其 canonical handoff 与独立状态禁令。
- 定向回归：`python -m pytest -q -p no:cacheprovider tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py`
  -> `46 passed`；加入 Controller handoff 回归后，
  `python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py`
  -> `83 passed`；`python -m compileall -q arisctl` 与 `git diff --check` 通过。
+
### Version 16.1：P0-6 路由与 legacy 收尾
- 活跃 README/指南/目录不再把 `research-pipeline` 标为输入研究方向的一键全流程；
  它们统一使用 `/research-pipeline "<canonical-run-id>"`，并说明正式研究先经过
  Controller 的方法确认和用户显式验证启动。
- 未发现 `iteration_log.py` 的 shipped consumer。工具保留为 `LEGACY` 兼容能力；
  主线/Codex 的 cadence 和 integration contract 都明确其无 active caller，且不得接入
  Controller、`research-pipeline` 或 `idea-discovery`。未来恢复前必须设计新的
  Controller-aware consumer。
- 新增公开路由与 legacy helper 一致性测试；回归
  `python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py tests/test_iteration_log.py`
  -> `93 passed`；inventory、compileall 和 `git diff --check` 通过。

### Version 17：P0-7 回退与失效产物管理

- 既有 `return-phase` 原先只复位阶段状态并从 `accepted_artifacts` 移除记录；对应的旧文件仍留在
  active 工作区，既没有 `invalidated` 状态、archive provenance，也没有可选择的复用经验出口。
- 仅扩展现有 Controller 回退入口：对 workflow 已声明的 return target 到触发回退 Gate 的连续 phase
  范围，移动所有 Controller-owned produced artifacts 到
  `.aris/archive/<run-id>/return-<event-id>/artifacts/`，并让 active 注册表只保留未受影响的上游产物。
  这使用固定的 phase-order 范围，不引入全局 dependency graph、额外 stage、Gate 或 Subagent。
- state 新增 append-only `invalidated_artifacts` 与 `return_history`：每个历史记录带
  `status: invalidated`、原 SHA/provenance、archive path/状态及触发 verdict/reviewer/return target；
  archive 是审计用 provenance，resolver 与 default hook 只能消费 active registry。
- 可复用失败经验通过可选 `return-phase --lesson-file <json>` 明确提交。只有包含
  `failure_phenomenon`、`wrong_assumption_or_reason`、`evidence_refs` 和 `future_check` 的摘要才追加到
  `LESSONS_LEARNED.md`；没有经验价值的回退不写 lesson，且 lesson 不复制失效 artifact 内容、不作为证据或 handoff。
- `idea-creator` 主线/Codex 镜像现在只可在相关时将 lessons 作为反重复检查，并明确禁止将
  `.aris/archive/` 当作 active 输入；根因合同同步声明回退 archive/lesson 行为。
- 回归覆盖 `REOPEN_PROBLEM` 后 active 文件与注册表均不再保留旧合同/根因裁决、archive 可按
  return event 追溯、失效记录为 `invalidated`、同路径可重建新版本、lesson 只含摘要及 CLI
  `--lesson-file` 解析。`python -m compileall -q arisctl`、
  `python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py`
  （`84 passed`）、`tests/test_run_state.py`（`25 passed`）与 `git diff --check` 通过。
### Version 18：P0-8 问题版本锁定与显式修订

- 将已接受的 `RESEARCH_CONTRACT.md` 明确收敛为问题与证据边界；科学主线、设计义务、路线与方法新颖性从该契约移出，改由独立的 `METHOD_PROPOSAL_TEMPLATE.md` 和既有方法产物承载。
- `ARISController` 在 `problem_acceptance` Human Gate 后记录线性的 `problem_versions`、`active_problem_version`（问题 ID、版本、问题/证据 hash 和接受回执）。方法设计、路线选择、方法精炼只可消费当前记录；其 Controller-registered 输出写入相同的 `problem_version_binding`。
- 新增受 Codex UI 规则保护的 `python -m arisctl revise-problem <run_id> --reason "..."`。它仅可在已接受问题后的 Controller 边界执行，归档/失效从 `problem_generation` 起的既有有效产物，令旧版本 `superseded`，创建同一问题 ID 的下一版 `draft`，并回到既有问题生成、质量 Gate、新颖性 Gate 和 Human Gate；没有新增阶段或 dependency graph。
- 已有 `REOPEN_PROBLEM -> problem_generation` 回退同步产生上述 draft 版本语义；根因 1a–2b schema、Gate 和返回映射未改变。
- 定向回归覆盖：方法精炼前篡改已接受问题契约被 Controller 阻断；显式 revise 生成 v2 draft；v2 在重新 Human Gate 接受前没有 active problem version，不能进入正式下游；方法最终验证 handoff 再核对最终提案与当前问题版本绑定。
- 验证：`python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py`（85 passed）；后续全量/静态检查见本次 `CURRENT_REVISION.md`。
- 静态检查：`python -m compileall -q arisctl` 与 `git diff --check` 通过；全量 `pytest` 因 124 秒运行时限中止，未记为通过。

### Version 18.1：P0-8 流程收敛修正

- 将显式问题修订纳入既有 Human Gate 审批语义：Controller 先签发绑定当前问题契约和 evidence capsule hash 的 `problem_revision` 请求，再消费一次 Codex UI 回执；成功事件追加到既有 `scientific_core.approvals`，随后复用既有归档与回退到 `problem_generation` 的路径。
- 问题版本 hash 校验覆盖所有正式方法消费阶段：方法设计、路线人工选择、方法精炼、最终方法新颖性 Gate 及最终方法人工确认；最终 validation handoff 继续核对最终方法提案的版本绑定。
- `REOPEN_PROBLEM` 保持既有根因回退的候选替换能力：新一轮可接受不同的问题 ID 并产生 draft 版本；显式 `revise-problem` 则维持同一问题 ID 的连续版本语义。未增加根因 schema、Gate、阶段或依赖图。
- 定向回归：`python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py` → `85 passed`；`python -m compileall -q arisctl` 通过；`git diff --check` 无新增空白错误（仅既有 CRLF 警告）。

### Version 19：P01 接通正式 Reviewer 的执行与 attestation 通道

- 复核确认：Controller 原本已在正式 Gate 启动时签发绑定 `run_id`、角色、固定 verdict 枚举和当前 artifact hash 的 review request，并在接受或回退时复用 `arisctl.reviews.consume_review_attestation` 一次性消费；P01 的实际缺口仅是 Codex 未注册 workflow 已声明的正式 Reviewer、`SubagentStop` 未匹配这些角色，以及独立 Hook 对 editable install 的隐式依赖。
- 在 `.codex/config.toml` 注册 `independent_problem_reviewer`、`independent_novelty_reviewer`、`independent_root_cause_reviewer`、`independent_method_reviewer`；为其增加只读、无 shell/web、仅响应 live Controller request 的配置。它们返回既有 attestation 契约所需的 run/request、reviewer/verdict、decision 和精确 artifact hash map，决策仍由 Controller 消费。
- `SubagentStop` matcher 覆盖 reader、coverage reviewer 与四个正式 Reviewer；`subagent_attestation.py` 先由自身路径解析 checkout 并插入 `sys.path`，再复用 `arisctl.reviews.review_attestation_path`，不再依赖额外 editable install 或调用方 cwd。
- 新增配置覆盖测试和隔离导入测试（`-I -S`，无 site-packages；仅为 Controller 模块导入提供最小 `yaml` 占位），验证 Hook 能从 checkout 写入正式 reviewer attestation。既有 Controller 回归继续覆盖 request、角色、hash、verdict 不匹配时的拒绝，以及正式 Gate 的一次性消费链。
- 验证：`tests/test_aris_controller.py`（39 passed）、`tests/test_scientific_core_contract.py`（27 passed）、`tests/test_run_state.py`（25 passed）、`tests/test_codex_skill_mirror.py`（20 passed）；`python -m compileall -q arisctl .codex/hooks` 通过；`git diff --check` 通过（仅报告既有无关 CRLF 警告）。

### Version 20：P02 闭合 Reviewer 被审版本、attestation 与 verdict artifact

- 复核确认：P01 已能生成/消费正式 Reviewer attestation，但 problem quality、problem novelty、method refinement 与最终方法 novelty 的落盘 verdict 原先仅按文件存在登记；其 reviewer、request、decision 和 reviewed hash 没有与 attestation 闭合。尤其 method refinement 的 live request 只绑定上游输入，未绑定最终 `FINAL_PROPOSAL.md`。
- 新增最小共享 Type-A verdict 解析：两个 problem JSONL 均要求逐候选 `candidate_verdict` 和唯一 `phase_verdict`，且所有记录共用 request/reviewer/verdict/hash binding；phase decision 必须由至少一个逐候选结论支持。problem quality 使用 `CERTIFIED/HOLD/REJECT/BLOCKED`，problem novelty 使用 `NOVEL/UNCERTAIN/NOT_NOVEL/BLOCKED`，以 `NOVEL` 取代歧义的 `CONFIRMED`。
- `FINAL_BLIND_REVIEW.md` 与 `FINAL_METHOD_NOVELTY_VERDICT.md` 继续是既有 Markdown verdict artifact，但必须嵌入唯一 JSON metadata block。Controller 以同一 live request 核对其 request ID、reviewer、verdict ID、decision 与精确 hash map，再消费既有一次性 attestation。
- workflow 仅为 `method_refinement` 声明已有产物 `FINAL_PROPOSAL.md` 是 reviewed artifact。该 Gate 开始时保留同一 live request ID；完成后 Controller 立即把最终 proposal SHA-256 合入 request，并在接受 attestation 前复验落盘 blind verdict 与该 binding。未新增 Gate、状态、verdict 文件或第二条审核路径。
- 定向回归覆盖错误 request、reviewed hash、reviewer、verdict ID，以及篡改 blind/final novelty verdict artifact 的拒绝；正常 canonical 全链继续通过。
- 验证：`python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py::test_formal_gate_rejects_workspace_forgery_and_input_hash_drift tests/test_aris_controller.py::test_controller_drives_post_landscape_flow_and_waits_for_user_validation tests/test_aris_controller.py::test_explicit_problem_revision_creates_a_draft_version_and_requires_reacceptance tests/test_run_state.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py` → `75 passed`；其余 Controller 测试 → `37 passed, 2 deselected`；`python -m compileall -q arisctl tools/run_state.py` 通过；`git diff --check` 通过（仅既有无关 CRLF 警告）。

### Version 21：P03 一次性 Reviewer/Human 证明的可恢复消费

- 根因确认：`consume_ui_approval_receipt` 和 `consume_review_attestation` 在 Controller 后置校验、产物归档或 `run_state._save` 之前立刻把 live proof 改名为 `.consumed.json`；失败时 mutation 不保存，live request 仍在，但 proof 已不可重试。
- 在既有 `_StateStore.mutate` 上增加仅用于失败路径的恢复回调。Controller 成功消费 receipt/attestation 后，在同一 mutation 内注册对应 restore；body 内任一异常或最终 state save 失败都会将 `.consumed.json` 原子恢复为原 live path。state 保存成功则不恢复，原一次性 marker 仍生效。
- 所有正式 Reviewer/Human 消费入口均使用该路径：reviewer accept/return、coverage review、scientific-core Human approve、research-lit Human approve/source-policy revision，以及既有 explicit problem revision。未新增 receipt/attestation、Gate、状态机或通用事务服务。
- 新增恢复回归：Human 输出在消费后消失、同 family Reviewer、coverage audit 失败、模拟 state save 失败均保留同一 live proof；修复后使用同一 proof 可重试成功；成功后 live path 缺失且 `.consumed.json` 存在，重复消费被拒绝。
- 验证：P03 定向 `5 passed`；`tests/test_run_state.py` `25 passed`；source-policy revision 与 explicit problem revision `2 passed`；科学核心契约 `27 passed`；canonical 端到端 `test_controller_drives_post_landscape_flow_and_waits_for_user_validation` `1 passed`（26.35s，后台完成，避免命令窗口 30s 限制）；其余 Controller 后段 `11 passed`。`python -m compileall -q arisctl tests` 与 `git diff --check` 通过（仅既有无关 CRLF 警告）。
### Version 22：P04 正式 Reviewer 负向 verdict 回退闭环

- 已为 problem quality、problem novelty 与 final method novelty Gate 的跨阶段负向结论声明固定回退目标；Controller 仅在已验证的负向结论上暴露 `return_phase`，不会同时提供错误的接受旁路。
- 早期问题 Gate 回到 `problem_generation` 时不再错误要求一个尚不存在的 Human-accepted problem version；后段已有 accepted problem 的根因回退仍复用原有版本 supersede/draft 语义。
- `return_current_phase` 继续复用既有 attestation、归档、artifact invalidation、return history 与固定 phase-order 检查；最终方法新颖性负向结论统一回到 `method_design`。`method_refinement` 的非 READY 轮内结论仍在本 phase 内修订，不新增跨阶段 rollback。
- 验证：P04 定向回归与 canonical 正常流 `4 passed`；`tests/test_run_state.py` `25 passed`；`tests/test_scientific_core_contract.py` `28 passed`；`tests/test_codex_skill_mirror.py` `20 passed`；`python -m compileall -q arisctl tools` 与 `git diff --check` 通过（仅已有无关 CRLF 警告）。

### Version 23: P05 Human Gate rejection and revision paths

- Confirmed the root cause: all scientific Human Gates were hard-coded to accept only `approve`, so a refusal or requested revision had no receipt-bound Controller transition. The existing explicit `revise-problem` path did not cover an unaccepted problem, route selection, final method acceptance, or scope revision.
- Declared exactly one non-accepting decision, `request_revision`, for each existing Human Gate, with fixed return targets: scope -> `landscape` (implemented through the existing `QUERY_PLANNING` re-entry); problem -> `problem_generation`; route -> `method_design`; final method -> `method_refinement`.
- The Controller validates that decision before issuing a UI receipt. A declined Gate reuses the live request, input hash binding, one-time receipt consumption, existing archive/invalidation registry, and phase-order reset. It cannot accept a caller-selected target. Rejection does not require an output that is created only on acceptance.
- Scope revision re-enters the existing literature query-planning loop; core Human revisions archive the declared target-through-Gate artifacts and append the existing approval/return audit records. Normal `approve` behavior is unchanged.
- Verification: workflow mirrors match; targeted Human revision, canonical happy-path, state-machine, workflow-contract, CLI, and mirror tests passed (`49 passed`); `python -m compileall -q arisctl tools` and `git diff --check` passed. The latter reported only pre-existing unrelated CRLF warnings.

### Version 24: P06 scientific core formal incremental literature retrieval

- 根因确认：初始 `research-lit` 到 `LANDSCAPE_ACCEPTED` 后，scientific core 的 phase 虽然仍需 problem/method/final novelty 的针对性文献，但 query、admission、full-text 和 Evidence Card action 只接受早期 research-lit stage；相关 Skill 因而仍指示 hosted-web 直检索，无法产生正式可追溯证据。
- Controller 现在只在 workflow 声明的、尚未开始的 `problem_novelty_gate`、`method_design`、`method_refinement` 和 `final_method_novelty_gate` 开放现有 `submit_query_plan`。该 phase-scoped session 复用同一 source policy、预算、provider gateway、`SEARCH_LEDGER.jsonl`、`LITERATURE_CORPUS.jsonl`、`paper_reader` 与 `EVIDENCE_REGISTRY.jsonl`；完成读取后直接回到 `LANDSCAPE_ACCEPTED`，不新增 stage、provider、corpus/ledger 或 coverage Gate。
- 新 session 仅收集自身新生成的 Controller-accepted Evidence Cards。其 hash 在正式 Gate 开始时并入 review request；非 Gate method design 的输出则写入既有 upstream provenance snapshot。Controller 阻止 session 未完成时启动 core phase，防止检索与 Gate 并行造成未绑定或陈旧 review request。
- `AGENTS.md`、canonical workflow 与各实现镜像的 novelty/method/refinement Skill 统一要求 formal 检索走 `arisctl` gateway，移除相关 mainline Skill 的 `WebSearch/WebFetch` 权限；overlay novelty Skill 同样不再指示 hosted-web 作为正式证据路径。
- 验证：新增 Controller 回归覆盖 problem novelty 的完整增量 query → admission → read → Evidence Card → Gate request/输出 hash binding 路径、阶段阻断、同一 ledger/registry 与无重复 coverage；定向回归 `6 passed`，canonical end-to-end `1 passed`，`tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py tests/test_run_state.py` 为 `73 passed`。workflow mirrors match；`python -m compileall -q arisctl tools` 与 `git diff --check` 通过（后者仅报告既有 CRLF 警告）。

### Version 25: P07 Unified formal Problem Evidence Capsule contract

- Root cause: the workflow and Controller already registered independent `RESEARCH_CONTRACT.md` and `PROBLEM_EVIDENCE_CAPSULE.md` hashes, but Skill instructions and the Contract template allowed an embedded or omitted capsule form, creating dual authority at production time.
- Added the standalone `PROBLEM_EVIDENCE_CAPSULE_TEMPLATE.md`; changed the Contract template into a pointer-only link; synchronized main, Codex, and Gemini `idea-creator`/`idea-discovery` instructions to require the independent Contract + Capsule pair and prohibit an embedded duplicate.
- Reused the existing Human Gate, two-artifact hash registry, active problem version, and root-cause/method consumers; added no Gate, state, validator, artifact store, or alternate path.
- Verification: targeted P07 tests `3 passed`; canonical flow + run-state + scientific-core + Codex mirror regression `75 passed`; `python -m compileall -q arisctl tools` and scoped `git diff --check` passed.

### Version 25 follow-up: P07 production timing wording

- Confirmed and corrected a real documentation-contract conflict: Contract/Capsule are prepared after explicit problem selection and before the Controller records Human acceptance; the successful Human Gate then registers their authoritative hashes and active version.
- Unified that ordering across main, Codex, and Gemini `idea-creator`/`idea-discovery` Skills and both P07 templates. Added assertions so active Skills and templates cannot regress to an after-acceptance production instruction.
- Verification rerun: P07 targeted tests `3 passed`; canonical flow + run-state + scientific-core + Codex mirror regression `75 passed`; scoped `git diff --check` passed.

### Version 26: P08 candidate, verdict, Human selection and Contract/Capsule closure

- Root cause: the Controller registered files and stored a non-empty Human `selected_id`, but neither the candidate index nor the two problem verdicts established an identity chain. A selection could name a non-candidate or a candidate that had not passed both Gates, while Contract/Capsule text was never checked against that selected problem or the exact upstream verdict artifacts.
- `PROBLEM_CANDIDATES.jsonl` now has the minimal Controller-consumed identity index: unique `problem_id` and enumerated `source_class`. The problem-generation hook records its candidate IDs. Quality verdicts must cover that exact set; novelty verdicts must cover exactly the quality survivors. Both phase records declare exact `survivor_ids`, derived from candidate decisions, without scoring Reality, Importance, Unresolvedness, or novelty.
- At problem Human acceptance, Controller requires `selected_id` to be a novelty survivor, validates Contract references to the registered candidate/quality/novelty artifacts (path, SHA-256, verdict ID), and validates Capsule problem ID plus linked Contract path/SHA-256. The existing UI receipt now also binds the current Contract/Capsule hashes, alongside the existing upstream review binding.
- No new Gate, state, evidence registry, verdict type, transition path, or scientific scoring rule was introduced. The canonical and Codex workflow mirrors and the problem-discovery contract describe the same fields.
- Verification: targeted candidate closure, Human receipt recovery, revision/return flow, canonical flow, run-state dependency check, scientific-core contract, and skill mirror tests: `56 passed`; `python -m py_compile arisctl/controller.py arisctl/validators.py tools/run_state.py tests/test_aris_controller.py tests/test_run_state.py` and `git diff --check` passed (only pre-existing unrelated CRLF warnings).

### Version 27: P09 Root-Cause Analysis 与当前问题/证据引用闭合

- 根因确认：根因分析虽已绑定 Contract/Capsule 哈希并校验内部 observation/cluster/trace/chain 引用，但 `problem_id` 未与 active accepted problem 对照；所有外部 `evidence_refs` 和 `source_artifact_ids` 仅被当作非空字符串。因此来自其他问题、失效 Evidence Card 或不存在源文件的引用仍可随分析推进。
- 根因阶段现在从 active problem version、Contract 和 Capsule 读取唯一问题 ID，并只接受 Capsule 中列出且仍与 Controller-accepted Evidence Registry Card 匹配的文献 ID。所有现象、因果 trace、因果链和 provenance 的外部引用均解析到该集合；这仍是 Type-A 身份/哈希校验，不评判因果解释的科学充分性。
- 为诊断所需的既有实验、数据集、真实观察和 diagnostic pilot，`analysis_provenance.source_artifacts` 声明稳定 ID、项目内路径、SHA-256 与来源类型。Controller 在接受分析时把这些已验证文件登记到既有 artifact registry 并绑定 active problem version；Root-Cause Gate 的 review request 也绑定其哈希，任何篡改在 Gate 完成前即被阻断。没有新建 evidence system、Gate、阶段或旁路。
- 更新 Capsule 模板和主/Codex root-cause contract，明确 Capsule 文献 ID 与非文献 artifact 注册语义；新增覆盖五种合法来源、错误 active problem、其他问题/不存在证据引用、诊断 pilot 注册、Gate 哈希绑定与篡改阻断的测试。
- 验证：`python -m pytest -q -p no:cacheprovider tests/test_aris_controller.py::test_root_cause_analysis_closes_current_problem_and_formal_evidence_references tests/test_aris_controller.py::test_root_cause_registers_nonliterature_evidence_and_binds_it_to_review tests/test_aris_controller.py::test_controller_drives_post_landscape_flow_and_waits_for_user_validation tests/test_run_state.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py` → `81 passed`；`python -m compileall -q arisctl tools/run_state.py tests/test_aris_controller.py` 通过；`git diff --check` 通过（仅报告既有无关 CRLF 警告）。

### Version 27 follow-up: P09 非文献证据边界收敛

- 复核发现此前 `source_artifacts` 允许根因分析同时新增 existing experiment、dataset、real-world 与 diagnostic pilot，造成“接受问题时既有证据”和“根因阶段新采集诊断证据”身份不对称；且已有 artifact registry 记录无法被直接复用。
- 现将既有实验、数据集、真实观察限定为双重闭合：必须列于当前 Capsule，且已有 artifact registry 记录携带完全匹配的 active problem-version binding。根因分析仅解析复用，不会现场登记它们。
- 仅保留 `analysis_provenance.new_diagnostic_pilot_artifacts` 作为 1a 可新增证据；其类型固定为 `diagnostic_pilot`，明确是为诊断新采集而非伪装为 accepted-problem 既有证据。它仍在分析接受时复用现有 artifact registry 登记，并进入既有 Root-Cause Gate 哈希绑定以防审阅证据漂移。
- 补齐既有非文献证据的可达登记时点：Capsule 在问题 Human Gate 前以可选 `Registered Non-Literature Artifacts` JSON block 声明 existing experiment、dataset 或 real-world 文件；成功接受时 Controller 校验路径/hash 并登记到既有 artifact registry，随后才可由 root-cause 分析复用。新增端到端回归覆盖该路径，非 pilot 不能走新增诊断登记面。最终相关回归 `83 passed`；编译和 `git diff --check` 通过（仅既有无关 CRLF 警告）。

### Version 28: P10 问题/根因到最终方法路线引用闭合

- 根因确认：Controller 先前只在已注册的 method artifacts 外层附加 active problem-version binding；`METHOD_ROUTES.*`、`SELECTED_ROUTE.yaml` 与 `FINAL_PROPOSAL.md` 的内部 route/problem/root-cause 字段未解析，Human `selected_id` 也没有与选择文件比对。因此文件存在且哈希未变时，错误问题/根因、重复或不存在 route，或最终提案换路仍可推进。
- `METHOD_ROUTES.jsonl` 现在是最小 machine index：唯一 `route_id`、当前 problem version/两项 hash、root-cause analysis ID/hash、primary causal-chain IDs 以及能解析回这些链的唯一 obligation IDs。`METHOD_ROUTES.md` 必须公开相同的闭合标识；不评价路线或 obligation 的科学质量。
- 既有 `route_selection` Human Gate 在签发回执前核对 `SELECTED_ROUTE.yaml` 的完整 problem/root-cause binding、route、causal-chain 和 obligation 集合；`selected_id` 必须等于该已存在 route。选择文件的 hash 被纳入既有 Human receipt binding，CLI 同样在创建 receipt 前传入并验证 selected ID，避免错误 receipt 造成重试阻塞。
- `method_refinement` 完成时复用相同 index/selection 解析，并要求 `FINAL_PROPOSAL.md` 的类型化 Markdown 字段仍绑定当前问题、已接受根因和 selected route，且其链/obligation 引用能解析到该 route。未新增 Gate、Reviewer、评分器、method-search artifact 或状态机。
- 更新方法设计/精炼主与 Codex 镜像契约和 `METHOD_PROPOSAL_TEMPLATE.md`，只说明上述可验证的 handoff 字段。验证：重复 route ID 的直接 validator 测试；canonical flow 中错误 problem hash、不存在 route、Human selection 不匹配、final proposal 换 route 均被阻断，正确路线完整通过。定向回归 `76 passed`；`compileall` 与 `git diff --check` 通过（仅已有无关 CRLF 警告）。

### Version 29: P11 验证结果回接 canonical 状态与回退闭环

- 根因确认：最终方法接受后仅有 read-only `validation-handoff`，没有可绑定的 handoff 身份、验证结果登记入口或回到 canonical phase 的受约束路径；`result-to-claim` 的诊断只能留在普通工作区文件。
- `validation-handoff` 现在返回 run/workflow/accepted-artifact/problem-version 的确定性 `handoff_sha256`。用户显式提交的 validation result 必须绑定当前 run、workflow 和 handoff，并列出项目内、SHA-256 匹配的实验/诊断证据；错误 run、变更后的 artifact、旧 handoff 或普通 findings 均不能触发状态迁移。
- 初版只允许四个固定结果：`VALIDATED` 正式关闭为 `VALIDATION_CONFIRMED`；`METHOD_MISMATCH` 固定回 `method_refinement`；`ROOT_CAUSE_REJECTED` 固定回 `root_cause_analysis`；`PROBLEM_PREMISE_REJECTED` 固定回 `problem_generation`。后续路线级复核已将歧义的 `METHOD_MISMATCH` 拆分，见 Version 29 route follow-up。
- 抽取正式 Gate return 与 validation return 共用的内部 canonical return 实现；没有新增 validation phase、Reviewer、Gate、证据体系或平行 state machine。更新 main/Codex research-pipeline 与 result-to-claim 直接契约，要求写出并由用户提交 binding result JSON。
- 验证：P11 + 完整 canonical flow 定向 `6 passed`；科学核心契约、Codex mirror 与 run-state 回归 `74 passed`；`compileall` 和 `git diff --check` 通过（后者仅已有无关 CRLF 警告）。

### Version 29 follow-up: P11 formal handoff issuance audit

- 复核发现 hash 校验本身不足以证明 validation 已由用户显式开始：初版没有保存 Controller 签发 handoff 的 live record，掌握当前 hash 的调用者可直接构造结果。
- `validation-handoff` 现仅在最终方法确认后，把现有 `validation_entry` 标记为 `HANDOFF_ISSUED` 并登记完整 handoff；提交结果前必须与这一当前 record 完整匹配。未签发、错误 run、错误/旧 handoff、或 handoff 后 accepted artifact 改变均不能触发回退。
- 不新增 phase、Gate 或平行状态机；这只是既有 validation entry 的最小显式启动记录。补充并通过未签发结果、错误 run 与产物变更后的 stale handoff 回归；P11 + canonical flow `6 passed`，科学核心/镜像/run-state `74 passed`，编译与 diff 检查通过。

### Version 29 route follow-up: P11 方法路线级失败回退

- 复核确认 `METHOD_MISMATCH -> method_refinement` 是真实语义缺口：refinement 只能消费既有 `SELECTED_ROUTE.yaml` 并修改路线内 proposal，不能重建路线集合或重新执行 Human route selection；验证若否定路线主体，会被困在错误路线。
- 将其拆为两个固定、不可由调用者选择 target 的结论：`METHOD_REFINEMENT_REQUIRED -> method_refinement`（路线仍成立的路线内修订）与 `METHOD_ROUTE_REJECTED -> method_design`（路线被否定，重新设计并经既有 route Human Gate 选择）。根因与问题前提结论保持原固定回退。
- `method_design` return 复用已有 phase-order archive/invalidation：旧 `METHOD_ROUTES.*`、`SELECTED_ROUTE.yaml`、final proposal、novelty verdict 与 final acceptance 均被失效，随后正常 canonical flow 重新产生路线和 Human selection；未增加新阶段、Gate 或自由 rollback。
- 验证：P11 + 完整 canonical flow 定向 `7 passed`；scientific-core contract、Codex mirror、run-state `74 passed`；`compileall` 与 `git diff --check` 通过（仅已有无关 CRLF 警告）。

### Version 29 final P11 audit

- 逐项复核 handoff 签发、current hash binding、结果证据、五种固定语义、archive/invalidation、problem-version 和恢复推进路径，未发现新的 P11 状态旁路、死锁或错误回退 target。
- 修正 Controller 顶部遗留的“read-only handoff”注释，准确反映已实现的 Controller-issued `HANDOFF_ISSUED` 语义；无功能性扩张。
- 最终回归：P11 + 完整 canonical flow `7 passed`；scientific-core contract、Codex mirror、run-state `74 passed`；`compileall` 和 `git diff --check` 通过（后者仅已有无关 CRLF 警告）。

### Version 30: P12 research-lit 产物唯一 ID 与交叉引用闭合

- 根因确认：Evidence Card 的 `source_id` 虽在 Controller 中与准入论文关联，但 Validator 未显式以已接受卡集合拒绝重复 ID；Active Field Map 仅检查必填顶层字段，未解析 method family、bottleneck、矩阵和 Evidence Registry 之间的引用；离线 landscape audit 也不会发现重复 Evidence Card ID 或 canonical Field Map 中的悬空引用。
- `validate_evidence_card` 现在验证非空 Evidence ID，并由 Controller 传入既有 accepted Evidence IDs 做唯一性校验。`validate_field_map` 复用现有 Field Map 结构，校验 method family/bottleneck 的唯一 ID，并将 family、problem、method 与当前 ID 集合解析；development trace 与 assumption/effectiveness/failure matrix 的 Evidence IDs 必须唯一且能解析至当前已接受 Evidence Card。未判断 taxonomy、证据真实性或 coverage。
- `literature_coverage_audit.py` 复用同一 Validator 解析 Controller 渲染的 Field Map，检查 Evidence Registry 的重复 `source_id` 和所有上述下游引用；保留未结构化 legacy handoff 的既有审计路径。未增加 Gate、Reviewer、coverage 规则或状态转换。
- 验证：P12 负向/恢复与 canonical flow、scientific-core contract、run-state 回归 `57 passed`；`python -m compileall -q arisctl tools tests` 和 scoped `git diff --check` 通过。

### Version 31: P13 公开文档、Skill 目录与 canonical workflow 同步

- 根因确认：Controller/workflow 早已在最终方法人工确认后停于 `METHOD_CONFIRMED_AWAITING_USER_VALIDATION`，并要求用户显式签发 `validation-handoff`；但 README、Agent Guide、Skill Catalog 和交接文档仍把 discovery、实验、review、写作描述为自动端到端链，`idea-discovery` 被错误标为产出实验计划，catalog 的 `research-pipeline -> auto-review-loop` 旧依赖也因此失真并导致目录测试失败。
- 仅同步公开边界与命名：`idea-discovery` 现在明确以问题优先的 Field Map→人工范围/问题/路线确认→根因与方法 Gates 为主线，终止于方法确认；`research-pipeline` 只以 canonical run ID 在用户启动验证后继续 `/experiment-plan`、`/experiment-bridge`、`/result-to-claim`。独立 review、论文和 ad-hoc 实验仍可使用，但不是 formal continuation。
- `SEARCH_LOG.md` 统一为 Controller artifact manifest 的 `SEARCH_LEDGER.jsonl`；中文交接文档同步主动检索的高引用/批准顶会 active-reading 门槛，以及 `USER_SUPPLIED_READ` 必须在阅读后另行评估的规则。未改变 source-admission policy 本身。
- `tools/skill-groups.tsv` 的 `research-pipeline` 默认依赖收敛到真实三段；新增测试固定该集合，并回归保护公开入口、artifact 名称、source-policy 语义和 final validation 边界。
- 验证：catalog + scientific-core + Codex mirror 定向回归 `57 passed`；全量 `python -m pytest -q` 通过（`lastfailed` cache 为空）；`git diff --check` 通过（仅既有无关 CRLF 警告）。未修改 Controller、Gate、Hook、State、Artifact schema 或 Validator，未新增状态、死锁或旁路。

### Version 31 follow-up: P13 历史入口去歧义

- 审计发现 README 中两条未标注废弃的历史 release note 仍直接把 `/research-pipeline` 描述成 discovery→review→paper 的自动链，或称三大工作流“端到端贯通”。这会与当前公开入口冲突，不能满足 P13 的严格无旧链说明标准。
- 两处均改为明确的 pre-Controller 归档记录，直接指向当前 Controller 主线和用户显式 validation handoff；新增 scientific-core 公共路由断言，防止旧表述重新出现。无运行时改动。

### Version 32: final-audit P0-1/P0-2 reviewer installation and transport

- Root cause: `.codex/config.toml` declared four scientific-core reviewers, but `install_project_codex_layer()` copied only `paper_reader` and `coverage_reviewer`; generated project instructions also prohibited the missing roles. Even if copied manually, those local Codex agents had no actual cross-family judgment transport while Controller correctly rejected same-family acceptance.
- The project-local managed layer now installs all declared agent TOMLs and the existing `gemini-review` MCP server. Generated `AGENTS.md` permits the reviewer role named by the live Controller request instead of a two-role allowlist.
- The four scientific reviewer agents are explicitly transport-isolated: they call the installed Gemini bridge, poll the external review, use the bridge-returned model identity, and emit no formal verdict when transport fails. The existing Controller request, artifact-hash binding, one-time SubagentStop attestation, verdict schema, and cross-family invariant are unchanged.
- Added an install-to-temporary-project regression that verifies every config-declared agent exists, the bridge is managed and executable, and project instructions expose the actual workflow roles. Directed regression: `4 passed`.

### Version 32.1: final-audit P0-3 Gemini overlay canonical-flow repair

- Root cause: the last-installed Gemini overlay replaced the base `idea-discovery`/`idea-creator` skills, but its flow jumped from human problem acceptance directly to method design and exposed only `problem|method` modes. This conflicted with the Controller phase graph and bypassed the methodology's mandatory 1a–2b diagnosis.
- The overlay now preserves the shared canonical sequence: problem quality/novelty → human problem acceptance → `mode: diagnosis` → independent root-cause Gate → method design. The diagnosis mode produces the existing root-cause artifacts and cannot issue its own verdict or design a method; method mode requires the current accepted analysis and `DIAGNOSIS_READY` verdict.
- Final method acceptance still terminates at `METHOD_CONFIRMED_AWAITING_USER_VALIDATION`; no phase, Gate, state, artifact type, or reviewer was added. Directed scientific-core/mirror regression: `21 passed`.

### Version 32.2: final-audit P0-4 query lifecycle closure

- Root cause: automatic attempts incremented `query_count`, while human completion wrote only per-paper metadata rows; unattempted planned queries routed into a human batch had synthetic IDs without budget accounting; provider recovery allocated a new query ID. The final audit counted only terminal query rows, so every documented recovery path could end with a counter/ledger mismatch.
- Every planned query now receives one normal budgeted `Qxxxx` identity. Human batch completion appends one terminal `complete_human` query row per requested query even for zero results, while retaining per-paper metadata rows. Provider recovery reuses the same query identity and does not consume a second budget slot.
- The landscape audit accepts `complete_human` as a terminal query outcome but retains the exact counter-to-terminal-ID equality check. No fallback source, Human Search boundary, coverage standard, Gate, or state was removed.
- Complete directed paths for all-provider failure/manual search, lower-priority success/manual follow-up, and credential recovery now reach and pass coverage review; batch accounting is also fixed. Directed regression: `4 passed`.

### Version 32.3: final-audit P1-1 bounded decision-grade source exception

- Root cause: the high-citation/elite-venue active-reading gate had no path for the exact low-citation sources most capable of changing unresolvedness or novelty judgments: verified concurrent closest prior work, negative/contradictory findings, and diagnostic/replication evidence.
- The default hard gate remains. Controller and CLI now accept only three fixed exception kinds, and only for identity-verified, in-scope papers with a recorded scientific reason and explicit decision targets. Recency or relevance alone is insufficient. The exception is recorded on the paper and in the search ledger; the source must still pass normal full-text reading and Evidence Card validation before it becomes decision-grade evidence.
- Main, Codex mirror, Gemini overlay, and the shared source policy now use the same semantics. No Human Gate, Reviewer, state, artifact type, or separate evidence path was added. Directed admission/policy/mirror regression: `23 passed`.

### Version 32.4: final remediation regression and affected-scope global review

- Shared Controller/scientific-core/project-install/mirror/run-state regression passed `144` tests. Full regression passed `610` tests with `66` expected skips and `4` passing subtests. `compileall` and `git diff --check` passed; only pre-existing unrelated CRLF warnings remain.
- The final affected-scope review found no new P0/P1: reviewer installation and external transport align with the workflow roles; Gemini retains the 1a–2b/root-cause sequence; all human/provider recovery routes close one query lifecycle; the admission exception is narrow and does not bypass full-text/Evidence validation.
- Existing Human Gates, cross-family scientific review, artifact bindings, fixed return targets, and user-initiated validation boundary remain intact. Impedance Control research-lit E2E is the next step.

### Version 32.5: Impedance Control research-lit E2E start

- Started a fresh formal run `impedance-control-landscape-e2e` in `D:\桌面\科研Agent Harness设计\impedance-control-e2e` through `python -m arisctl start`, using the canonical workflow and `codex-gpt-5.6-sol` executor.
- Main prepared a bounded research brief and an impedance-control-specific source policy covering classical/variable/adaptive/learning impedance and admittance control, stability/passivity, contact-rich manipulation, pHRI/teleoperation, and relevant whole-body interaction. The policy retains the default citation/elite-venue gate and the three bounded decision-grade exceptions.
- Controller validation passed and canonicalized the policy. The run is correctly paused at `WAITING_FOR_HUMAN` for `source_policy_approval`, bound to request `03ad534c62e64e1c8cfa7d889eabc69d` and policy SHA-256 `85e35b40432b2e1ed10a10dd7773d3e034c3fb5eb86707a525c151c8d5055f48`.
- No approval receipt was created. Current allowed actions are exactly approve or request revision; no agent is allowed to continue. The project-local installation contains all six agent roles and the Gemini review bridge.

### Version 32.6: E2E CLI Unicode output boundary

- The approved Impedance Control E2E reached its first real metadata query. SerpApi Google Scholar completed successfully and Controller committed Q0001 plus 20 discovery records, but the CLI then raised `UnicodeEncodeError` while printing an en dash through the Windows GBK text stream and returned exit code 1.
- Root cause was limited to the CLI presentation boundary: every command used `print()` with `ensure_ascii=False`, thereby inheriting the host code page after the state mutation had already committed. An autonomous caller could therefore misclassify a successful query as failed, while a retry was correctly rejected as already attempted.
- CLI output now writes UTF-8 through the underlying byte stream when available and falls back to the current text stream only for capture objects without `.buffer`. Controller, provider cascade, query accounting, artifacts, Gate/state semantics, and the already-completed Q0001 were not changed or replayed.
- Added a focused regression using a GBK `TextIOWrapper` and a non-GBK en dash to prove that emitted JSON remains valid UTF-8.

### Version 32.7: E2E full-text fallback waits for automatic attempts

- The first two open-access reads completed, but the next unavailable PDF immediately moved the run to `HUMAN_SEARCH_REQUIRED` and requested all 14 admitted papers. The batch wrongly included both completed read events because it treated only accepted Evidence Cards or user files as proof that full text had already been obtained. It also stopped before the remaining automatic full-text routes had been attempted.
- A completed read event now excludes that paper from a human full-text batch. Provider unavailability is recorded per paper while the run remains in `PAPER_READING` if any admitted paper still has an untried automatic route. Once successful reads have Evidence Cards and every remaining paper has a recorded provider failure, `finish_reading` creates one batch containing only the actual failures.
- No Gate, stage, action, artifact, provider, or reviewer was added. Existing one-shot batch submission and the rule that every admitted paper requires an Evidence Card remain unchanged.
- Directed regression for immediate single-paper fallback, deferred multi-paper fallback, evidence-free blocking, and UTF-8 CLI output passed `4` tests. The live E2E state was atomically repaired by removing only the obsolete premature request and restoring `PAPER_READING`; its three read attempts, two completed events, one AQ failure, counters, and ledgers were preserved.

### Version 32.8: E2E Crossref exact-title disambiguation

- A downloaded public PDF exposed two Crossref records with the same normalized title and authors: an IJRR journal article and a Springer chapter. The metadata verifier previously selected the first exact-title result, so a discovery record could be marked verified with the wrong venue and DOI and later bind full-text evidence to the wrong version.
- Exact-title matching remains mandatory. When Crossref returns multiple exact-title records, the verifier now ranks them only by existing discovery identity signals: exact DOI, venue-token overlap, publication-year agreement, and author-family overlap. A tie is rejected as `verify_failed` instead of guessing. Single exact-title results retain the existing behavior.
- No source-policy rule, provider, Gate, State, Artifact, Validator, Reviewer, or Human checkpoint was added. The change strengthens source identity without changing admission or evidence judgment.
- Regression added for correct duplicate-title selection and unresolved ambiguity. Shared research-lit gateway, Controller, and CLI regression passed `91 tests`.

### Version 32.9: E2E admitted-source correction without workflow migration

- The user removed one already-admitted paper during `PAPER_READING`. The previous Controller had no formal way to retract it, so `finish_reading` would permanently require its full text even though the research scope had been corrected.
- Added two non-advancing Controller corrections available only during `PAPER_READING` or a pending human full-text batch: `withdraw_admission` records `EXCLUDE_USER_WITHDRAWN` in Corpus/Ledger, and `reverify_admission` corrects a verified identity while preserving previous/corrected metadata snapshots. Both reject papers with accepted Evidence Cards. A pending batch is updated in place; withdrawing its final paper resumes `PAPER_READING`.
- These corrections are exposed dynamically by the Controller rather than added to `idea-workflow.yaml`, so existing formal runs retain their immutable workflow hash and no in-place workflow migration or state-file rewrite is introduced. Primary workflow actions and all transition semantics remain unchanged.
- Live run: `kg4YFrTouZMJ` was formally withdrawn. Local PDF audit found the Hogan file is the wrong conference paper, while the downloaded 1998 Cheah/Wang journal article is correct but the old verifier had bound its 1995 conference counterpart. The new re-verification route failed closed on two Crossref network errors and did not mutate live identity.
- Shared research-lit gateways, CLI, and Controller regression passed `94 tests`.

### Version 32.10: E2E paper-reader attestation Unicode boundary

- The first live `paper_reader` Evidence Card exposed a Windows-only provenance failure: the SubagentStop hook could decode UTF-8 JSON through the active locale before hashing, and its machine receipt could fail while serializing a Unicode project path. The research content was valid, but Controller submission could not reliably consume the Hook receipt.
- The hook now decodes the incoming event directly from `stdin.buffer` as UTF-8 (accepting an optional BOM) and writes the attestation as UTF-8 JSON with ASCII escapes. The Evidence Card canonicalization and SHA-256 calculation remain unchanged, and JSON readers reconstruct the original project path and agent metadata.
- No Gate, stage, role, evidence schema, Controller transition, or scientific decision rule changed. A focused regression sends UTF-8 bytes containing a Unicode project path and verifies a readable receipt with the exact original value; the four hook-focused tests pass.
- Live E2E confirmation: the exact returned `paper_reader` payloads for `LJMBf6MAPHQJ` and `dqYs440MKMMJ` passed the repaired Hook, Evidence Validator, read-event/SHA binding, and Controller acceptance.

### Version 32.11: E2E rediscovery preserves formal paper state

- A coverage-driven exact-title query re-discovered six papers that already had accepted Evidence Cards. The old query ingestion replaced each whole paper object with fresh discovery metadata, rolling `verified` identity, `ADMIT_DECISION_GRADE`, and verification provenance back to `verify_pending`/`DISCOVERY_METADATA_ONLY` while leaving the accepted Evidence Artifact intact.
- Automatic and human-search ingestion now merge repeated discovery non-destructively once a paper has a verified identity or any formal admission/withdrawal decision. Only discovery counters/snippets/provider metadata are refreshable; query IDs are unioned, while identity, admission, user-fulltext, and later provenance remain authoritative.
- `finish_retrieval` also repairs the pre-fix live inconsistency only when an accepted Evidence Artifact exists and the append-only formal Corpus contains a matching `verified + ADMIT_DECISION_GRADE` snapshot; absence of such a snapshot fails closed. Repair appends explicit Corpus and Ledger records.
- No Gate, State, Reviewer, source threshold, exception kind, or evidence rule changed. Directed prevention, pre-fix recovery, and human-fallback landscape tests pass `3 passed`; shared research-lit gateway, CLI, and Controller regression passes `97 passed`. The six live records were restored through the Controller-owned retrieval transition.

### Version 32.12: E2E later user-supplied full text for a known paper

- The second coverage cycle exposed a missing correction path: a paper already present as discovery metadata could later be explicitly supplied by the user, but `register_user_source` accepted only a new ID during metadata retrieval and the pending full-text batch accepted only its exact requested admitted set. A relevant user-supplied paper therefore could not enter the policy's existing `USER_SUPPLIED_READ` track without relabelling metadata or misusing a decision-grade exception.
- Added `promote_user_source`, a non-advancing Controller correction available only during `PAPER_READING` or a pending human full-text batch. It accepts only a known discovery-only paper, a nonempty file under `source-materials/`, an explicit scientific reason, verified identity (or a verifier that produces one), and no accepted Evidence Card. It preserves the original discovery origin/query provenance, binds the local file hash, records `USER_SUPPLIED_READ`, and appends Corpus/Ledger provenance.
- The action is exposed dynamically, like the existing admission corrections, so the immutable workflow snapshot and existing formal runs require no migration. It does not alter citation thresholds, bounded exception kinds, Evidence Card validation, Hook attestation, or coverage review.
- Live E2E used the route for the explicitly supplied 2014 optimal-interaction paper and 2021 inverse-RL variable-impedance paper. The latter failed closed when Crossref was unavailable, then was identity-verified from the supplied PDF front matter (exact title, four authors, venue, year, and DOI) before promotion.
- Shared research-lit gateway, CLI, and Controller regression passes `99 passed`; Controller-specific regression passes `76 passed`. `compileall` and scoped `git diff --check` pass apart from pre-existing unrelated CRLF warnings.

### Version 32.13: E2E reconciled Corpus receipt contamination

- The second coverage verdict was scientifically `CANDIDATE_SUFFICIENT`, but the final landscape audit failed closed because six Corpus rows written by the E2E-7 reconciliation had invalid record hashes. The reconciliation copied old `previous_record_sha256`/`record_sha256` receipts from formal snapshots into live paper objects, and `append_jsonl` included the old `record_sha256` as semantic input before overwriting it with the new receipt.
- `append_jsonl` now strips caller-supplied chain fields at the write boundary. Reconciliation also removes snapshot receipts before restoring live paper state, preventing both the immediate defect and later propagation through paper-level appends.
- Added a deliberately narrow repair: every invalid row must reproduce exactly when a prior hash from the same paper is embedded as the legacy semantic `record_sha256`; broken links, malformed rows, or any other hash mismatch remain rejected. Controller permits the repair only during a live Coverage Review, archives the original Corpus by SHA-256, rebuilds only machine chain fields atomically, strips leaked receipts from live paper state, and records before/after hashes plus affected rows in the Search Ledger.
- Live repair matched exactly rows 340-345, archived Corpus SHA `43147efd...`, rebuilt 353 rows to SHA `232c1453...`, and then passed the global coverage audit. No scientific content, Evidence Card, Field Map, Gate, admission, or reviewer decision changed.
- Final full regression after the repair passed `622 passed, 66 skipped, 4 subtests passed`; `compileall` and scoped `git diff --check` passed.

### Version 32.14: remove the unused source-policy `risk_rules` requirement

- The source-policy Validator and canonical YAML template already treat the policy as a literature-admission contract and never require or consume `risk_rules`; only the shared prose contract still claimed that the field was mandatory.
- Removed that stale requirement from both the main and Codex-mirror shared references, and removed the residual `risk_rules` block from the impedance-control project candidate policy. The approved live policy already omitted the field, so no policy reapproval, hash migration, State rewrite, or run transition is required.
- No dedicated negative regression was added: the removal is a prose/policy cleanup, and the existing main/Codex mirror check already guards synchronization. The focused existing contract and mirror suite passes `21 passed`; `compileall` passes.
- Per the user's revised scope, Codex project-level approval configuration and the current `paper_reader` dispatch/approval behavior were intentionally left unchanged. No Gate, Hook, State, Artifact, Validator threshold, Reviewer, or evidence rule was changed.

### Version 32.15: arXiv-only automatic full-text acquisition

- The canonical `fetch-fulltext` gateway previously tried arXiv, Crossref, OpenAlex, and Semantic Scholar for each admitted paper. This conflicted with the project operating policy because non-arXiv publisher literature is rarely obtainable automatically and repeated provider probing adds cost without improving the corpus.
- The existing gateway entry point now delegates only to the declared-arXiv downloader. The research-lit contract instructs Main to partition unread admitted papers once: fetch declared arXiv identities automatically and pass all non-arXiv IDs together to the existing `defer-fulltext-batch` action without publisher, Crossref, OpenAlex, Semantic Scholar, or Web PDF probing.
- The existing Controller behavior remains authoritative: after arXiv Evidence Cards are accepted, one `finish-reading` call creates one `HUMAN_SEARCH_REQUIRED` batch containing every deferred non-arXiv paper plus any failed arXiv download; the target remains `source-materials/` and the user returns one manifest.
- Reused the existing Gateway, State, batch request, manifest ingestion, read-event binding, and Evidence validation. No new Gate, State, Artifact, Validator, Reviewer, receipt, or module was added. Relevant Gateway/CLI/Controller/mirror regression passes `132 passed`; `compileall` and scoped `git diff --check` pass.

### Version 32.16: task-bound high-citation triage and controlled replenishment

- Citation thresholds now establish high-citation eligibility rather than automatically assigning `HIGH_CITATION_BACKBONE`. The Controller requires a labelled backbone to meet the high-citation policy and preserves its mandatory full-text rule; an in-scope high-citation candidate may remain at title/abstract level when the task records why it is a non-mainline, mechanism-homogeneous, or application-only record already covered by available evidence.
- The existing Coverage Review `CONTINUE → QUERY_PLANNING` return route is now the controlled correction path. A `CONTINUE` verdict requires concrete nonempty reasons and gaps, and the replacement Query Plan must retain each reviewed gap before the normal retrieval, admission, reading, Evidence Card, Field Map, and independent-review chain may resume. Scientific-core incremental literature continues to reuse that same evidence chain.
- No new Gate, State, Hook, Artifact type, reviewer role, or parallel workflow was introduced. The source-policy template and the main/Codex research-lit contracts now set the pre-2000 threshold to `>300`, 2000–2009 to `>200`, and describe the task-bound selection rule without hard-coded domains or paper lists.
- Regression: new Controller cases cover abstract-only high-citation candidates, a threshold-bound backbone label, and gap-bound `CONTINUE` re-entry. Research-lit gateway, CLI, scientific-core-contract, and Codex-mirror suites pass `76`; the full suite reaches `637 passed, 66 skipped, 4 subtests passed`, with one unrelated Windows `forensics_gate` file-lock flake that passed twice on direct rerun.

### Version 32.17: Impedance Control E2E re-screening baseline submitted

- Reclassified the former 89-paper E2E full-text list into 75 full-text candidates and 14 title/abstract-only records: six early records below the revised year–citation thresholds and eight task-specific application/branch records. The candidates remain explicit in the project batch, while the summary preserves the abstract-level records for later coverage-driven reconsideration.
- Updated the project source-policy candidate with the Harness distinction between active-reading eligibility and the mandatory `HIGH_CITATION_BACKBONE` label. Submitted the validated candidate through `arisctl submit-source-policy`; the run is now `WAITING_FOR_HUMAN` for the existing `source_policy_approval` Gate. No approval, direct state rewrite, or evidence/artifact mutation was performed.

### Version 32.18: evidence-shaped Field Map evolution closure

- The literature-cognition target is now explicit in the existing Field Map
  Contract and both `research-lit` Skill variants: `research problem -> method
  / mechanism -> evidence -> residual bottleneck -> transition -> subsequent
  evolution`. This is a fixed reasoning frame, not a history template. The
  literature determines whether a field has one, many, parallel, merging, or
  no material transitions; neither stage count nor calendar periodization is
  prescribed.
- Existing `family_development_traces` were strengthened rather than replaced.
  Each declared trace now has a unique ID, the full problem/progress/bottleneck/
  question-shift/direction chain, a permitted transition status, and non-empty
  unique Evidence IDs that resolve to accepted Evidence Cards. `family` remains
  optional for cross-family shifts. No `representative_evidence_ids` field was
  added: a transition can be supported by a set of existing Evidence Cards.
- The existing independent Coverage Reviewer now returns four explicit
  evolution judgments: foundation-to-frontier coverage, key nodes and branches,
  transition causality, and overall explanatory coherence. It must identify
  material evolution gaps that change the historical explanation or frontier
  judgment, but must not manufacture gaps from irregular chronology, parallel
  development, or a lack of a single landmark paper.
- To close the zero-trace reliability gap without inventing a new module, the
  existing Controller-bound Coverage Review request carries only
  `development_trace_count`. The existing Coverage Validator checks that the
  Reviewer explicitly distinguishes declared traces, evidence-supported absence
  of a material transition, and an omitted material transition. It does not
  decide the scientific truth of that judgment.
- Any evolution `GAP` is required to produce `CONTINUE`; every material
  evolution gap is forwarded verbatim through existing top-level `gaps`, so the
  established `CONTINUE -> QUERY_PLANNING` path retains it in the next targeted
  Query Plan. The candidate-sufficient path, State machine, Evidence/Card
  pipeline, full-text workflow, and all existing Gates remain unchanged.
- Regression covers incomplete classification-only traces, zero-trace review,
  parallel and cross-family traces, no fixed year/stage fields, duplicate or
  invalid trace structures, explanatory-coherence gaps, gap-forwarding, and
  targeted re-entry for a missing material historical transition. Controller
  tests pass `97`; scientific-contract tests pass `30`; the full suite passes
  `647 passed, 66 skipped, 4 subtests passed`.

# Innovation-method Harness revision — 2026-08-14

Scope: minimal sufficient repair of the existing scientific-core workflow. No
research stage, Gate, reviewer role, or parallel state machine was added.

## Root causes and repairs

1. **Root-cause evidence deepening** — `root_cause_analysis` was absent from
   the existing gateway allowlist, and the validator recognised only Capsule
   evidence and diagnostic pilots. Added it to the existing incremental gateway
   policy and made Controller-registered Evidence Cards valid only as
   phase-scoped diagnostic evidence. The accepted Problem Contract/Evidence
   Capsule remains immutable; only evidence that invalidates that accepted
   handoff warrants `REOPEN_PROBLEM`.

2. **Root-Cause Gate consistency** — the Type-A verdict validator allowed
   `DIAGNOSIS_READY` with a non-PASS scientific rubric. It now requires all
   seven rubrics to be `PASS` and no `BLOCKING` issue. This means sufficient to
   enter method design, not finally proven.

3. **Causal chain to capability handoff** — `METHOD_ROUTES.jsonl` previously
   checked only IDs. Each obligation now requires causal-chain IDs, required
   capability, why current methods fail, measurable acceptance condition, and
   `MUST|SHOULD` priority.

4. **Minimal dominant solution and necessary support** — routes now require a
   minimal dominant solution/origin, dominant-only closure, residual MUST gaps,
   and supporting mechanisms only when they cover those gaps. Each supporting
   mechanism carries mechanism match, activation condition, integration
   interface, and removal-failure prediction. First-principles dominant designs
   are valid; transfer/combination is not a default.

5. **Final proposal route semantics** — final proposals now preserve the exact
   selected causal-chain set and every MUST obligation. Every SHOULD is
   explicitly retained, waived, or superseded (with reason); it cannot vanish.

6. **3a–4b validation closure** — `VALIDATED` now requires, for every selected
   causal chain and MUST obligation, predicted mechanism change, observed change,
   discriminating evidence tied to registered validation artifacts, and a
   performance consequence. Allowed identifiable evidence includes controlled
   intervention, ablation, counterfactual, mechanism measurement, theory, and
   necessary joint-mechanism experiments; performance-only results are rejected.

7. **Independent reviewer ownership and bypass boundary** — the root-cause
   reviewer now emits the complete canonical verdict payload. The Hook verifies
   identity/request/hash and preserves that payload externally; Controller
   validates and atomically materializes it. Main cannot synthesize or amend
   verdict content. The existing pre-tool Hook now protects the remaining
   canonical scientific contracts and detects common direct network-library
   paths in addition to shell fetch commands.

## Files and minimality

- Runtime: `arisctl/validators.py`, `arisctl/controller.py`,
  `arisctl/reviews.py`, `tools/run_state.py`.
- Boundary: `.codex/hooks/subagent_attestation.py`,
  `.codex/hooks/pre_tool_use_policy.py`, and the existing independent root-cause
  reviewer instruction.
- Contracts/templates: the existing workflow, root-cause and method-design
  contracts, both Codex mirrors, proposal template, and the two method Skills.
- Tests: adjusted affected fixtures and added seven-rubric/route-closure
  coverage. No unrelated refactor or workflow expansion was performed.

## Verification

- `py_compile` for changed runtime and Hook modules: passed.
- Targeted Controller tests: `14 passed, 84 deselected`.
- Root-cause/refinement state tests: `2 passed, 23 deselected`.
- Scientific-contract and Codex-mirror tests: `51 passed`.
- `git diff --check`: no whitespace errors (the repository already contains
  unrelated dirty/untracked work; it was preserved).

## Remaining real issues

None found within the seven confirmed issues. Full-suite execution was not run:
the requested verification was limited to directly affected contracts and
runtime paths.

# Innovation-method Harness follow-up revision — 2026-08-14

Scope: independently re-checked the three newly reported gaps. All three were
real. This revision changes only their existing Controller, Hook, producer
contract, and test boundaries; it adds no research stage, Gate, reviewer, or
parallel state machine.

## Real root causes and minimal repairs

1. **Running root-cause evidence deepening / Gate binding** — the existing
   gateway condition admitted an incremental literature session only while its
   phase was `pending`; `root_cause_analysis` could not reopen it after 1a–2b
   exposed a focused evidence gap. Root-Cause Gate also bound only the Gate
   phase's incrementals, omitting the analysis phase's diagnostic Evidence Card
   hashes. `arisctl/controller.py` now permits only `root_cause_analysis` to
   re-enter the existing gateway while `running`, exposes that action, preserves
   all successive phase-scoped cards rather than overwriting them, and binds
   their hashes into the Root-Cause Gate request. The Problem Contract and
   Evidence Capsule remain untouched.

2. **3a–4b explanation closure / producer drift** — Controller previously
   required nonempty closure prose, so a declared lack of mechanism change plus
   a performance gain could still become `VALIDATED`; both result-to-claim
   Skills still emitted the obsolete validation result shape. Controller now
   requires every selected causal-chain/MUST closure to declare
   `EXPLANATION_SUPPORTED` and `MATCHES_PREDICTION` before `VALIDATED`; the two
   producer contracts emit those fields and route performance-only or
   contradicted results back through existing decisions. This preserves allowed
   discriminating designs (controlled intervention, ablation, counterfactual,
   mechanism measurement, theory, or necessary joint-mechanism experiment),
   without requiring one ablation per module.

3. **Non-gateway network bypass** — the pre-tool Hook matched direct
   `requests.get` but not `requests.Session().get`, `http.client`, or
   `socket.create_connection`; the main idea-discovery orchestrator also
   advertised `WebSearch`/`WebFetch`. The existing Hook now rejects those
   concrete library paths, and the unnecessary Web tools were removed from the
   orchestrator. It remains an invariant boundary rather than a duplicate
   Controller state machine.

## Files and verification

- Runtime/boundary: `arisctl/controller.py`,
  `.codex/hooks/pre_tool_use_policy.py`.
- Contracts: `skills/shared-references/idea-workflow.yaml`,
  `skills/shared-references/root-cause-analysis-contract.md`, their Codex
  mirrors, `skills/idea-discovery/SKILL.md`, and both
  `result-to-claim/SKILL.md` variants.
- Tests: `tests/test_aris_controller.py` and
  `tests/test_scientific_core_contract.py` now cover running-only RCA re-entry,
  accumulated evidence and Root-Cause Gate hash binding, performance-only
  rejection, producer fields, and the three network bypass forms.
- `py_compile` changed runtime/Hook modules: passed.
- Direct Controller regression: `10 passed, 90 deselected`.
- Direct scientific-contract and Codex-mirror regression: `51 passed`.
- `git diff --check`: no whitespace errors; only pre-existing unrelated CRLF
  warnings were reported. Existing dirty/untracked work was preserved.

## Remaining real issues

None found in the three reported gaps after repair. The implementation cannot
independently establish scientific truth from free-text observations; it now
requires the explicit, artifact-bound causal verdict that the existing
independent review and validation workflow are responsible for assessing.

# Innovation-method Harness validation-ownership revision — 2026-08-14

Scope: independently checked the two newly reported gaps. Both were real. This
revision formalizes the already-existing result-to-claim judgment and replaces
the network denylist with one Controller route; it adds no scientific stage,
Gate, rollback path, or parallel state machine.

## Real root causes and minimal repairs

1. **`VALIDATED` was Main-declarable.** Controller verified nonempty mechanism
   closure fields but accepted them directly from Main; the existing Codex
   result-to-claim judgment was advisory text, not a bound verdict. A
   Controller-issued validation handoff now includes one hash-bound
   `FORMAL_VALIDATION_JUDGMENT` request. The existing judgment is formalized as
   `result_to_claim_reviewer`: its complete payload is Hook-attested outside
   the workspace, including reviewer/request/source-handoff hashes and every
   result artifact hash. Controller verifies the payload hash and accepts only
   an exact copy, then atomically records its provenance. Main cannot change an
   observation, status, decision, or closure after review. `VALIDATED` still
   requires the existing `EXPLANATION_SUPPORTED` and `MATCHES_PREDICTION`
   closure checks; free-text scientific truth remains the fresh reviewer's
   responsibility, not a string heuristic.

2. **Network Hook was an extensible denylist.** Alias imports, `git`, `ssh`,
   and arbitrary runtime code had no named pattern and passed. The Hook now
   permits Bash only for a single `python -m arisctl ...` Controller command;
   its registered query/enrichment/full-text gateway is the sole shell network
   route. All other shell executables are denied without enumerating libraries.
   WebSearch and WebFetch are also denied at PreToolUse, so Skill declarations
   cannot form a parallel literature route. This Hook only enforces the
   transport invariant; Controller remains the owner of scientific state.

## Files and verification

- Runtime/provenance: `arisctl/controller.py`,
  `.codex/hooks/subagent_attestation.py`, `.codex/hooks.json`,
  `.codex/config.toml`, and the reviewer configuration for the existing
  result-to-claim judgment.
- Producer contracts: both `result-to-claim/SKILL.md` variants now require the
  fresh reviewer to emit the exact canonical verdict rather than Main parsing
  and rewriting it.
- Tests: direct mutation of an attested observed mechanism is rejected; stale
  or missing reviewer verdicts are rejected; alias-import, socket, git, ssh,
  WebSearch, and WebFetch bypasses are denied while `arisctl query` remains
  allowed.
- `py_compile` changed runtime/Hook modules: passed.
- Direct Controller regression: `10 passed, 92 deselected`.
- Direct scientific-contract and Codex-mirror regression: `51 passed`.
- `git diff --check`: no whitespace errors; only pre-existing unrelated CRLF
  warnings were reported. Existing dirty/untracked work was preserved.

## Remaining real issues

None found in these two reported gaps after repair. End-to-end judgment quality
still depends on the fresh reviewer examining the bound evidence; the Harness
now makes that ownership and provenance mechanically mandatory.

# Innovation-method Harness final validation-path audit — 2026-08-14

Scope: re-audited the recent validation-ownership and network-boundary repair.
One real execution-path gap was found and repaired; no further confirmed gap
was found in the inspected scope.

## Real root cause and minimal repair

**Validation reviewer dispatch was absent.** After `validation_handoff` created
the now-mandatory `FORMAL_VALIDATION_JUDGMENT` request, `allowed_agents()`
still returned no agent for the validation entry. The result-to-claim reviewer
therefore had a valid Hook/Controller contract but no Controller-authorized
dispatch path. `arisctl/controller.py` now returns only the already-declared
`result_to_claim_reviewer` while that request is live. It returns no reviewer
before user initiation or after completion. No stage, Gate, role category, or
state machine was added. The result-to-claim producer contracts now name this
Controller-authorized dispatch explicitly.

The network allowlist was also checked with the normal `--root` Controller CLI
form: it remains permitted, while direct Python, aliases, socket variants,
`git`, `ssh`, WebSearch, and WebFetch remain denied.

## Verification

- `py_compile` changed Controller and Hook modules: passed.
- Validation ownership, Hook, and subagent-configuration regressions:
  `10 passed, 92 deselected`.
- Scientific-contract and Codex-mirror regressions: `51 passed`.
- Full Controller suite was launched to check the wider state-machine surface;
  it completed without a reported failure or a new pytest `lastfailed` entry.
- `git diff --check`: no whitespace errors; only pre-existing unrelated CRLF
  warnings were reported. Existing dirty/untracked work was preserved.

## Remaining real issues

None found in this re-audit scope. The Harness now enforces ownership and
transport of the validation judgment; the fresh reviewer remains responsible
for the substantive evidence assessment.

# Method-design residual-gap literature re-entry — 2026-08-15

## Confirmed root cause

`method_design` was named in the incremental-literature allowlist but the
Controller permitted a running-phase re-entry only for `root_cause_analysis`.
The method Skill also instructed a before-phase-start search, and the workflow
did not declare `ACTIVE_FIELD_MAP.md` as a method-design input. Thus the
existing Field Map was not a formal method-design handoff and a concrete
capability/residual gap could not naturally trigger the existing gateway.

## Minimal repair

- Added the Controller-accepted Active Field Map to `method_design` required
  inputs, so its hash is included in the existing output upstream snapshot.
- Kept Field Map/Evidence Registry reuse first: root cause -> obligations ->
  minimal dominant solution -> dominant-only closure precedes retrieval.
- Allowed only running `method_design` (beside the existing running diagnosis)
  to re-enter the same gateway. Pending method design no longer has a proactive
  method-search path.
- Required the existing query-plan payload, only for that running method phase,
  to declare root-cause ID, Field Map hash, obligations, dominant-only closure,
  and per-query decision target/residual MUST IDs. The Validator rejects an
  empty residual closure and generic query items. No new stage, gate, provider,
  corpus, ledger, evidence type, or reading route was added.
- The established admission, full-text receipt, paper-reader Evidence Card,
  Registry, and phase-scoped Evidence Card hash binding remain unchanged. The
  Controller stamps each new method-design Card with its accepted query-plan
  hash and residual-gap context for direct Registry-level traceability.

## Verification

- Targeted Controller re-entry/Field-Map/no-gap tests: `3 passed`.
- `tests/test_run_state.py`: `25 passed`.
- Gateway, scientific-contract, and Codex-mirror regressions: `76 passed`.
- `py_compile` for changed Controller/Validator and `git diff --check`: passed
  (only pre-existing unrelated CRLF warnings).

# Method-design doctrine alignment — 2026-08-15

## Confirmed conflict

The live method-design Contract already required a minimal dominant solution and
a residual `MUST` gap before support search, but the refinement Protocol still
described combination as the default/preferred strategy. Several active
pipeline, novelty, review, Codex-mirror, and Claude/Gemini overlay Skills
repeated that doctrine. The Contract also described cross-field search as the
next route step after same-field search without requiring a recorded
same-field insufficiency. Its scientific-core test protected the old Protocol
wording by asserting that `combination is the default preferred` existed.

## Minimal alignment

- Standardized the live decision order to root cause -> Design Obligations ->
  minimal sufficient dominant solution -> dominant-only closure -> residual
  `MUST` gap -> accepted Field Map/same-field mechanisms -> cross-field
  structural search only when those options cannot reasonably close that gap.
- Reframed transfer/combination as permitted, residual-gap-specific supporting
  mechanisms; they are neither a default route nor an innovation target.
- Updated the main Skills, Codex mirrors, and review overlays that had retained
  the contradictory default/preferred wording. Cross-field review now checks
  for Field-Map/same-field assessment and a declared gap.
- Updated the direct scientific-core tests to verify ordered, conditional
  search behavior and to reject the obsolete default-combination doctrine.
- Did not add a ban on combination, a new Gate, a new search route, or new
  Controller/Validator behavior. Existing Controller enforcement already
  requires a residual gap for method-design incremental literature.

## Verification

- `python -m pytest tests/test_scientific_core_contract.py -q`: `31 passed`.
- Targeted method-design gateway tests: `2 passed, 115 deselected`.

# Method-refinement formal independent Gate closure — 2026-08-15

## Confirmed root cause

The live method-refinement path had three distinct layers but only one formal
verdict: R2-R4 were internal iterative feedback, R5 prescribed a fresh blind
audit, and the Controller then required `independent_method_reviewer` to attest
another fresh review of the same `FINAL_PROPOSAL.md`. The latter two were the
same phase-ending scientific responsibility. Meanwhile the canonical workflow
and `tools/run_state.py` admitted only `METHOD_READY`, even though the generic
Controller already supported declared `return_targets`. A correct formal
non-ready assessment therefore had no consumable Controller outcome.

## Minimal repair

- Kept R2-R4 as iterative issue-resolution only, and made R5 the sole
  Controller-issued fresh independent Gate. Main/Codex runtime Skills and
  Claude/Gemini overlays no longer instruct a second final blind review.
- Reused existing Contract terminology and the existing Gate token:
  `METHOD_READY` advances; `REVISE` and `HOLD` deterministically return to
  `method_refinement`; `RETHINK` deterministically returns to `method_design`.
  The existing route Human Gate then selects any redesigned route.
- Added those three fixed workflow `return_targets`; the existing request,
  attestation, one-time consumption, archive/invalidation, return history, and
  phase ordering do all execution work. The workflow loader now permits a
  self-return for the legitimate in-phase `REVISE/HOLD` loop while still
  rejecting downstream targets.
- Bound the Markdown method-refinement verdict parser to the workflow-declared
  accepted plus return verdicts, preventing a Contract/workflow enum drift.
  The reviewer is explicitly limited to method-level judgment; it cannot use a
  method verdict to reopen problem or root-cause phases.
- No new Reviewer, Gate, state, artifact type, or parallel transition path was
  created; the duplicated final audit duty was removed.

## Verification

- Scientific-contract, Codex-mirror, and run-state regressions: `77 passed`.
- Controller end-to-end flow: `1 passed`; it exercises
  `REVISE/HOLD -> method_refinement`, `RETHINK -> method_design -> route
  selection`, and a later `METHOD_READY` advance.
- `python -m compileall -q arisctl tools` passed.
- `git diff --check` passed with only pre-existing unrelated CRLF warnings.

# Canonical diagnosis-derived Design Obligations — 2026-08-15

## Confirmed root cause

`METHOD_ROUTES.jsonl` previously repeated the complete
`design_obligations` object in every route. `validate_method_routes` verified
each route's local IDs, chains and priority fields, but did not enforce that
two routes described the same requirements. A route could therefore tailor a
capability, acceptance condition, or `MUST`/`SHOULD` priority to its preferred
method without a detectable upstream change.

## Minimal repair

- Retained `METHOD_ROUTES.jsonl` as the sole method-design handoff. Its first
  v2 record is now the one diagnosis-bound `design_obligation_set`; routes only
  reference that set ID and supply their own coverage/residual assessment.
- The validator enforces one set before all routes, shared binding and causal
  basis, and rejects routes that carry a replacement obligation definition.
  Selection and final refinement retain the set ID as well.
- Documented that scientific changes to an obligation are an existing formal
  method-design re-derivation, or the existing root-cause return when the
  diagnosis/hypothesis premise changes.
- No extra artifact, phase, Gate, reviewer, duplicated requirement copy, or
  parallel lifecycle was added; Controller already invokes this validator for
  method-design, selection, and refinement handoffs.

## Verification

- Direct route/controller/contract/mirror/run-state regression: `7 passed,
  191 deselected`.
- Covers shared-set acceptance with different per-route coverage/residual
  judgments and rejection of capability, acceptance-condition, and priority
  rewrites.
- `compileall` and `git diff --check` passed (only existing unrelated CRLF
  warnings from the latter).

# Formal native-subagent project-root preflight — 2026-08-16

## Confirmed root cause

Native Codex children inherit the parent task cwd. The formal impedance-control
project has the managed attestation Hook only in its own `.codex`, while the
reproducing task was rooted at the containing workspace. The child therefore
completed without project-local Stop/SubagentStop delivery, and the existing
Controller correctly failed closed only at formal submission.

## Minimal repair

- Reused the project installer manifest and existing `.codex` configuration;
  no Hook was copied upward and no runtime layer was introduced.
- Added a non-transitioning Controller preflight for the two native formal
  roles. It requires the dispatching task cwd to equal the formal project root,
  verifies the entire managed layer is current, and verifies the configured
  role plus both natural attestation Hooks.
- Exposed the check through `preflight-native-subagent` and made the project
  dispatch instructions/rule require it before a native child is created.
  Wrong roots fail before child scientific work; receipt, binding, consumption,
  and Evidence/Review semantics are unchanged.

## Verification

- Targeted setup, Controller, reader/reviewer attestation, formal submit, and
  isolated Hook-import regression: `7 passed, 122 deselected`.
- Project-root CLI preflight PASS on `impedance-control-e2e`; the same command
  from the containing workspace failed explicitly with the runtime/formal-root
  mismatch.
- `compileall` passed. A full live positive native-child E2E was not claimed:
  this desktop session cannot create a task rooted at the unregistered E2E
  directory, and no lifecycle event, receipt, or formal result was fabricated.

# Step 1 — Review-led 领域认知闭环 — 2026-08-20

## 真实根因

初始 landscape 路径将 screening/admission/priority metadata 直接当作全文
cohort：`finish_retrieval()` 可将所有 admitted paper 送入 `PAPER_READING`，
而 reading、Evidence、human-fulltext 和 `finish_reading()` 又按全局 admitted
集合处理。因此无法先完成当前 initial corpus 的全量筛选、用 Review 建立
provisional cognition，再由该 Map 正式选择 Primary；`ACTIVE_FIELD_MAP.md` 的
首次提交也被强制要求 coverage verdict。

## 最小修改

- 新增一个现有 Controller state 内的 pass-local `active_reading_session`，不是
  新 Stage、Gate、Manager 或 Registry。初始检索完成后，Main 必须显式绑定
  非空 subset，才可进入 `PAPER_READING`；admission/priority/`fulltext_selected`
  不再自动授权读取。
- `select_reading_subset()` 仅验证当前 screened corpus membership、identity、
  source policy、scope/duplicate 和 lifecycle。首次 subset 可为 Agent 选择的
  Review，或无可用 Review 时的最小 Primary fallback；在同一 initial pass 中
  可以追加 fallback。Controller 不判断 Review、foundation、representative 或
  sufficiency 的科学含义。
- full-text gateway、registered user full-text、human batch、defer、Evidence
  submission 和 `finish_reading()` 均使用 live subset。pass 完成即清除该
  authorization；已被再次选择且已有 canonical Evidence 的 paper 被视为完成，
  不会 reread 或生成第二份 Evidence。
- `TITLE_ONLY_ABSTRACT_UNAVAILABLE` 在 identity 已验证且正常 enrichment 已
  完成、仍无 actual abstract 时可完成 screening，不要求 `fulltext_selected`；
  snippet 仍不能充当 abstract 或 scientific Evidence。
- 首个 `submit_field_map()` 在同一 `ACTIVE_FIELD_MAP.md` canonical path 上接受
  provisional Initial Map：无 `coverage_record`、无 coverage review、无 ordinary
  gap query。随后 `select_formal_primary_subset()` 将 Initial Map hash、初始
  screened corpus IDs、selected IDs 与 Agent rationale 绑定，进入正常
  `PAPER_READING`。其后 Map submission 恢复既有严格 coverage semantics。
- landscape Evidence IDs 单独保留；Field synthesis 仅接受本 landscape
  lifecycle 的 canonical Evidence，不能混入 scientific-core incremental
  Evidence。
- 每次覆盖 `ACTIVE_FIELD_MAP.md` 前，将前一 Controller-accepted exact bytes
  归档到既有 `.aris/archive/<run>/field-map/<sha>.md`；`field_map_history` 只
  保存该 mutable artifact 的 SHA/path 归档指针，确保正式 provenance 引用的旧
  Map 可恢复，不引入通用 revision registry。
- 更新 CLI、workflow allowed actions/agents，以及 main/Codex mirror 的
  source-admission 和 research-lit contract，明确 Review-led 初始认知与
  post-Initial Primary selection。

## 验证

- `python -m pytest tests/test_aris_controller.py -q -k "review_led_initial_map or initial_review_fallback or active_selection_cannot"`：`3 passed`。
  覆盖全量 screening → Review subset → provisional Map → formal Primary → revised
  Map、Review 后 fallback、无 Review 直接 fallback、Evidence reuse、排除项不能
  被 active selection 洗白、以及旧 Map exact bytes 归档。
- `python -m pytest tests/test_scientific_core_contract.py tests/test_aris_cli_output.py tests/test_codex_skill_mirror.py -q`：`53 passed`。
- `python -m pytest tests/test_aris_controller.py -q -k "configured_paper_reader_attestation_path_is_unchanged or coverage_request_authorization_rejects_wrong_root_without_state_side_effects or coverage_replenishment or current_field_map"`：`2 passed`。
- `python -m py_compile arisctl/controller.py arisctl/validators.py arisctl/__main__.py`：PASS。
- 完整 Controller suite 的嵌套临时项目分支仍有既有 test fixture cwd 与 formal
  project-root invariant 不一致的问题；失败发生在 native reviewer dispatch
  前，与本 Step 的 landscape lifecycle 无关，未通过放宽 runtime-root protection
  规避。

# Step 2 — Problem Lead maturation + shared Query Plan history — 2026-08-20

## 已完成

- 将 Problem Lead 明确为 `problem_generation` 内部 cognition：fan-out 只做
  discovery/triage；被 reject 的 Lead 不 materialize Candidate，不进入现有
  Candidate Validator、Quality/Novelty Gate 或 Human Acceptance；mature 才使用
  原有 Candidate 链路。
- `problem_generation pending` 不再出现 `submit_query_plan`，只能先进入
  `running`；running 时允许以现有 incremental literature gateway 深入 promising
  Lead，并允许同一 derivation 的 narrow/reframe 后 replacement query plan。
- Lead query 的 mechanical contract 已加入 validator：非空 `lead_id`、
  `lead_statement`、`purpose`、`expected_close_condition`，当前 accepted Field Map
  hash binding，以及唯一六维 primary `decision_dimension`。未加入任何科研评分或
  Controller-owned Lead identity/hash/version。
- 自动 query event、`HUMAN_SEARCH_REQUIRED` request/result 与由 query 来源形成的
  Evidence Card 记录 immutable context snapshot；Evidence 保留 query-plan hash、
  Lead、Map 和 decision/purpose/close-condition provenance。
- 在共享 canonical Query Plan overwrite boundary 添加按 SHA exact-byte archive；
  仅在旧 Plan 已被 formal query event 引用时归档，并用现有 run archive 下的
  `query_plan_history` 指针解析。逻辑不按 phase 新建 archive system，且没有使
  same-derivation incremental Evidence stale。

## 验证

- Lead normal path：Field Map → running Problem Lead → automatic query → Evidence
  → reject/no Candidate → narrow/reframe/replacement plan → Human Search result，
  验证 immutable snapshots、六维 enum、Field Map binding、旧 plan exact bytes 与
  Evidence 非 stale：`2 passed`。
- Contract、CLI、Codex mirrors：`53 passed`。
- `py_compile`：PASS。
- 完整 Controller suite 的已知 nested-temp-project runtime-root fixture failure
  保持；未修改既有 formal native reviewer protection。

# Step 1 — Field Map / Evidence lifecycle 语义校正 — 2026-08-20

## 校正

- 保留 `initial_field_map_binding`、`formal_primary_selection` 与既有
  `map_lifecycle` 表达。`ACTIVE_FIELD_MAP.md` 始终是唯一的 Field Map；
  `INITIAL_PROVISIONAL` 仅标记当前用于 initial cognition，不是新的 Map 类型、
  文件或独立 lifecycle。未增加 `INITIAL_FIELD_MAP`、`REVISED_FIELD_MAP` 或
  平行 Map lifecycle。
- 每次 `ACTIVE_FIELD_MAP.md` 更新前自动归档旧 accepted bytes 的既有实现保持
  不变：继续写入 `.aris/archive` 和 `field_map_history`，不改为按引用条件保存。
- 未新增 fallback 专用 Evidence reuse 机制。formal Primary selection 中如 selected
  paper 已有合法 canonical Evidence，由既有统一 Evidence lifecycle 满足阅读要求，
  不 reread 或重复创建 Evidence；formal selection 本身仍须执行。

## 验证

- main 与 Codex mirror 的 `research-lit` contract 已同步；
  `python -m pytest tests/test_scientific_core_contract.py tests/test_aris_cli_output.py tests/test_codex_skill_mirror.py -q --disable-warnings --maxfail=1`：`53 passed`。

# Step 3 — Incremental Evidence currentness / re-adoption / search budget — 2026-08-20

## 已完成

- 在既有 `research_lit.incremental_evidence_by_phase` 的 phase binding 上保存
  `phase_binding_anchor`；不改写 Evidence Card、Evidence Registry、query/read
  provenance，也不建立第二套 derivation、Evidence 或 binding Registry。
- anchor 只包含该 phase 真实的 formal upstream：`required_inputs` 的 registered
  identity/hash、Problem 的现有 accepted/pending revision binding、return lifecycle
  provenance、accepted RCA binding，以及当前 method obligation/selection context。
  初始 `problem_generation` 只绑定 Field Map 等 existing inputs，不要求 active
  Problem version；`REOPEN_PROBLEM` 额外绑定现有 pending revision 与 return receipt。
- current view 在 `_incremental_evidence_bindings()` 中比较 stored anchor 与当前
  phase anchor。Query Plan 的同一 derivation 内 replacement 不属于 anchor；正式
  rollback/replace/supersede 后的 relevant lifecycle 或 upstream binding 改变才会
  令历史 phase binding 停止 current。RCA 在同一 accepted Problem 下的普通
  `REVISE_DIAGNOSIS` 不会清空仍相关的 diagnostic Evidence。
- 对旧 run 中尚无 anchor 的既有 binding，在下一次已有 Controller return/rollback
  前按当时正式上下游补齐 anchor；保留原 Evidence 与历史 binding，避免 byte-identical
  re-derivation 错误复活 downstream currentness。
- 新增受限 `readopt-evidence` CLI/Controller action：仅支持 current method context
  的 A→B re-adoption，以及 formal reopened RCA 中的 Method Evidence re-adoption。
  Controller 仅验证 current-run Card/hash/Registry/query/read provenance、target
  context、accepted RCA、obligation IDs/return binding；Agent 仍判断科学适用性。
  新 binding 追加到同一 phase collection，旧 binding 与原 provenance 均保留；已在
  current RCA context 可见的 Evidence 不重复 binding。
- 复用 existing `extend-literature-budget` authorization，增加
  `--max-search-cycles`。仅在合法、idle 的 scientific-core incremental retrieval
  boundary 且已达 global cycle limit 时单调扩展；保留 before/after/reason audit，
  不在 active retrieval/session 中修改计划，也不扩大 phase literature-entry 权限。
- 更新 main/Codex mirror workflow contract 的 incremental Evidence binding 表述。

## 验证

- `python -m pytest tests/test_aris_controller.py -k "incremental_problem_binding_uses_field_map_then_existing_reopen_provenance or re_adoption_preserves_history_and_search_cycle_authorization_is_boundary_only or root_cause_running_may_reenter_literature_gateway_and_keeps_prior_evidence or running_problem_lead_queries_preserve_context_and_query_plan_history or literature_budget_extension_is_monotonic_and_logged" -q`：`5 passed`。
  覆盖 initial/REOPEN Problem anchor、same-derivation Query Plan replacement、A→B
  historical/current binding coexist、Method→reopened RCA、same-Problem RCA diagnostic
  Evidence 保留、byte-identical rollback 不复活，以及 boundary-only cycle extension。
- `python -m pytest tests/test_aris_cli_output.py tests/test_scientific_core_contract.py tests/test_codex_skill_mirror.py -q`：`54 passed`。
- `python -m py_compile arisctl/controller.py arisctl/__main__.py`：PASS。
- 完整 Controller suite 的 `-x` 运行在既有 nested temporary project fixture 停止：
  fixture 的 runtime cwd 为父目录、formal project 为子目录，触发现有 native
  runtime-root invariant；未修改该保护机制规避此既有非本 Step 路径问题。
