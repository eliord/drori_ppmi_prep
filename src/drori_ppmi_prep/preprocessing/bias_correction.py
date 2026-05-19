from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np


SYNTHSEG_WM_LABELS = (2, 41)


def create_synthseg_wm_mask(synthseg_path: str | Path, output_mask_path: str | Path):
    synthseg_path = Path(synthseg_path)
    output_mask_path = Path(output_mask_path)

    if not synthseg_path.exists():
        return None, "missing"

    synthseg_img = nib.load(str(synthseg_path))
    synthseg_data = synthseg_img.get_fdata()
    mask = np.isin(np.rint(synthseg_data).astype(np.int32), SYNTHSEG_WM_LABELS).astype(np.uint8)

    output_mask_path.parent.mkdir(parents=True, exist_ok=True)
    mask_img = nib.Nifti1Image(mask, synthseg_img.affine, synthseg_img.header)
    mask_img.set_data_dtype(np.uint8)
    nib.save(mask_img, str(output_mask_path))

    return output_mask_path, "done"


def run_t1_space_bias_correction(
    session_dir: str | Path,
    overwrite: bool = False,
    degree: int = 2,
):
    session_dir = Path(session_dir)
    t1_space_dir = session_dir / "t1_space"
    output_dir = t1_space_dir / f"mri_unbias_deg{degree}"
    synthseg_segmentation = (
        t1_space_dir
        / "segmentation"
        / "synthseg"
        / "synthseg.nii.gz"
    )
    wm_mask = output_dir / "wm_labels_2_41_mask.nii.gz"

    if not synthseg_segmentation.exists():
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
    expected_outputs.append(wm_mask)

    if all(path.exists() for path in expected_outputs) and not overwrite:
        return output_dir, "skipped"

    try:
        from mri_unbias.io import unbias_nifti
    except ImportError as exc:
        raise ImportError(
            "Bias correction requires mri-unbias. Reinstall drori_ppmi_prep "
            "so pip installs its dependencies."
        ) from exc

    if overwrite or not wm_mask.exists():
        _, mask_status = create_synthseg_wm_mask(synthseg_segmentation, wm_mask)
        if mask_status != "done":
            return None, mask_status

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
