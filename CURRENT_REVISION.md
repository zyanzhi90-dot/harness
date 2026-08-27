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
