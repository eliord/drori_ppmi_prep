import argparse
from pathlib import Path

from drori_ppmi_prep.segmentation.freesurfer import (
    export_all_freesurfer_mgz_to_orig_space,
    link_freesurfer_to_session,
    run_freesurfer,
)


def run_freesurfer_segmentations(
    analysis_root,
    subjects_dir=None,
    freesurfer_cmd="recon-all",
    mri_vol2vol_cmd="mri_vol2vol",
    overwrite=False,
    restart_incomplete_freesurfer=False,
):
    analysis_root = Path(analysis_root)

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    if subjects_dir is None:
        subjects_dir = analysis_root.parent / "group_analysis" / "FreeSurfer"
    subjects_dir = Path(subjects_dir)

    processed_sessions = 0
    skipped_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            reference_t1 = session_dir / "t1_space" / "T1.nii.gz"
            if not reference_t1.exists():
                skipped_sessions += 1
                continue

            freesurfer_subject_id = f"{subject_dir.name}_{session_dir.name}"

            print(f"Running FreeSurfer for session: {session_dir}")

            freesurfer_subject_dir, status = run_freesurfer(
                input_image=reference_t1,
                subjects_dir=subjects_dir,
                subject_id=freesurfer_subject_id,
                recon_all_cmd=freesurfer_cmd,
                overwrite=overwrite,
                restart_incomplete=restart_incomplete_freesurfer,
            )

            if status in {"missing", "missing_command", "failed"}:
                skipped_sessions += 1
                continue

            freesurfer_mri_link = link_freesurfer_to_session(
                freesurfer_subject_dir=freesurfer_subject_dir,
                session_dir=session_dir,
            )

            if freesurfer_mri_link is not None:
                _, export_status = export_all_freesurfer_mgz_to_orig_space(
                    freesurfer_mri_dir=freesurfer_mri_link,
                    reference_t1=reference_t1,
                    output_dir=freesurfer_mri_link / "t1_space_outputs",
                    mri_vol2vol_cmd=mri_vol2vol_cmd,
                    overwrite=overwrite,
                )
                if export_status not in {"done", "skipped"}:
                    skipped_sessions += 1
                    continue

            processed_sessions += 1

    print(f"Done. Processed {processed_sessions} sessions, skipped {skipped_sessions} sessions.")


def main():
    parser = argparse.ArgumentParser(
        description="Run FreeSurfer on T1-space T1 images in all analysis sessions."
    )
    parser.add_argument(
        "analysis_root",
        help="Root directory of the analysis dataset",
    )
    parser.add_argument(
        "--subjects-dir",
        default=None,
        help="FreeSurfer SUBJECTS_DIR. Defaults to ANALYSIS_ROOT/../group_analysis/FreeSurfer.",
    )
    parser.add_argument(
        "--freesurfer-cmd",
        default="recon-all",
        help="FreeSurfer recon-all command name or full path",
    )
    parser.add_argument(
        "--mri-vol2vol-cmd",
        default="mri_vol2vol",
        help="FreeSurfer mri_vol2vol command name or full path",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing outputs",
    )
    parser.add_argument(
        "--restart-incomplete-freesurfer",
        action="store_true",
        help="Delete and restart only incomplete FreeSurfer subject directories.",
    )

    args = parser.parse_args()

    run_freesurfer_segmentations(
        analysis_root=args.analysis_root,
        subjects_dir=args.subjects_dir,
        freesurfer_cmd=args.freesurfer_cmd,
        mri_vol2vol_cmd=args.mri_vol2vol_cmd,
        overwrite=args.overwrite,
        restart_incomplete_freesurfer=args.restart_incomplete_freesurfer,
    )


if __name__ == "__main__":
    main()
