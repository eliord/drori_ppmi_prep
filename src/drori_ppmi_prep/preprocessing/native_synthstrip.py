import argparse
from pathlib import Path

from drori_ppmi_prep.preprocessing.synthstrip import run_synthstrip


def run_native_synthstrip(
    analysis_session_dir: Path,
    image_name: str,
    overwrite: bool = False,
    synthstrip_cmd="mri_synthstrip",
):
    analysis_session_dir = Path(analysis_session_dir)

    input_nii = analysis_session_dir / f"{image_name}.nii.gz"
    if not input_nii.exists():
        return None, "missing"

    synthstrip_dir = analysis_session_dir / "segmentation_native" / "synthstrip"
    synthstrip_dir.mkdir(parents=True, exist_ok=True)

    output_nii = synthstrip_dir / f"{image_name}_brainmask.nii.gz"
    output_mask = synthstrip_dir / f"{image_name}_brainmask_mask.nii.gz"
    output_nii_nocsf = synthstrip_dir / f"{image_name}_brainmask_nocsf.nii.gz"
    output_mask_nocsf = synthstrip_dir / f"{image_name}_brainmask_mask_nocsf.nii.gz"

    expected_outputs = [
        output_nii,
        output_mask,
        output_nii_nocsf,
        output_mask_nocsf,
    ]

    if all(path.exists() for path in expected_outputs) and not overwrite:
        return synthstrip_dir, "skipped"

    run_synthstrip(
        input_nii=input_nii,
        output_nii=output_nii,
        mask_nii=output_mask,
        overwrite=overwrite,
        no_csf=False,
        synthstrip_cmd=synthstrip_cmd,
    )

    run_synthstrip(
        input_nii=input_nii,
        output_nii=output_nii_nocsf,
        mask_nii=output_mask_nocsf,
        overwrite=overwrite,
        no_csf=True,
        synthstrip_cmd=synthstrip_cmd,
    )

    if all(path.exists() for path in expected_outputs):
        return synthstrip_dir, "done"

    return None, "failed"


def synthstrip_native(*args, **kwargs):
    return run_native_synthstrip(*args, **kwargs)


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
    parser.add_argument(
        "--synthstrip-cmd",
        default="mri_synthstrip",
        help="SynthStrip executable name or full path.",
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
    skipped_images = 0
    missing_images = 0
    failed_images = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            print(f"Processing session: {session_dir}")

            for image_name in ["T1", "T2", "PD"]:
                _, status = run_native_synthstrip(
                    session_dir,
                    image_name,
                    overwrite=args.overwrite,
                    synthstrip_cmd=args.synthstrip_cmd,
                )

                if status == "done":
                    print(f"  {image_name}: DONE")
                elif status == "skipped":
                    print(f"  {image_name}: SKIPPED: already done")
                    skipped_images += 1
                elif status == "missing":
                    print(f"  {image_name}: SKIPPED: missing input")
                    missing_images += 1
                else:
                    print(f"  {image_name}: FAILED")
                    failed_images += 1

            processed_sessions += 1

    print(
        "Done. "
        f"Processed {processed_sessions} session folders. "
        f"Skipped images: {skipped_images}. "
        f"Missing images: {missing_images}. "
        f"Failed images: {failed_images}."
    )


if __name__ == "__main__":
    main()
