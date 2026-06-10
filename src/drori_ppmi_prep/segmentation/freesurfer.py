import shutil
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np


REQUIRED_FREESURFER_SEGMENTATIONS = (
    "aparc+aseg.mgz",
    "aparc.DKTatlas+aseg.mgz",
)


def freesurfer_outputs_exist(subject_dir):
    mri_dir = Path(subject_dir) / "mri"
    return all((mri_dir / filename).exists() for filename in REQUIRED_FREESURFER_SEGMENTATIONS)


def run_freesurfer(
    input_image,
    subjects_dir,
    subject_id,
    recon_all_cmd="recon-all",
    overwrite=False,
    restart_incomplete=False,
):
    input_image = Path(input_image)
    subjects_dir = Path(subjects_dir)
    subject_dir = subjects_dir / subject_id

    if not input_image.exists():
        return None, "missing"

    if freesurfer_outputs_exist(subject_dir) and not overwrite:
        return subject_dir, "skipped"

    if shutil.which(recon_all_cmd) is None:
        return None, "missing_command"

    if subject_dir.exists() and (overwrite or restart_incomplete):
        shutil.rmtree(subject_dir)

    subjects_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        recon_all_cmd,
        "-subjid", subject_id,
        "-sd", str(subjects_dir),
    ]
    if not subject_dir.exists():
        cmd.extend(["-i", str(input_image)])
    cmd.append("-all")

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
        return None, "failed"

    if not freesurfer_outputs_exist(subject_dir):
        return None, "failed"

    return subject_dir, "done"


def link_freesurfer_to_session(
    freesurfer_subject_dir,
    session_dir,
):
    freesurfer_mri_dir = Path(freesurfer_subject_dir) / "mri"
    session_dir = Path(session_dir)

    link_path = session_dir / "t1_space" / "segmentation" / "freesurfer"
    link_path.parent.mkdir(parents=True, exist_ok=True)

    if not freesurfer_mri_dir.exists():
        return None

    if link_path.exists() or link_path.is_symlink():
        link_path.unlink()

    link_path.symlink_to(freesurfer_mri_dir, target_is_directory=True)

    return link_path


def export_all_freesurfer_mgz_to_orig_space(
    freesurfer_mri_dir,
    reference_t1,
    output_dir,
    mri_vol2vol_cmd="mri_vol2vol",
    overwrite=False,
):
    if freesurfer_mri_dir is None:
        return [], "missing"

    freesurfer_mri_dir = Path(freesurfer_mri_dir)
    reference_t1 = Path(reference_t1)
    output_dir = Path(output_dir)

    if not freesurfer_mri_dir.exists():
        return [], "missing"

    if not reference_t1.exists():
        return [], "missing"

    if shutil.which(mri_vol2vol_cmd) is None:
        return [], "missing_command"

    required_segmentations = [
        freesurfer_mri_dir / filename
        for filename in REQUIRED_FREESURFER_SEGMENTATIONS
    ]
    if not all(path.exists() for path in required_segmentations):
        return [], "missing"

    output_dir.mkdir(parents=True, exist_ok=True)

    exported = []

    input_mgz_files = [
        *required_segmentations,
        *[
            path
            for path in sorted(freesurfer_mri_dir.glob("*.mgz"))
            if path not in required_segmentations
        ],
    ]

    for input_mgz in input_mgz_files:
        output_name = input_mgz.with_suffix(".nii.gz").name
        output_file = output_dir / output_name

        if output_file.exists() and not overwrite:
            exported.append(output_file)
            continue

        is_label = is_integer_label_volume(input_mgz)

        cmd = [
            mri_vol2vol_cmd,
            "--mov",
            str(input_mgz),
            "--targ",
            str(reference_t1),
            "--regheader",
            "--o",
            str(output_file),
        ]

        if is_label:
            cmd.append("--nearest")
        else:
            cmd.extend(["--interp", "trilinear"])

        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            return exported, "failed"
        exported.append(output_file)

        if input_mgz in required_segmentations and not output_file.exists():
            return exported, "failed"

    if not all(
        (output_dir / Path(filename).with_suffix(".nii.gz").name).exists()
        for filename in REQUIRED_FREESURFER_SEGMENTATIONS
    ):
        return exported, "failed"

    if exported:
        return exported, "done"

    return exported, "missing"


def is_integer_label_volume(image_path, max_unique_labels=5000):
    image = nib.load(str(image_path))
    data = image.get_fdata()

    finite_data = data[np.isfinite(data)]

    if finite_data.size == 0:
        return False

    values_are_integer = np.allclose(finite_data, np.round(finite_data))

    if not values_are_integer:
        return False

    unique_values = np.unique(finite_data)

    return unique_values.size <= max_unique_labels
