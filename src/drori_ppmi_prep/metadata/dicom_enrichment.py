from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import pandas as pd
import pydicom


def is_missing_image_id(value: object) -> bool:
    if pd.isna(value):
        return True
    s = str(value).strip()
    return s == "" or s == "0" or s.lower() == "nan"


def find_image_dir(ppmi_root: Path, subject_id: object, image_id: object) -> Optional[Path]:
    if is_missing_image_id(image_id):
        return None

    subject_str = str(int(float(subject_id)))
    image_str = str(int(float(image_id)))

    subject_dir = ppmi_root / subject_str
    if not subject_dir.exists():
        return None

    matches = list(subject_dir.glob(f"*/*/I{image_str}"))
    return matches[0] if matches else None


def find_first_dcm(image_dir: Optional[Path]) -> Optional[Path]:
    if image_dir is None or not image_dir.exists():
        return None

    dcm_files = sorted(image_dir.glob("*.dcm"))
    return dcm_files[0] if dcm_files else None


def safe_get(ds: pydicom.dataset.FileDataset, attr: str, default: str = "") -> str:
    value = getattr(ds, attr, default)
    if value is None:
        return default
    return str(value)


def safe_float(ds: pydicom.dataset.FileDataset, attr: str) -> Optional[float]:
    value = getattr(ds, attr, None)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def format_number(x: Optional[float]) -> str:
    if x is None:
        return ""
    return f"{x:.2f}"


def build_t1_info(ds: pydicom.dataset.FileDataset) -> str:
    tr = format_number(safe_float(ds, "RepetitionTime"))
    te = format_number(safe_float(ds, "EchoTime"))
    ti = format_number(safe_float(ds, "InversionTime"))
    fa = format_number(safe_float(ds, "FlipAngle"))
    return f"TR={tr},TE={te},TI={ti},FA={fa}"


def build_t2_pd_info(ds: pydicom.dataset.FileDataset) -> str:
    tr = format_number(safe_float(ds, "RepetitionTime"))
    te = format_number(safe_float(ds, "EchoTime"))
    fa = format_number(safe_float(ds, "FlipAngle"))
    return f"TR={tr},TE={te},FA={fa}"


def process_metadata_row(job):
    row_index, row_dict, ppmi_root, t1_cols, t2_cols, pd_cols = job

    ppmi_root = Path(ppmi_root)
    subject_id = row_dict["SubjectID"]

    preferred_cols = t1_cols + t2_cols + pd_cols

    first_image_dir = None
    for col in preferred_cols:
        image_dir = find_image_dir(ppmi_root, subject_id, row_dict.get(col))
        if image_dir is not None:
            first_image_dir = image_dir
            break

    session_id = first_image_dir.parent.name if first_image_dir is not None else ""

    scanner_dcm = None
    for col in preferred_cols:
        image_dir = find_image_dir(ppmi_root, subject_id, row_dict.get(col))
        dcm_file = find_first_dcm(image_dir)
        if dcm_file is not None:
            scanner_dcm = dcm_file
            break

    institution_name = ""
    manufacturer = ""
    model = ""
    software = ""

    if scanner_dcm is not None:
        ds = pydicom.dcmread(scanner_dcm, stop_before_pixels=True)
        institution_name = safe_get(ds, "InstitutionName", "")
        manufacturer = safe_get(ds, "Manufacturer", "")
        model = safe_get(ds, "ManufacturerModelName", "")
        software = safe_get(ds, "SoftwareVersions", "")

    t1_info = ""
    for col in t1_cols:
        image_dir = find_image_dir(ppmi_root, subject_id, row_dict.get(col))
        dcm_file = find_first_dcm(image_dir)
        if dcm_file is not None:
            ds = pydicom.dcmread(dcm_file, stop_before_pixels=True)
            t1_info = build_t1_info(ds)
            break

    t2_info = ""
    for col in t2_cols:
        image_dir = find_image_dir(ppmi_root, subject_id, row_dict.get(col))
        dcm_file = find_first_dcm(image_dir)
        if dcm_file is not None:
            ds = pydicom.dcmread(dcm_file, stop_before_pixels=True)
            t2_info = build_t2_pd_info(ds)
            break

    pd_info = ""
    for col in pd_cols:
        image_dir = find_image_dir(ppmi_root, subject_id, row_dict.get(col))
        dcm_file = find_first_dcm(image_dir)
        if dcm_file is not None:
            ds = pydicom.dcmread(dcm_file, stop_before_pixels=True)
            pd_info = build_t2_pd_info(ds)
            break

    return row_index, {
        "SessionID": session_id,
        "AnalysisDir": f"{subject_id}/{session_id}" if session_id else "",
        "InstitutionName": institution_name,
        "Manufacturer": manufacturer,
        "Model": model,
        "Software": software,
        "T1_DicomInfo": t1_info,
        "T2_DicomInfo": t2_info,
        "PD_DicomInfo": pd_info,
    }


def enrich_metadata_with_dicom_info(
    metadata_csv: str | Path,
    ppmi_root: str | Path,
    output_csv: str | Path,
    parallel: bool = False,
    max_workers=None,
) -> pd.DataFrame:
    metadata_csv = Path(metadata_csv)
    ppmi_root = Path(ppmi_root)
    output_csv = Path(output_csv)

    if not metadata_csv.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {metadata_csv}")
    if not ppmi_root.exists():
        raise FileNotFoundError(f"PPMI root not found: {ppmi_root}")

    df = pd.read_csv(metadata_csv)

    if "SubjectID" not in df.columns:
        raise ValueError("Metadata CSV must contain a 'SubjectID' column.")

    def image_columns_for_weighting(weighting: str) -> list[str]:
        cols = []
        if weighting in df.columns:
            cols.append(weighting)

        i = 1
        while f"{weighting}_{i}" in df.columns:
            cols.append(f"{weighting}_{i}")
            i += 1

        return cols

    t1_cols = image_columns_for_weighting("T1")
    t2_cols = image_columns_for_weighting("T2")
    pd_cols = image_columns_for_weighting("PD")

    jobs = [
        (
            idx,
            row.to_dict(),
            ppmi_root,
            t1_cols,
            t2_cols,
            pd_cols,
        )
        for idx, row in df.iterrows()
    ]

    results = {}

    if parallel:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_metadata_row, job) for job in jobs]

            for future in as_completed(futures):
                row_index, row_result = future.result()
                results[row_index] = row_result
    else:
        for job in jobs:
            row_index, row_result = process_metadata_row(job)
            results[row_index] = row_result

    for col in [
        "SessionID",
        "AnalysisDir",
        "InstitutionName",
        "Manufacturer",
        "Model",
        "Software",
        "T1_DicomInfo",
        "T2_DicomInfo",
        "PD_DicomInfo",
    ]:
        df[col] = ""

    for row_index, row_result in results.items():
        for col, value in row_result.items():
            df.at[row_index, col] = value

    cols = list(df.columns)

    for col in ["SessionID", "AnalysisDir"]:
        if col in cols:
            cols.remove(col)

    if "Age" in cols:
        age_idx = cols.index("Age")
        cols.insert(age_idx + 1, "SessionID")
        cols.insert(age_idx + 2, "AnalysisDir")
    else:
        cols.extend(["SessionID", "AnalysisDir"])

    df = df[cols]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)

    return df
