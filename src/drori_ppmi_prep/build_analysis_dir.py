from __future__ import annotations

from pathlib import Path
import os
import pandas as pd


def build_analysis_dataset_from_metadata(
    metadata_csv: str | Path,
    nifti_root: str | Path,
    output_root: str | Path,
    overwrite: bool = False,
) -> pd.DataFrame:
    """
    Build an analysis dataset from metadata and a NIfTI root directory.

    For each row in the metadata table, create:
        output_root/SubjectID/SessionID/

    Inside that directory, create symlinks:
        T1.nii.gz
        T2.nii.gz
        PD.nii.gz

    The source NIfTI files are expected under a structure derived from the original
    converted dataset, where the final file name is based on the image ID:
        nifti_root/SUBJECT_ID/SEQUENCE_NAME/SESSION_ID/IIMAGE_ID.nii.gz
        or
        nifti_root/SUBJECT_ID/SEQUENCE_NAME/SESSION_ID/IMAGE_ID.nii.gz

    If multiple scans of the same weighting exist in one row, the function chooses
    the most relevant one based on the corresponding description columns, avoiding
    scans that contain certain irrelevant markers when better alternatives exist.

    Parameters
    ----------
    metadata_csv : str or Path
        Path to the metadata CSV.
    nifti_root : str or Path
        Root directory of the converted NIfTI dataset.
    output_root : str or Path
        Root directory where the analysis dataset will be created.
    overwrite : bool
        If True, replace existing symlinks/files.

    Returns
    -------
    pd.DataFrame
        A summary table with one row per metadata row, including the selected image IDs.
    """
    metadata_csv = Path(metadata_csv)
    nifti_root = Path(nifti_root)
    output_root = Path(output_root)

    if not metadata_csv.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {metadata_csv}")
    if not nifti_root.exists():
        raise FileNotFoundError(f"NIfTI root not found: {nifti_root}")

    df = pd.read_csv(metadata_csv)

    required_cols = ["SubjectID", "SessionID"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Metadata CSV is missing required columns: {missing}")

    irrelevant_scans_ordered = ['GRAPPA_ND', 'GRAPPA 2', 'GRAPPA2', 'TSE_AC_PC line']

    def is_missing_value(value: object) -> bool:
        if pd.isna(value):
            return True
        s = str(value).strip()
        return s == "" or s == "0" or s.lower() == "nan"

    def normalize_numeric_id(value: object) -> str | None:
        if is_missing_value(value):
            return None
        s = str(value).strip()
        try:
            f = float(s)
            if f.is_integer():
                return str(int(f))
        except Exception:
            pass
        return s

    def get_weighting_columns(weighting: str) -> list[tuple[str, str | None]]:
        """
        Returns pairs of (image_col, desc_col) in order:
            T1, T1_Description
            T1_1, T1_1_Description
            T1_2, T1_2_Description
            ...
        """
        cols: list[tuple[str, str | None]] = []
        if weighting in df.columns:
            desc_col = f"{weighting}_Description" if f"{weighting}_Description" in df.columns else None
            cols.append((weighting, desc_col))

        i = 1
        while f"{weighting}_{i}" in df.columns:
            image_col = f"{weighting}_{i}"
            desc_col = f"{weighting}_{i}_Description" if f"{weighting}_{i}_Description" in df.columns else None
            cols.append((image_col, desc_col))
            i += 1

        return cols

    def description_penalty(description: str) -> tuple[int, int]:
        """
        Lower is better.
        First component: whether any irrelevant marker appears.
        Second component: position in irrelevant_scans_ordered (later is less bad).
        """
        desc_upper = description.upper()
        for idx, marker in enumerate(irrelevant_scans_ordered):
            if marker.upper() in desc_upper:
                return (1, idx)
        return (0, -1)

    def choose_best_image(row: pd.Series, weighting: str) -> tuple[str | None, str]:
        candidates: list[tuple[tuple[int, int], str, str]] = []

        for image_col, desc_col in get_weighting_columns(weighting):
            image_id = normalize_numeric_id(row.get(image_col))
            if image_id is None:
                continue

            description = ""
            if desc_col is not None and desc_col in row.index and pd.notna(row[desc_col]):
                description = str(row[desc_col])

            penalty = description_penalty(description)
            candidates.append((penalty, image_id, description))

        if not candidates:
            return None, ""

        # Prefer scans with no irrelevant markers.
        # Among flagged scans, prefer the one whose marker is less redundant
        # according to irrelevant_scans_ordered.
        candidates.sort(key=lambda x: x[0])
        _, image_id, description = candidates[0]
        return image_id, description

    def find_nifti_for_image(subject_id: object, session_id: object, image_id: str | None) -> Path | None:
        if image_id is None:
            return None

        subject_str = normalize_numeric_id(subject_id)
        session_str = str(session_id).strip()

        if subject_str is None or session_str == "":
            return None

        subject_dir = nifti_root / subject_str
        if not subject_dir.exists():
            return None

        candidates = [
            f"I{image_id}.nii.gz",
            f"{image_id}.nii.gz",
            f"I{image_id}.nii",
            f"{image_id}.nii",
            f"I{image_id}_e1.nii.gz",
            f"{image_id}_e1.nii.gz",
            f"I{image_id}_e1.nii",
            f"{image_id}_e1.nii",
            f"I{image_id}_e2.nii.gz",
            f"{image_id}_e2.nii.gz",
            f"I{image_id}_e2.nii",
            f"{image_id}_e2.nii",
        ]

        # Expected structure: SUBJECT/SEQUENCE/SESSION/file
        for filename in candidates:
            matches = list(subject_dir.glob(f"*/{session_str}/{filename}"))
            if matches:
                return matches[0]

        return None

    def safe_symlink(src: Path, dst: Path, overwrite_link: bool = False) -> None:
        if dst.exists() or dst.is_symlink():
            if not overwrite_link:
                return
            dst.unlink()
        os.symlink(src, dst)

    selections = []

    for _, row in df.iterrows():
        subject_id = normalize_numeric_id(row["SubjectID"])
        session_id = str(row["SessionID"]).strip() if pd.notna(row["SessionID"]) else ""

        if subject_id is None or session_id == "":
            selections.append({
                "SubjectID": row.get("SubjectID", ""),
                "SessionID": row.get("SessionID", ""),
                "SelectedT1": "",
                "SelectedT2": "",
                "SelectedPD": "",
                "AnalysisDir": "",
            })
            continue

        analysis_dir = output_root / subject_id / session_id
        analysis_dir.mkdir(parents=True, exist_ok=True)

        selected = {}

        for weighting in ["T1", "T2", "PD"]:
            image_id, description = choose_best_image(row, weighting)
            nifti_path = find_nifti_for_image(subject_id, session_id, image_id)

            selected[weighting] = image_id if image_id is not None else ""
            selected[f"{weighting}_Description"] = description
            selected[f"{weighting}_Path"] = str(nifti_path) if nifti_path is not None else ""

            if nifti_path is not None:
                suffix = ".nii.gz" if nifti_path.name.endswith(".nii.gz") else nifti_path.suffix
                # Destination names should be fixed to T1.nii.gz, etc.
                dst_name = f"{weighting}.nii.gz" if suffix in [".gz", ".nii"] else f"{weighting}.nii.gz"
                safe_symlink(nifti_path, analysis_dir / dst_name, overwrite_link=overwrite)

        selections.append({
            "SubjectID": subject_id,
            "SessionID": session_id,
            "SelectedT1": selected["T1"],
            "SelectedT2": selected["T2"],
            "SelectedPD": selected["PD"],
            "AnalysisDir": str(analysis_dir),
        })

    summary_df = pd.DataFrame(selections)
    return summary_df
