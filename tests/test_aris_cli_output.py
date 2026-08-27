from __future__ import annotations

import io
import json
import sys

from arisctl.__main__ import _emit_json, build_parser


def test_cli_json_output_is_utf8_when_host_text_encoding_cannot_encode(monkeypatch) -> None:
    raw = io.BytesIO()
    narrow_stdout = io.TextIOWrapper(raw, encoding="gbk")
    monkeypatch.setattr(sys, "stdout", narrow_stdout)

    _emit_json({"title": "Robot–impedance control", "status": "完成"})
    narrow_stdout.flush()

    payload = json.loads(raw.getvalue().decode("utf-8"))
    assert payload == {"title": "Robot–impedance control", "status": "完成"}


def test_problem_human_return_cli_carries_the_bound_feedback() -> None:
    args = build_parser().parse_args(
        [
            "human-approve",
            "run-1",
            "problem_acceptance",
            "--decision",
            "reject",
            "--selected-id",
            "P-1",
            "--human-feedback",
            "The premise is not established.",
        ]
    )
    assert args.decision == "reject"
    assert args.selected_id == "P-1"
    assert args.human_feedback == "The premise is not established."
