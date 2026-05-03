import argparse
from pathlib import Path

from drori_ppmi_prep.synthstrip_utils import run_synthstrip


def process_image(analysis_session_dir: Path, image_name: str, overwrite: bool = False) -> None:
    """
    Run SynthStrip on one image in one analysis session directory.

    Expected input:
        analysis_session_dir / f"{image_name}.nii.gz"

    Outputs:
        analysis_session_dir/segmentation_native/synthstrip/{image_name}_brainmask.nii.gz
        analysis_session_dir/segmentation_native/synthstrip/{image_name}_brainmask_mask.nii.gz
        analysis_session_dir/segmentation_native/synthstrip/{image_name}_brainmask_nocsf.nii.gz
        analysis_session_dir/segmentation_native/synthstrip/{image_name}_brainmask_mask_nocsf.nii.gz
    """
    input_nii = analysis_session_dir / f"{image_name}.nii.gz"
    if not input_nii.exists():
        return

    synthstrip_dir = analysis_session_dir / "segmentation_native" / "synthstrip"
    synthstrip_dir.mkdir(parents=True, exist_ok=True)

    # Standard SynthStrip
    output_nii = synthstrip_dir / f"{image_name}_brainmask.nii.gz"
    output_mask = synthstrip_dir / f"{image_name}_brainmask_mask.nii.gz"

    print(f"  Running SynthStrip on {input_nii}")
    run_synthstrip(
        input_nii=input_nii,
        output_nii=output_nii,
        mask_nii=output_mask,
        overwrite=overwrite,
        no_csf=False,
    )

    # SynthStrip with --no-csf
    output_nii_nocsf = synthstrip_dir / f"{image_name}_brainmask_nocsf.nii.gz"
    output_mask_nocsf = synthstrip_dir / f"{image_name}_brainmask_mask_nocsf.nii.gz"

    print(f"  Running SynthStrip (--no-csf) on {input_nii}")
    run_synthstrip(
        input_nii=input_nii,
        output_nii=output_nii_nocsf,
        mask_nii=output_mask_nocsf,
        overwrite=overwrite,
        no_csf=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run SynthStrip on T1/T2/PD images in each analysis folder and write "
            "outputs under segmentation_native/synthstrip/."
        )
    )
    parser.add_argument(
        "nifti_root",
        help="Root directory of the NIfTI dataset (accepted for pipeline consistency).",
    )
    parser.add_argument(
        "analysis_root",
        help="Root directory of the analysis dataset.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing SynthStrip outputs.",
    )

    args = parser.parse_args()

    nifti_root = Path(args.nifti_root)
    analysis_root = Path(args.analysis_root)

    if not nifti_root.exists():
        raise FileNotFoundError(f"NIfTI root not found: {nifti_root}")
    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    print("Scanning analysis dataset for session folders...")
    processed_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            print(f"Processing session: {session_dir}")
            process_image(session_dir, "T1", overwrite=args.overwrite)
            process_image(session_dir, "T2", overwrite=args.overwrite)
            process_image(session_dir, "PD", overwrite=args.overwrite)
            processed_sessions += 1

    print(f"Done. Processed {processed_sessions} session folders.")


if __name__ == "__main__":
    main()
