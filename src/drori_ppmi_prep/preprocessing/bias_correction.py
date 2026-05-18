from __future__ import annotations

from pathlib import Path


def run_t1_space_bias_correction(
    session_dir: str | Path,
    overwrite: bool = False,
    degree: int = 2,
):
    session_dir = Path(session_dir)
    t1_space_dir = session_dir / "t1_space"
    output_dir = t1_space_dir / f"mri_unbias_deg{degree}"
    wm_mask = (
        t1_space_dir
        / "segmentation"
        / "freesurfer"
        / "t1_space_outputs"
        / "wm.nii.gz"
    )

    if not wm_mask.exists():
        return None, "missing"

    images = [
        image_path
        for image_path in [
            t1_space_dir / "T1.nii.gz",
            t1_space_dir / "PD.nii.gz",
            t1_space_dir / "T2.nii.gz",
        ]
        if image_path.exists()
    ]

    if not images:
        return None, "missing"

    expected_outputs = []
    for image_path in images:
        expected_outputs.extend([
            output_dir / image_path.name,
            output_dir / f"{image_path.name.removesuffix('.nii.gz')}_bias.nii.gz",
        ])

    if all(path.exists() for path in expected_outputs) and not overwrite:
        return output_dir, "skipped"

    try:
        from mri_unbias.io import unbias_nifti
    except ImportError as exc:
        raise ImportError(
            "Bias correction requires mri-unbias. Reinstall drori_ppmi_prep "
            "so pip installs its dependencies."
        ) from exc

    for image_path in images:
        corrected_path = output_dir / image_path.name
        bias_path = output_dir / f"{image_path.name.removesuffix('.nii.gz')}_bias.nii.gz"

        if corrected_path.exists() and bias_path.exists() and not overwrite:
            continue

        unbias_nifti(
            image_path=image_path,
            mask_path=wm_mask,
            corrected_path=corrected_path,
            bias_field_path=bias_path,
            degree=degree,
        )

    if all(path.exists() for path in expected_outputs):
        return output_dir, "done"

    return None, "failed"
