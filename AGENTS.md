# ARIS Harness

- Formal research work starts and advances only through `python -m arisctl`; `tools/run_state.py` is not an alternate transition path for Controller-managed runs.
- Ask the Controller for the current stage, allowed action, and allowed agent. After scope approval the same Controller drives the declared problem and method phases.
- Workers return structured cognition; they never search, read unadmitted papers, edit state/contracts, approve Gates, or publish canonical artifacts.
- Hosted web search and direct network/file bypasses are not formal literature routes.
- After `LANDSCAPE_ACCEPTED`, a declared eligible pending scientific-core phase
  may open a phase-scoped incremental literature session. The existing iterative
  `root_cause_analysis` and `method_design` phases may also re-enter that same
  session while running, subject to the Controller's existing phase conditions.
  It reuses the existing query, admission, paper-reader, ledger, corpus, and
  Evidence Registry actions; it must finish before the affected phase can
  proceed, and its registered Evidence Card hashes are the only new formal
  evidence for that phase.
- Scientific judgment belongs to Main, `paper_reader`, and the independent reviewer; mechanical constraints and all transition decisions belong to code.
- A formal reviewer may answer only a live Controller-issued request and must return its request ID, run ID, reviewer/verdict IDs, fixed decision, and exact reviewed-artifact hashes; the external attestation is consumed once by the Controller.
- Human Gate commands bind the live request, current artifact hashes, any required selection, and an explicit decision before the Controller records or advances the phase.
- `force` is legacy/development-only for unstructured runs and cannot advance a declared workflow or Controller-managed formal run.
- Final method acceptance stops at `METHOD_CONFIRMED_AWAITING_USER_VALIDATION`; validation starts only when the user explicitly initiates it.


For long-running asynchronous work:
- Empty `write_stdin` polls MUST use `yield_time_ms >= 180000`;
  prefer `300000` when intermediate output is not needed.
- `functions.wait` MUST use `yield_time_ms >= 180000`.
- `functions.exec` MUST set its outer `@exec yield_time_ms` at least
  30000 ms longer than the longest nested tool wait, so the outer
  code cell does not yield first.
- Do not apply the long wait to non-empty `write_stdin` calls that
  send interactive input.
- These tools return early when the process or cell completes.
  Do not wake the model merely to report that work is still running.


  ## Git workflow

Repository:
- GitHub repository: git@github.com:zyanzhi90-dot/research-harness.git
- Always push completed changes to this repository.

After completing any code modification:

1. Run relevant tests.
2. Inspect git diff.
3. Commit the completed change.
4. Push the commit to GitHub.

Do not leave completed modifications uncommitted.

Commit message format:

<type>: <summary>

Examples:
- fix: repair evidence provenance binding
- feat: add method rca reopen lifecycle
- test: add regression coverage
