import argparse
from pathlib import Path

from drori_ppmi_prep.segmentation.dbsegment import run_dbsegment


def run_dbsegment_segmentations(
    analysis_root,
    model_path=None,
    dbsegment_cmd="DBSegment",
    overwrite=False,
):
    analysis_root = Path(analysis_root)

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    if model_path is None:
        model_path = analysis_root.parent / "group_analysis" / "DBSegment"
    model_path = Path(model_path)
    model_path.mkdir(parents=True, exist_ok=True)

    processed_sessions = 0
    skipped_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            input_image = session_dir / "t1_space" / "segmentation" / "synthstrip" / "T1_brainmask.nii.gz"
            output_dir = session_dir / "t1_space" / "segmentation" / "dbsegment"

            if not input_image.exists():
                skipped_sessions += 1
                continue

            print(f"Running DBSegment for session: {session_dir}")

            run_dbsegment(
                input_image=input_image,
                output_dir=output_dir,
                model_path=model_path,
                dbsegment_cmd=dbsegment_cmd,
                overwrite=overwrite,
            )

            processed_sessions += 1

    print(f"Done. Processed {processed_sessions} sessions, skipped {skipped_sessions} sessions.")


def main():
    parser = argparse.ArgumentParser(
        description="Run DBSegment on T1 SynthStrip outputs in all analysis sessions."
    )
    parser.add_argument(
        "analysis_root",
        help="Root directory of the analysis dataset",
    )
    parser.add_argument(
        "--model-path",
        default=None,
        help="DBSegment model/cache directory. Defaults to ANALYSIS_ROOT/../group_analysis/DBSegment.",
    )
    parser.add_argument(
        "--dbsegment-cmd",
        default="DBSegment",
        help="DBSegment command name or full path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs",
    )

    args = parser.parse_args()

    run_dbsegment_segmentations(
        analysis_root=args.analysis_root,
        model_path=args.model_path,
        dbsegment_cmd=args.dbsegment_cmd,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
