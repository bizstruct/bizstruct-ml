"""Unit tests for experiments/calibration/ — the rubric-calibration
harness (manual evaluation). Runs offline against synthetic data; the
live generation/export/degrade cycle is exercised separately against the
real calibration-set (see experiments/calibration/sets/v1/).
"""

from __future__ import annotations

import copy
import csv
import json
from pathlib import Path

import pytest

from experiments.calibration.degrade import check_structure, import_edited
from experiments.calibration.export import FILE_LETTERS, build_calibration_export
from experiments.calibration.rubric import CRITERION_IDS, render_rubric_md
from experiments.calibration.scoring import ROUNDS, store_scores, validate_scores, write_score_template
from experiments.calibration.tokens import estimate_tokens


def _sample_blocks() -> dict:
    return {
        "empathy_map": {
            "says": [{"id": 1, "text": "a" * 20}, {"id": 2, "text": "b" * 20}, {"id": 3, "text": "c" * 20}],
            "thinks": [{"id": 1, "text": "a" * 20}, {"id": 2, "text": "b" * 20}, {"id": 3, "text": "c" * 20}],
            "does": [{"id": 1, "text": "a" * 20}, {"id": 2, "text": "b" * 20}, {"id": 3, "text": "c" * 20}],
            "feels": [{"id": 1, "text": "a" * 20}, {"id": 2, "text": "b" * 20}, {"id": 3, "text": "c" * 20}],
            "pains": [{"id": 1, "text": "a" * 20}, {"id": 2, "text": "b" * 20}, {"id": 3, "text": "c" * 20}],
            "gains": [{"id": 1, "text": "a" * 20}, {"id": 2, "text": "b" * 20}, {"id": 3, "text": "c" * 20}],
        },
        "architecture": {
            "epicenter": "customer_driven",
            "epicenter_rationale": "x" * 50,
            "pattern": "unbundling",
            "pattern_subtype": None,
            "pattern_rationale": "y" * 50,
        },
    }


class TestRubric:
    def test_render_includes_all_criteria_and_what_doesnt_affect_section(self):
        md = render_rubric_md(CRITERION_IDS[:])
        for cid in CRITERION_IDS:
            assert cid in md
        assert "Що НЕ впливає на оцінку" in md
        assert "обсяг тексту" in md

    def test_render_respects_given_order(self):
        reversed_order = list(reversed(CRITERION_IDS))
        md = render_rubric_md(reversed_order)
        positions = [md.index(cid) for cid in reversed_order]
        assert positions == sorted(positions)


