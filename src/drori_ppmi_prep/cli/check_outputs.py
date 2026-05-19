import argparse
import csv
import json
from pathlib import Path

import pandas as pd


def resolve_analysis_root(path):
    path = Path(path)

    config_path = path / "ppmi_config.json"
    if config_path.exists():
        config = json.loads(config_path.read_text())
        return Path(config["analysis_root"])

    analysis_root = path / "PPMI_analysis"
    if analysis_root.exists():
        return analysis_root

    return path


def resolve_dataset_paths(path):
    path = Path(path)

    config_path = path / "ppmi_config.json"
    if not config_path.exists() and path.name == "PPMI_analysis":
        config_path = path.parent / "ppmi_config.json"

    if config_path.exists():
        config = json.loads(config_path.read_text())
        return {
            "analysis_root": Path(config["analysis_root"]),
            "metadata_csv": Path(config["metadata_csv"]),
            "nifti_root": Path(config["nifti_root"]),
        }

    analysis_root = path / "PPMI_analysis"
    if analysis_root.exists():
        return {
            "analysis_root": analysis_root,
            "metadata_csv": path / "ppmi_metadata.csv",
            "nifti_root": path / "PPMI_nifti",
        }

    return {
        "analysis_root": path,
        "metadata_csv": None,
        "nifti_root": None,
    }


def iter_session_dirs(analysis_root):
    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if session_dir.is_dir():
                yield subject_dir.name, session_dir.name, session_dir


def all_exist(session_dir, paths):
    return all((session_dir / path).exists() for path in paths)


def status(applicable, complete):
    if not applicable:
        return "not_applicable"
    if complete:
        return "done"
    return "missing_output"


def is_gzip_file(path):
    try:
        with open(path, "rb") as f:
            return f.read(2) == b"\x1f\x8b"
    except OSError:
        return False


def build_native_source_availability(metadata_csv, nifti_root):
    if metadata_csv is None or nifti_root is None:
        return {}

    metadata_csv = Path(metadata_csv)
    nifti_root = Path(nifti_root)

    if not metadata_csv.exists() or not nifti_root.exists():
        return {}

    df = pd.read_csv(metadata_csv)
    irrelevant_scans_ordered = ["GRAPPA_ND", "GRAPPA 2", "GRAPPA2", "TSE_AC_PC line"]
    nifti_index = {}

    for path in nifti_root.glob("*/*/*/*.nii.gz"):
        session_dir = path.parent
        sequence_dir = session_dir.parent
        subject_dir = sequence_dir.parent
        nifti_index[(subject_dir.name, session_dir.name, path.name)] = path

    def is_missing_value(value):
        if pd.isna(value):
            return True
        value = str(value).strip()
        return value == "" or value == "0" or value.lower() == "nan"

    def normalize_numeric_id(value):
        if is_missing_value(value):
            return None
        value = str(value).strip()
        try:
            numeric_value = float(value)
            if numeric_value.is_integer():
                return str(int(numeric_value))
        except Exception:
            pass
        return value

    def get_weighting_columns(weighting):
        cols = []
        if weighting in df.columns:
            desc_col = f"{weighting}_Description" if f"{weighting}_Description" in df.columns else None
            cols.append((weighting, desc_col))

        index = 1
        while f"{weighting}_{index}" in df.columns:
            image_col = f"{weighting}_{index}"
            desc_col = f"{weighting}_{index}_Description" if f"{weighting}_{index}_Description" in df.columns else None
            cols.append((image_col, desc_col))
            index += 1

        return cols

    def description_penalty(description):
        description = description.upper()
        for index, marker in enumerate(irrelevant_scans_ordered):
            if marker.upper() in description:
                return (1, index)
        return (0, -1)

    def choose_best_image(row, weighting):
        candidates = []

        for image_col, desc_col in get_weighting_columns(weighting):
            image_id = normalize_numeric_id(row.get(image_col))
            if image_id is None:
                continue

            description = ""
            if desc_col is not None and desc_col in row.index and pd.notna(row[desc_col]):
                description = str(row[desc_col])

            candidates.append((description_penalty(description), image_id))

        if not candidates:
            return None

        candidates.sort(key=lambda item: item[0])
        return candidates[0][1]

    def find_nifti_for_image(subject_id, session_id, image_id):
        if image_id is None:
            return None

        subject_id = normalize_numeric_id(subject_id)
        session_id = str(session_id).strip()
        if subject_id is None or not session_id:
            return None

        subject_dir = nifti_root / subject_id
        if not subject_dir.exists():
            return None

        filenames = [
            f"I{image_id}.nii.gz",
            f"{image_id}.nii.gz",
            f"I{image_id}_e1.nii.gz",
            f"{image_id}_e1.nii.gz",
            f"I{image_id}_e2.nii.gz",
            f"{image_id}_e2.nii.gz",
        ]

        for filename in filenames:
            path = nifti_index.get((subject_id, session_id, filename))
            if path is not None and is_gzip_file(path):
                return path

        return None

    availability = {}

    for _, row in df.iterrows():
        subject_id = normalize_numeric_id(row.get("SubjectID"))
        session_id = str(row.get("SessionID")).strip() if pd.notna(row.get("SessionID")) else ""
        if subject_id is None or not session_id:
            continue

        availability[(subject_id, session_id)] = {
            weighting: find_nifti_for_image(
                subject_id,
                session_id,
                choose_best_image(row, weighting),
            ) is not None
            for weighting in ["T1", "T2", "PD"]
        }

    return availability


