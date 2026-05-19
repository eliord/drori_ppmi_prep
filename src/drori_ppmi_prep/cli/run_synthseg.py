import argparse
from pathlib import Path

from drori_ppmi_prep.segmentation.synthseg import run_synthseg


def run_synthseg_segmentations(
    analysis_root,
    synthseg_cmd="mri_synthseg",
    overwrite=False,
):
    analysis_root = Path(analysis_root)

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    processed_sessions = 0
    skipped_sessions = 0
    failed_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            input_image = session_dir / "t1_space" / "T1.nii.gz"
            output_dir = session_dir / "t1_space" / "segmentation" / "synthseg"

            print(f"Running SynthSeg for session: {session_dir}")

            _, status = run_synthseg(
                input_image=input_image,
                output_dir=output_dir,
                synthseg_cmd=synthseg_cmd,
                overwrite=overwrite,
            )

            if status in {"done", "skipped"}:
                processed_sessions += 1
            elif status in {"missing", "missing_command"}:
                skipped_sessions += 1
            else:
                failed_sessions += 1

    print(
        "Done. "
        f"Processed {processed_sessions} sessions, "
        f"skipped {skipped_sessions} sessions, "
        f"failed {failed_sessions} sessions."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run FreeSurfer SynthSeg on T1-space T1 images in all analysis sessions."
    )
    parser.add_argument(
        "analysis_root",
        help="Root directory of the analysis dataset",
    )
    parser.add_argument(
        "--synthseg-cmd",
        default="mri_synthseg",
        help="FreeSurfer mri_synthseg command name or full path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs",
    )

    args = parser.parse_args()

    run_synthseg_segmentations(
        analysis_root=args.analysis_root,
        synthseg_cmd=args.synthseg_cmd,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
