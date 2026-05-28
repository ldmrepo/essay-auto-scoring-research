import json

import numpy as np
import pytest

from pipelines.build_features import (
    PHASE3_LABEL_COLUMNS,
    PHASE3_WEIGHT_COLUMNS,
    build_phase3_target_artifacts,
    compute_rubric_targets,
    resolve_source_path,
)


def _essay_doc(essay_id: str = "ESSAY_1") -> dict:
    return {
        "info": {
            "essay_id": essay_id,
            "essay_type": "argument",
            "essay_level": "2",
        },
        "student": {
            "student_grade_group": "middle",
            "student_grade": "middle_1",
            "location": "001",
        },
        "paragraph": [{"paragraph_txt": "sample body"}],
        "score": {
            "essay_scoreT_avg": 20.0,
            "essay_scoreT_detail": {
                "essay_scoreT_exp": [[3, 2, 0], [3, 3, 0], [2, 3, 0]],
                "essay_scoreT_org": [[3, 0, 3, 3], [2, 0, 3, 2], [2, 0, 2, 3]],
                "essay_scoreT_cont": [[3, 3, 3, 2], [3, 2, 3, 2], [2, 2, 2, 3]],
            },
        },
        "rubric": {
            "expression_weight": {
                "exp_grammar": 3,
                "exp_vocab": 3,
                "exp_style": 0,
                "exp": 3,
            },
            "organization_weight": {
                "org_paragraph": 0,
                "org_essay": 7,
                "org_coherence": 2,
                "org_quantity": 1,
                "org": 3,
            },
            "content_weight": {
                "con_clearance": 4,
                "con_description": 2,
                "con_novelty": 2,
                "con_prompt": 1,
                "con": 4,
            },
        },
    }


def test_compute_rubric_targets_matches_weighted_average_contract():
    targets = compute_rubric_targets(_essay_doc())

    assert targets["target_exp"] == pytest.approx((2.5 + 3.0 + 2.5) / 3)
    assert targets["target_org"] == pytest.approx((0.9 + 0.8 + 0.7) / 3)
    assert targets["target_cont"] == pytest.approx((26 / 9 + 24 / 9 + 19 / 9) / 3)
    assert targets["target_overall_norm"] == pytest.approx(2.0)
    assert targets["target_overall_raw"] == pytest.approx(20.0)
    assert [targets[column] for column in PHASE3_WEIGHT_COLUMNS] == [3.0, 3.0, 4.0, 0.5]


def test_compute_rubric_targets_rejects_schema_drift():
    doc = _essay_doc()
    del doc["rubric"]["content_weight"]["con_prompt"]

    with pytest.raises(ValueError, match="Phase 3 rubric validation failed"):
        compute_rubric_targets(doc)


def test_build_phase3_target_artifacts_are_machine_checkable(tmp_path):
    rows = []
    for idx in range(2):
        doc = _essay_doc(f"ESSAY_{idx}")
        rows.append(
            {
                "essay_id": doc["info"]["essay_id"],
                "relative_path": f"sample/{idx}.json",
                "text_source_field": "paragraph[].paragraph_txt",
                "source_sha256": f"hash-{idx}",
                "phase3_targets": compute_rubric_targets(doc),
            }
        )

    result = build_phase3_target_artifacts(
        fold=0,
        rows=rows,
        output_dir=tmp_path,
        train_n=1,
        valid_n=1,
    )

    arrays = np.load(result["target_artifact_path"])
    assert arrays["labels"].shape == (2, 4)
    assert arrays["macro_weights"].shape == (2, 4)
    assert list(arrays["label_columns"]) == PHASE3_LABEL_COLUMNS
    assert list(arrays["macro_weight_columns"]) == PHASE3_WEIGHT_COLUMNS

    manifest = json.loads(
        (tmp_path / "fold_0_phase3_transformer_rows.json").read_text(encoding="utf-8")
    )
    assert manifest["prompt_text"]["enabled"] is False
    assert manifest["text_contract"]["field"] == "text"
    assert manifest["rows"][0]["partition"] == "train"
    assert manifest["rows"][1]["partition"] == "valid"


def test_resolve_source_path_accepts_sample_root_with_label_data_layer(tmp_path):
    relative_path = "TL_type/type/example.json"
    expected = tmp_path / "라벨링데이터" / relative_path
    expected.parent.mkdir(parents=True)
    expected.write_text("{}", encoding="utf-8")

    assert resolve_source_path(tmp_path, relative_path) == expected
