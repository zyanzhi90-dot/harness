# Hook lifecycle and project-layer E2E fixes

## Live failures

1. The project `PreToolUse` policy treated any command containing a protected
   path as a write whenever the same command contained a generic write verb.
   Literal read-only PDF/hash/state inspection was blocked, while constructing
   the protected path from string fragments bypassed the match.
2. A configured `paper_reader` completed and returned a valid Evidence Card,
   but no receipt was emitted. Codex 0.147 records a normally completed child
   thread as `open`; normal turn completion emits `Stop`, while
   `SubagentStop` is reserved for explicit child closure.
3. The live project's installed `.codex` layer predated merged Harness changes.
   It omitted `result_to_claim_reviewer` and newer reviewer-payload and
   protected-contract checks. `project_setup.MANAGED_FILES` also declared the
   reviewer in config without installing its TOML file.

## Minimal changes

- Protected-path denial now applies only to mutating tools or explicit shell
  write intent; literal read-only inspection remains available.
- The existing attestation hook is reused for both `Stop` and
  `SubagentStop`. For `Stop`, it verifies the configured role and agent ID from
  the runtime transcript's `session_meta`. Duplicate lifecycle events are
  idempotent and cannot recreate a consumed receipt; a new live response for
  the same request can still replace a failed, unconsumed response.
- `result_to_claim_reviewer.toml` was added to the existing project installer,
  and the live project was resynchronized through
  `install_project_codex_layer`; its manifest now covers 13 matching files.

## Verification

- Live read-only PDF/hash extraction after the policy fix: passed.
- Live configured reader completion: produced a schema-complete card; the old
  `SubagentStop`-only configuration correctly failed closed and wrote neither
  receipt nor candidate.
- Natural-`Stop` transcript-role, idempotency, Unicode, policy-boundary, and
  reviewer retry tests: passed.
- Controller and CLI regression: `108 passed`.
- Project-layer setup regression: `2 passed`.
- Live post-fix `Stop` receipt generation remains pending because the Codex CLI
  account reached its weekly rate limit immediately after the diagnostic full-
  text run; no receipt or formal Evidence Card was synthesized to hide that
  boundary.

## Native generic reader/reviewer compatibility

- Kept the configured `paper_reader` / `coverage_reviewer` lifecycle path
  unchanged. The existing hook now additionally recognizes only a real native
  generic child transcript that carries one Controller-bound compatibility task
  binding and the exact hash/text of the configured role contract.
- Compatibility applies only to `paper_reader` and `coverage_reviewer`, records
  `dispatch_mode = native_generic_compat` plus real runtime/child identities,
  transcript hash, task binding, and observed tools. It never claims that a
  configured profile was loaded.
- Reader compatibility fails closed on any tool call. Coverage compatibility
  permits only its declared WebSearch capability and fails closed on every other
  recorded tool or incomplete/mismatched run/request/artifact binding. Existing
  payload hashing, retry idempotency, external review receipt storage, and
  one-time Controller consumption are reused without modification.
- Added direct configured-path, native-compatibility, mismatch, tool/capability,
  root/generic-negative, consumption, project setup, and Hook tests. No live
  paper was read and no E2E transition was executed.

## E2E managed-layer synchronization and continuation handoff

- Reused `install_project_codex_layer()` to resynchronize the current
  `impedance-control-e2e` managed `.codex` layer. Its 13 manifest entries now
  match their actual SHA-256 values, including byte-identical source and
  project `subagent_attestation.py` files; no installer logic or project
  `AGENTS.md` was changed.
- Replaced the stale quota-reset/fresh-turn continuation in the existing E2E
  handoff with the current-turn configured-first/native-generic-compatibility
  route. It retains the original `PAPER_READING` bindings, rejects reuse of the
  unattested `HVvmYj1jhCIJ` Card, and preserves the canonical receipt,
  Controller submission, and one-time-consumption sequence.
- No live paper, receipt, formal state, Gate, or E2E transition was created or
  modified during this synchronization.