class TestDegradeStructuralCheck:
    def test_text_only_edit_passes(self):
        blocks = _sample_blocks()
        edited = copy.deepcopy(blocks)
        edited["architecture"]["epicenter_rationale"] = "completely different text " * 3
        result = check_structure(blocks, edited)
        assert result.ok

    def test_dropped_list_item_fails(self):
        blocks = _sample_blocks()
        edited = copy.deepcopy(blocks)
        edited["empathy_map"]["says"].pop()
        result = check_structure(blocks, edited)
        assert not result.ok
        assert any("says" in e for e in result.errors)

    def test_missing_block_fails(self):
        blocks = _sample_blocks()
        edited = copy.deepcopy(blocks)
        del edited["architecture"]
        result = check_structure(blocks, edited)
        assert not result.ok
        assert any("missing block" in e for e in result.errors)

    def test_invalid_enum_value_fails_schema_validation(self):
        blocks = _sample_blocks()
        edited = copy.deepcopy(blocks)
        edited["architecture"]["epicenter"] = "not_a_real_value"
        result = check_structure(blocks, edited)
        assert not result.ok
        assert any("schema validation failed" in e for e in result.errors)

    def test_import_edited_writes_nothing_on_failure(self, tmp_path: Path):
        set_dir = tmp_path / "set"
        set_dir.mkdir()
        record = {"idea_id": "idea-001", "run_index": 0, "blocks": _sample_blocks()}
        (set_dir / "runs.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

        bad_edit = {"idea_id": "idea-001", "blocks": {"empathy_map": _sample_blocks()["empathy_map"]}}  # missing architecture
        in_path = tmp_path / "edited.json"
        in_path.write_text(json.dumps(bad_edit), encoding="utf-8")

        result = import_edited(set_dir, "idea-001", in_path, "K1")
        assert not result.ok
        assert not (set_dir / "degraded" / "idea-001.json").exists()
        assert not (set_dir / "degraded" / "manifest.csv").exists()

    def test_import_edited_writes_degraded_and_manifest_on_success(self, tmp_path: Path):
        set_dir = tmp_path / "set"
        set_dir.mkdir()
        blocks = _sample_blocks()
        record = {"idea_id": "idea-001", "run_index": 0, "blocks": blocks}
        (set_dir / "runs.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")

        edited_blocks = copy.deepcopy(blocks)
        edited_blocks["architecture"]["epicenter_rationale"] = "generic text " * 10
        in_path = tmp_path / "edited.json"
        in_path.write_text(json.dumps({"idea_id": "idea-001", "blocks": edited_blocks}), encoding="utf-8")

        result = import_edited(set_dir, "idea-001", in_path, "K2", note="genericized")
        assert result.ok
        assert (set_dir / "degraded" / "idea-001.json").exists()
        manifest_rows = list(csv.DictReader((set_dir / "degraded" / "manifest.csv").open(encoding="utf-8")))
        assert manifest_rows[0]["idea_id"] == "idea-001"
        assert manifest_rows[0]["criterion"] == "K2"
        assert manifest_rows[0]["note"] == "genericized"


class TestExport:
    def _make_set_dir(self, tmp_path: Path) -> Path:
        set_dir = tmp_path / "set"
        set_dir.mkdir()
        lines = []
        for i in range(1, 6):
            idea_id = f"idea-{i:03d}"
            record = {
                "idea_id": idea_id, "run_index": 0, "project_id": f"proj-{i}", "status": "completed",
                "blocks": _sample_blocks(),
            }
            lines.append(json.dumps(record))
        (set_dir / "runs.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return set_dir

    def test_exports_five_files_with_no_identifying_markers(self, tmp_path: Path):
        set_dir = self._make_set_dir(tmp_path)
        out_dir = tmp_path / "export"
        keys_dir = tmp_path / "keys"
        idea_texts = {f"idea-{i:03d}": f"Idea text {i}" for i in range(1, 6)}

        exported = build_calibration_export(set_dir, out_dir, keys_dir, idea_texts, seed=42)
        assert len(exported) == 5
        assert sorted(e.file_id for e in exported) == [f"project-{letter}" for letter in FILE_LETTERS]

        for e in exported:
            content = (out_dir / f"{e.file_id}.md").read_text(encoding="utf-8")
            # No idea_id or project_id leaked into the judge-facing file.
            for other in exported:
                assert other.idea_id not in content
                if other.project_id:
                    assert other.project_id not in content
            assert e.tokens_estimated > 0

        key_rows = list(csv.DictReader((keys_dir / "key.csv").open(encoding="utf-8")))
        assert {r["file_id"] for r in key_rows} == {e.file_id for e in exported}

    def test_criteria_order_is_shuffled_per_file(self, tmp_path: Path):
        set_dir = self._make_set_dir(tmp_path)
        idea_texts = {f"idea-{i:03d}": f"Idea text {i}" for i in range(1, 6)}
        exported = build_calibration_export(set_dir, tmp_path / "export", tmp_path / "keys", idea_texts, seed=7)
        orders = [tuple(e.criteria_order) for e in exported]
        assert all(set(o) == set(CRITERION_IDS) for o in orders)
        # Not every file got the identical order (extremely unlikely with 5
        # independent shuffles of 5 items unless the RNG is broken).
        assert len(set(orders)) > 1

    def test_seed_makes_export_deterministic(self, tmp_path: Path):
        set_dir = self._make_set_dir(tmp_path)
        idea_texts = {f"idea-{i:03d}": f"Idea text {i}" for i in range(1, 6)}
        exported1 = build_calibration_export(set_dir, tmp_path / "export1", tmp_path / "keys1", idea_texts, seed=123)
        exported2 = build_calibration_export(set_dir, tmp_path / "export2", tmp_path / "keys2", idea_texts, seed=123)
        assert [(e.file_id, e.idea_id, e.criteria_order) for e in exported1] == \
               [(e.file_id, e.idea_id, e.criteria_order) for e in exported2]

    def test_degraded_override_is_used_when_present(self, tmp_path: Path):
        set_dir = self._make_set_dir(tmp_path)
        (set_dir / "degraded").mkdir()
        degraded_blocks = _sample_blocks()
        degraded_blocks["architecture"]["epicenter_rationale"] = "DEGRADED MARKER TEXT " * 5
        (set_dir / "degraded" / "idea-002.json").write_text(
            json.dumps({"idea_id": "idea-002", "blocks": degraded_blocks}), encoding="utf-8"
        )
        idea_texts = {f"idea-{i:03d}": f"Idea text {i}" for i in range(1, 6)}
        exported = build_calibration_export(set_dir, tmp_path / "export", tmp_path / "keys", idea_texts, seed=1)

        degraded_entry = next(e for e in exported if e.idea_id == "idea-002")
        assert degraded_entry.degraded is True
        content = (tmp_path / "export" / f"{degraded_entry.file_id}.md").read_text(encoding="utf-8")
        assert "DEGRADED MARKER TEXT" in content

        clean_entries = [e for e in exported if e.idea_id != "idea-002"]
        assert all(e.degraded is False for e in clean_entries)


class TestTokens:
    def test_estimate_scales_with_length(self):
        short = estimate_tokens("a" * 40)
        long = estimate_tokens("a" * 400)
        assert long > short
        assert estimate_tokens("") == 0


class TestScoring:
    def _file_ids(self) -> list[str]:
        return [f"project-{letter}" for letter in FILE_LETTERS]

    def test_template_has_correct_row_count(self, tmp_path: Path):
        out = tmp_path / "template.csv"
        write_score_template(out, self._file_ids())
        rows = list(csv.DictReader(out.open(encoding="utf-8")))
        assert len(rows) == 5 * len(ROUNDS) * len(CRITERION_IDS)

    def test_valid_filled_template_passes(self, tmp_path: Path):
        out = tmp_path / "template.csv"
        write_score_template(out, self._file_ids())
        rows = list(csv.DictReader(out.open(encoding="utf-8")))
        for row in rows:
            row["score"] = "3"
            row["rationale"] = "some rationale"
        filled = tmp_path / "filled.csv"
        with filled.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_id", "round", "criterion", "score", "rationale"])
            writer.writeheader()
            writer.writerows(rows)

        result = validate_scores(filled, self._file_ids())
        assert result.ok, result.errors
        assert len(result.rows) == 5 * len(ROUNDS) * len(CRITERION_IDS)

    def test_out_of_range_score_rejected(self, tmp_path: Path):
        filled = tmp_path / "filled.csv"
        with filled.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["file_id", "round", "criterion", "score", "rationale"])
            writer.writerow(["project-A", "1", "K1", "7", "bad"])
        result = validate_scores(filled, self._file_ids())
        assert not result.ok
        assert any("out of range" in e for e in result.errors)

    def test_missing_criterion_rejected(self, tmp_path: Path):
        out = tmp_path / "template.csv"
        write_score_template(out, self._file_ids())
        rows = list(csv.DictReader(out.open(encoding="utf-8")))
        for row in rows:
            row["score"] = "3"
        # drop one row entirely -> project-A round 1 is missing a criterion
        rows = [r for r in rows if not (r["file_id"] == "project-A" and r["round"] == "1" and r["criterion"] == "K1")]
        filled = tmp_path / "filled.csv"
        with filled.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_id", "round", "criterion", "score", "rationale"])
            writer.writeheader()
            writer.writerows(rows)

        result = validate_scores(filled, self._file_ids())
        assert not result.ok
        assert any("missing criteria" in e for e in result.errors)

    def test_missing_round_rejected(self, tmp_path: Path):
        out = tmp_path / "template.csv"
        write_score_template(out, self._file_ids())
        rows = list(csv.DictReader(out.open(encoding="utf-8")))
        for row in rows:
            row["score"] = "3"
        rows = [r for r in rows if not (r["file_id"] == "project-A" and r["round"] == "3")]
        filled = tmp_path / "filled.csv"
        with filled.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["file_id", "round", "criterion", "score", "rationale"])
            writer.writeheader()
            writer.writerows(rows)

        result = validate_scores(filled, self._file_ids())
        assert not result.ok
        assert any("missing round" in e for e in result.errors)

    def test_store_scores_roundtrip(self, tmp_path: Path):
        set_dir = tmp_path / "set"
        rows = [{"file_id": "project-A", "round": "1", "criterion": "K1", "score": "4", "rationale": "ok"}]
        path = store_scores(set_dir, rows)
        assert path.exists()
        stored = list(csv.DictReader(path.open(encoding="utf-8")))
        assert stored == rows