def build_checks(session_dir, native_sources=None):
    native_t1 = Path("T1.nii.gz")
    native_t2 = Path("T2.nii.gz")
    native_pd = Path("PD.nii.gz")
    native_sources = native_sources or {}

    native_synthstrip = {
        image: [
            Path(f"segmentation_native/synthstrip/{image}_brainmask.nii.gz"),
            Path(f"segmentation_native/synthstrip/{image}_brainmask_mask.nii.gz"),
            Path(f"segmentation_native/synthstrip/{image}_brainmask_nocsf.nii.gz"),
            Path(f"segmentation_native/synthstrip/{image}_brainmask_mask_nocsf.nii.gz"),
        ]
        for image in ["T1", "T2", "PD"]
    }

    t1_space_synthstrip = [
        Path("t1_space/segmentation/synthstrip/T1_brainmask.nii.gz"),
        Path("t1_space/segmentation/synthstrip/T1_brainmask_mask.nii.gz"),
        Path("t1_space/segmentation/synthstrip/T1_brainmask_nocsf.nii.gz"),
        Path("t1_space/segmentation/synthstrip/T1_brainmask_mask_nocsf.nii.gz"),
    ]

    checks = {}

    native_t1_applicable = native_sources.get("T1", (session_dir / native_t1).exists())
    native_t2_applicable = native_sources.get("T2", (session_dir / native_t2).exists())
    native_pd_applicable = native_sources.get("PD", (session_dir / native_pd).exists())

    checks["native_T1_link"] = status(native_t1_applicable, (session_dir / native_t1).exists())
    checks["native_T2_link"] = status(native_t2_applicable, (session_dir / native_t2).exists())
    checks["native_PD_link"] = status(native_pd_applicable, (session_dir / native_pd).exists())

    checks["native_synthstrip_T1"] = status(
        (session_dir / native_t1).exists(),
        all_exist(session_dir, native_synthstrip["T1"]),
    )
    checks["native_synthstrip_T2"] = status(
        (session_dir / native_t2).exists(),
        all_exist(session_dir, native_synthstrip["T2"]),
    )
    checks["native_synthstrip_PD"] = status(
        (session_dir / native_pd).exists(),
        all_exist(session_dir, native_synthstrip["PD"]),
    )

    t1_registration_applicable = (
        (session_dir / native_t1).exists()
        and (session_dir / native_pd).exists()
        and (session_dir / native_synthstrip["T1"][0]).exists()
        and (session_dir / native_synthstrip["PD"][0]).exists()
    )

    checks["t1_space_T1"] = status(
        (session_dir / native_t1).exists(),
        (session_dir / "t1_space/T1.nii.gz").exists(),
    )
    checks["t1_space_PD"] = status(
        t1_registration_applicable,
        (session_dir / "t1_space/PD.nii.gz").exists(),
    )
    checks["t1_space_T2"] = status(
        t1_registration_applicable and (session_dir / native_t2).exists(),
        (session_dir / "t1_space/T2.nii.gz").exists(),
    )
    checks["t1_space_transform"] = status(
        t1_registration_applicable,
        (session_dir / "t1_space/flirt9dof_PD_to_T1.mat").exists(),
    )
    checks["t1_space_synthstrip"] = status(
        all_exist(session_dir, native_synthstrip["T1"]),
        all_exist(session_dir, t1_space_synthstrip),
    )

    t1_reference = Path("t1_space/segmentation/synthstrip/T1_brainmask.nii.gz")
    t1_reference_exists = (session_dir / t1_reference).exists()

    checks["fsl_first"] = status(
        t1_reference_exists,
        (session_dir / "t1_space/segmentation/fslfirst/first_all_fast_firstseg.nii.gz").exists(),
    )
    checks["fsl_first_eroded"] = status(
        t1_reference_exists,
        (session_dir / "t1_space/segmentation/fslfirst/first_all_fast_firstseg_eroded.nii.gz").exists(),
    )
    checks["dbsegment"] = status(
        t1_reference_exists,
        (session_dir / "t1_space/segmentation/dbsegment/T1.nii.gz").exists(),
    )

    freesurfer_link = session_dir / "t1_space/segmentation/freesurfer"
    checks["freesurfer_link"] = status(
        (session_dir / "t1_space/T1.nii.gz").exists(),
        freesurfer_link.exists(),
    )
    checks["freesurfer_t1_space_outputs"] = status(
        freesurfer_link.exists(),
        (session_dir / "t1_space/segmentation/freesurfer/t1_space_outputs/aparc+aseg.nii.gz").exists(),
    )

    bias_source = session_dir / "t1_space/segmentation/freesurfer/t1_space_outputs/aparc+aseg.nii.gz"
    bias_dir = session_dir / "t1_space/mri_unbias_deg2"
    bias_images = [
        image
        for image in ["T1", "PD", "T2"]
        if (session_dir / f"t1_space/{image}.nii.gz").exists()
    ]
    checks["mri_unbias_deg2"] = status(
        bias_source.exists() and bool(bias_images),
        all(
            (bias_dir / f"{image}.nii.gz").exists()
            and (bias_dir / f"{image}_bias.nii.gz").exists()
            for image in bias_images
        )
        and (bias_dir / "wm_labels_2_41_mask.nii.gz").exists(),
    )

    return checks


