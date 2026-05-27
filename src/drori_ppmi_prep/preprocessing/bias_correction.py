from __future__ import annotations

from pathlib import Path

import nibabel as nib
import numpy as np

from drori_ppmi_prep.segmentation.utils import erode_label_segmentation


SYNTHSEG_WM_LABELS = (2, 41)
README_TEXT = """Bias map is estimated in each image using a 2-degree 3D polynomial within white-matter mask.
White-matter mask is defined as an eroded whole-WM ROI from SynthSeg.
Brain mask is defined from SynthStrip T1.
Raw image is divided by the estimated bias map.
"""


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
    brain_mask = (
        t1_space_dir
        / "segmentation"
        / "synthstrip"
        / "T1_brainmask_mask.nii.gz"
    )
    wm_mask = output_dir / "wm_mask.nii.gz"
    eroded_wm_mask = output_dir / "wm_mask_eroded.nii.gz"
    readme_file = output_dir / "README.txt"

    if not synthseg_segmentation.exists() or not brain_mask.exists():
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
    expected_outputs.extend([wm_mask, eroded_wm_mask, readme_file])

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

    if overwrite or not eroded_wm_mask.exists():
        eroded_output = erode_label_segmentation(
            segmentation_file=wm_mask,
            output_file=eroded_wm_mask,
            iterations=1,
            overwrite=overwrite,
        )
        if eroded_output is None:
            return None, "failed"

    if overwrite or not readme_file.exists():
        readme_file.write_text(README_TEXT)

    for image_path in images:
        corrected_path = output_dir / image_path.name
        bias_path = output_dir / f"{image_path.name.removesuffix('.nii.gz')}_bias.nii.gz"

        if corrected_path.exists() and bias_path.exists() and not overwrite:
            continue

        unbias_nifti(
            image_path=image_path,
            mask_path=eroded_wm_mask,
            corrected_path=corrected_path,
            bias_field_path=bias_path,
            degree=degree,
            brain_mask_path=brain_mask,
        )

    if all(path.exists() for path in expected_outputs):
        return output_dir, "done"

    return None, "failed"
