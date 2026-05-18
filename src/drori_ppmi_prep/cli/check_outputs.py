import argparse
import csv
import json
from pathlib import Path


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


def iter_session_dirs(analysis_root):
    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if session_dir.is_dir():
                yield subject_dir.name, session_dir.name, session_dir


def all_exist(session_dir, paths):
    return all((session_dir / path).exists() for path in paths)


def any_nifti_in(session_dir, path):
    target_dir = session_dir / path
    return target_dir.exists() and any(target_dir.glob("*.nii.gz"))


def status(applicable, complete):
    if not applicable:
        return "not_applicable"
    if complete:
        return "done"
    return "missing_output"


def build_checks(session_dir):
    native_t1 = Path("T1.nii.gz")
    native_t2 = Path("T2.nii.gz")
    native_pd = Path("PD.nii.gz")

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

    checks["native_T1_link"] = status(True, (session_dir / native_t1).exists())
    checks["native_T2_link"] = status(True, (session_dir / native_t2).exists())
    checks["native_PD_link"] = status(True, (session_dir / native_pd).exists())

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

    checks["t1_space_T1"] = status(
        (session_dir / native_t1).exists(),
        (session_dir / "t1_space/T1.nii.gz").exists(),
    )
    checks["t1_space_PD"] = status(
        (session_dir / native_pd).exists(),
        (session_dir / "t1_space/PD.nii.gz").exists(),
    )
    checks["t1_space_T2"] = status(
        (session_dir / native_t2).exists(),
        (session_dir / "t1_space/T2.nii.gz").exists(),
    )
    checks["t1_space_transform"] = status(
        (session_dir / native_pd).exists(),
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
        any_nifti_in(session_dir, Path("t1_space/segmentation/freesurfer/t1_space_outputs")),
    )

    return checks


def check_analysis_outputs(analysis_root):
    analysis_root = Path(analysis_root)

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    rows = []

    for subject_id, session_id, session_dir in iter_session_dirs(analysis_root):
        row = {
            "subject_id": subject_id,
            "session_id": session_id,
            "session_dir": str(session_dir),
        }
        row.update(build_checks(session_dir))
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

    analysis_root = resolve_analysis_root(args.path)
    rows = check_analysis_outputs(analysis_root)
    summary = summarize(rows)

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