def check_analysis_outputs(analysis_root, native_source_availability=None):
    analysis_root = Path(analysis_root)
    native_source_availability = native_source_availability or {}

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    rows = []

    for subject_id, session_id, session_dir in iter_session_dirs(analysis_root):
        row = {
            "subject_id": subject_id,
            "session_id": session_id,
            "session_dir": str(session_dir),
        }
        row.update(build_checks(
            session_dir,
            native_source_availability.get((subject_id, session_id)),
        ))
        rows.append(row)

    return rows


def summarize(rows):
    if not rows:
        return []

    check_names = [
        key
        for key in rows[0]
        if key not in {"subject_id", "session_id", "session_dir"}
    ]

    summary = []
    for check_name in check_names:
        applicable = [row for row in rows if row[check_name] != "not_applicable"]
        done = [row for row in applicable if row[check_name] == "done"]
        missing = [row for row in applicable if row[check_name] == "missing_output"]
        not_applicable = [row for row in rows if row[check_name] == "not_applicable"]

        summary.append({
            "check": check_name,
            "applicable": len(applicable),
            "done": len(done),
            "missing": len(missing),
            "not_applicable": len(not_applicable),
        })

    return summary


def write_csv(rows, output_csv):
    output_csv = Path(output_csv)
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    with output_csv.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def print_summary(analysis_root, rows, summary):
    print(f"Analysis root : {analysis_root}")
    print(f"Total sessions: {len(rows)}")
    print()
    print("Check                          Applicable  Done  Missing  Not applicable")
    print("-" * 74)
    for item in summary:
        print(
            f"{item['check']:<30}"
            f"{item['applicable']:>11}"
            f"{item['done']:>6}"
            f"{item['missing']:>9}"
            f"{item['not_applicable']:>16}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Check completeness of PPMI analysis-session outputs."
    )
    parser.add_argument(
        "path",
        help="OUTPUT_ROOT, a directory containing PPMI_analysis, or PPMI_analysis itself.",
    )
    parser.add_argument(
        "--list-missing",
        action="store_true",
        help="Print sessions with missing outputs, grouped by check.",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help="Optional CSV path for the full per-session status table.",
    )

    args = parser.parse_args()

    dataset_paths = resolve_dataset_paths(args.path)
    analysis_root = dataset_paths["analysis_root"]
    native_source_availability = build_native_source_availability(
        dataset_paths["metadata_csv"],
        dataset_paths["nifti_root"],
    )
    rows = check_analysis_outputs(analysis_root, native_source_availability)
    summary = summarize(rows)

    print_summary(analysis_root, rows, summary)

    if args.csv is not None and rows:
        write_csv(rows, args.csv)
        print()
        print(f"CSV report: {args.csv}")

    if args.list_missing:
        print()
        print("Missing outputs:")
        for item in summary:
            if item["missing"] == 0:
                continue
            print(f"\n{item['check']} ({item['missing']} missing)")
            for row in rows:
                if row[item["check"]] == "missing_output":
                    print(f"  {row['subject_id']} / {row['session_id']}")
                    print(f"    {row['session_dir']}")


if __name__ == "__main__":
    main()
