# Query Plan Event Reconciliation Changelog

## 2026-08-14

- Added the Controller-owned `reconcile-query-plan-events` recovery action for a
  migrated or resubmitted accepted Query Plan whose item statuses were reset to
  `planned` even though matching gateway query events were already terminal.
- Reconciliation requires the same `plan_item_id`, query text, and executable
  year/page/exact-title constraints, and exactly one terminal event. It restores
  only the plan-item status and `query_id`; it does not execute a search, consume
  query budget, or change the paper corpus.
- The action is exposed by `allowed-actions` only while at least one exact
  reconciliation is available and records its result in the formal search ledger.
- Added a regression test covering state restoration, unchanged query/event/paper
  counts, conditional action exposure, and ledger auditability.
