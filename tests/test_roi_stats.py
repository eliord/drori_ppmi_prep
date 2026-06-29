from drori_ppmi_prep.analysis.roi_stats import (
    DBSEGMENT_LABELS,
    MASSP_LABELS,
    _roi_column_name,
)


def test_roi_column_name_removes_hyphens():
    assert _roi_column_name("Lateral-ventricle-L") == "Lateral_ventricle_L"


def test_dbsegment_lut_uses_current_vpl_ventricle_vim_labels():
    assert DBSEGMENT_LABELS[26] == "VPL-L"
    assert DBSEGMENT_LABELS[27] == "VPL-R"
    assert DBSEGMENT_LABELS[28] == "Lateral-ventricle-L"
    assert DBSEGMENT_LABELS[29] == "Lateral-ventricle-R"
    assert DBSEGMENT_LABELS[30] == "VIM-L"
    assert DBSEGMENT_LABELS[31] == "VIM-R"


def test_massp_lut_uses_capital_l_r_suffixes():
    assert MASSP_LABELS[1] == "Str-L"
    assert MASSP_LABELS[2] == "Str-R"
    assert MASSP_LABELS[31] == "Cl-R"
