import argparse
from pathlib import Path

from drori_ppmi_prep.segmentation.first import run_fsl_first


def run_fsl_first_segmentations(
    analysis_root,
    overwrite=False,
    first_cmd="run_first_all",
):
    analysis_root = Path(analysis_root)

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    processed_sessions = 0
    skipped_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            t1_image = session_dir / "t1_space" / "T1.nii.gz"
            output_dir = session_dir / "t1_space" / "segmentation" / "fslfirst"

            if not t1_image.exists():
                skipped_sessions += 1
                continue

            print(f"Running FSL FIRST for session: {session_dir}")

            run_fsl_first(
                input_image=t1_image,
                output_dir=output_dir,
                first_cmd=first_cmd,
                overwrite=overwrite,
            )

            processed_sessions += 1

    print(f"Done. Processed {processed_sessions} sessions, skipped {skipped_sessions} sessions.")


def main():
    parser = argparse.ArgumentParser(
        description="Run FSL FIRST on T1 images in all analysis sessions."
    )
    parser.add_argument(
        "analysis_root",
        help="Root directory of the analysis dataset",
    )
    parser.add_argument(
        "--first-cmd",
        default="run_first_all",
        help="FIRST command name or full path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs",
    )

    args = parser.parse_args()

    run_fsl_first_segmentations(
        analysis_root=args.analysis_root,
        overwrite=args.overwrite,
        first_cmd=args.first_cmd,
    )


if __name__ == "__main__":
    main()

