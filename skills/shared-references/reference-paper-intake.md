# Reference-paper intake module

This module handles an optional user-named paper before field mapping. It
prevents a reference paper from becoming an unexamined anchor or an accidental
research question. It is an evidence input, not a method-design shortcut.

## Activation and precedence

Activate only when the caller supplies an explicit `REF_PAPER` path, URL, DOI,
or paper identifier. The default is off. A paper supplied by the user is
`USER_SUPPLIED_READ`: inspect it before judging whether it belongs in the
proactively retrieved source set. For a proactively retrieved paper, apply
`source-admission-policy.md` before abstract or full-text reading.

Accept local PDF, publisher or repository URL, DOI, and arXiv identifier. Use
the available reader/search capability and record access or verification
failures; never invent missing bibliographic fields or citations. If only an
abstract is available, label every stronger claim as unverified.

## Compact evidence product

Write a timestamped summary and a fixed handoff copy at
`idea-stage/REF_PAPER_SUMMARY.md`. Keep the handoff under 4,000 characters and
include:

- title, authors, venue/year, identifier, and access status;
- the paper's question, setting, method, evidence, and claimed contribution;
- assumptions, limitations, boundary conditions, and unresolved questions;
- evidence anchors (page/section/figure or stable source IDs);
- possible improvement directions, explicitly marked as hypotheses;
- code/data availability when it affects feasibility.

Separate `paper_claim`, `evidence`, `inference`, and `open_question`. A paper's
gap is not automatically a novel problem. The field map must still compare
against independent literature, negative evidence, contradictions, and
concurrent work.

## Workflow integration

Present the compact summary at the scope checkpoint. The user may keep,
exclude, or reframe its influence. The summary may inform `/research-lit` and
the problem evidence packet, but it cannot silently change scope. If the user
asks to “improve this paper”, route the request through `mode: problem` first;
do not generate a method before a problem contract is human-accepted.

Downstream modules receive the summary path and selected evidence IDs, not the
full PDF or a long paper transcript. The module may be rerun with a new paper;
the input hash and supersession relation must be recorded so stale summaries
cannot masquerade as current evidence.

