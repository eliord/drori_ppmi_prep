import pandas as pd

from drori_ppmi_prep.metadata.builder import choose_analysis_candidate


def test_choose_analysis_candidate_prefers_non_excluded_description():
    row = {
        "T1_1": "I1",
        "T1_1_Description": "Sag MPRAGE GRAPPA_ND",
        "T1_2": "I2",
        "T1_2_Description": "Sag MPRAGE GRAPPA",
    }

    image_id, description = choose_analysis_candidate(row, "T1", 2)

    assert image_id == "I2"
    assert description == "Sag MPRAGE GRAPPA"


def test_choose_analysis_candidate_uses_last_repeat_when_quality_is_equal():
    row = {
        "T2_1": "I10",
        "T2_1_Description": "Axial T2",
        "T2_2": "I11",
        "T2_2_Description": "Axial T2",
    }

    image_id, description = choose_analysis_candidate(row, "T2", 2)

    assert image_id == "I11"
    assert description == "Axial T2"


def test_choose_analysis_candidate_ignores_missing_values():
    row = {
        "PD_1": 0,
        "PD_1_Description": "",
        "PD_2": pd.NA,
        "PD_2_Description": "",
        "PD_3": "I20",
        "PD_3_Description": "PD",
    }

    image_id, description = choose_analysis_candidate(row, "PD", 3)

    assert image_id == "I20"
    assert description == "PD"
