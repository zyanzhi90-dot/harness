# Final Method Packet and View Guide

Main does not author `FINAL_PROPOSAL.md`. Main authors
`refine-logs/FINAL_METHOD_PACKET.json`; after mechanical validation, the
Controller deterministically renders the Markdown view. The Packet is the only
Final Method machine authority.

The Packet must contain the exact accepted Problem, Necessity, RCA, and
Controller-materialized Selected Principle bindings, followed by:

1. `target_constraints`
2. `assumption_constraint_collisions` with a disposition for every collision
3. `minimal_faithful_realization`, separating reused implementation machinery
   from core scientific changes
4. exact `principle_only_closure` coverage with `CLOSED | RESIDUAL_GAP`
5. `residual_musts` derived only from `RESIDUAL_GAP`
6. `minimal_necessary_composition` (legally empty when no residual exists)
7. `core_method_changes` and an acyclic `causal_repair_dag`
8. an Existing-to-New `mechanism_delta` and Evidence-bound nearest-prior
   separation
9. Target RMC ↔ Selected/Source Intervention ↔ Final Computational Change
   alignment
10. `target_only_natural_derivation` with the Source story removed
11. claim-proportional `feasibility_closure`, debts, restrictions, and fatality
12. one future `counterfactual_necessity_obligation` per retained support
13. a bounded `final_scientific_delta_claim` whose status is
    `FINAL_PENDING_VALIDATION`
14. claim-validation obligations that require predicted mechanism change,
    observed mechanism change, discriminating evidence, and performance
    consequence
15. failure, applicability, and claim-restriction boundaries

Every support must bind a Residual MUST and every scientific DAG edge must bind
a claim-validation obligation. An unexecuted counterfactual remains
`FUTURE_OBLIGATION` and is not Evidence. `Established Scientific Delta` is
reserved for a later Controller-accepted Full Validation result.

The rendered view is produced only by:

```text
render_final_method_view(FINAL_METHOD_PACKET.json)
  -> Controller writes FINAL_PROPOSAL.md
```

Manual changes to `FINAL_PROPOSAL.md` make the view invalid; never recover or
infer Packet facts from Markdown.
