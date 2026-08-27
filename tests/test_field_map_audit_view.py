from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _skill(root: Path) -> str:
    return (root / "idea-discovery" / "SKILL.md").read_text(encoding="utf-8")


def test_field_map_audit_view_is_a_nonblocking_human_only_sidecar() -> None:
    required = (
        "ACTIVE_FIELD_MAP_AUDIT.md",
        "derived Human Audit View",
        "WAITING_FOR_HUMAN",
        "scope_human_approval",
        "EVIDENCE_REGISTRY.jsonl",
        "LITERATURE_CORPUS.jsonl",
        "structured Evidence first",
        "what the Evidence actually supports",
        "minimal sufficient",
        "retain the Map's `evidence_ids` / `source_ids`",
        "independently explanatory sources",
        "foundational, pivotal-transition, branch, current-representative, or key",
        "boundary/failure role",
        "substantively\nredundant in mechanism, evolutionary role, and explanatory value",
        "Development Trace",
        "cover every key evolution node",
        "only recent representative work",
        "material origin or transition",
        "cannot determine a link",
        "Do not conduct new research",
        "create Evidence/read events/attestations",
        "Never register this view in a manifest",
        "accepted artifacts",
        "landscape handoff",
        "Gate binding",
        "required input",
        "downstream context",
        "no Controller/Validator, provenance, recovery",
        "If derivation fails",
        "continue the unchanged scope checkpoint",
        "request_revision",
        "regenerate and overwrite",
        "do not retain an\nolder view",
        "requires no approval",
    )
    texts = [
        _skill(root)
        for root in (REPO_ROOT / "skills", REPO_ROOT / "skills" / "skills-codex")
    ]
    for text in texts:
        for needle in required:
            assert needle in text
        assert "formal review object remains `ACTIVE_FIELD_MAP.md`" in " ".join(text.split())
    selection_start = "Select supporting literature/Evidence as"
    selection_end = "Do not conduct new research"
    selection_rules = [
        text[text.index(selection_start):text.index(selection_end, text.index(selection_start))]
        for text in texts
    ]
    assert selection_rules[0] == selection_rules[1]
