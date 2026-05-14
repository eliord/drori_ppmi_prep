from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import shutil
import subprocess
from typing import Union


def find_existing_nifti_outputs(out_dir, image_id):
    return sorted(
        list(out_dir.glob(f"{image_id}*.nii.gz"))
        + list(out_dir.glob(f"{image_id}*.nii"))
    )


def convert_one_dicom_dir(job):
    (
        image_dir,
        input_root,
        output_root,
        dcm2niix_path,
        overwrite,
    ) = job

    image_dir = Path(image_dir)
    input_root = Path(input_root)
    output_root = Path(output_root)

    rel = image_dir.relative_to(input_root)
    parts = rel.parts

    if len(parts) != 4:
        return None, "unexpected_layout"

    subject_id, sequence_name, session_id, image_id = parts

    out_dir = output_root / subject_id / sequence_name / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    existing_outputs = find_existing_nifti_outputs(out_dir, image_id)

    if existing_outputs and not overwrite:
        return existing_outputs[0], "skipped"

    cmd = [
        dcm2niix_path,
        "-z", "y",
        "-b", "n",
        "-o", str(out_dir),
        "-f", image_id,
        str(image_dir),
    ]

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        return None, "failed"

    new_outputs = find_existing_nifti_outputs(out_dir, image_id)

    if new_outputs:
        return new_outputs[0], "done"

    return None, "failed"


def convert_ppmi_dicoms_to_nifti(
    input_root: Union[str, Path],
    output_root: Union[str, Path],
    dcm2niix_path: str = "dcm2niix",
    overwrite: bool = False,
    parallel: bool = False,
    max_workers: int | None = None,
) -> None:
    """
    Convert a PPMI-style DICOM dataset to NIfTI while preserving directory structure.

    Expected input layout:
        PPMI/SUBJECT_ID/SEQUENCE_NAME/SESSION_ID/IMAGE_ID/*.dcm

    Output layout:
        output_root/SUBJECT_ID/SEQUENCE_NAME/SESSION_ID/IMAGE_ID.nii.gz
    """
    input_root = Path(input_root).resolve()
    output_root = Path(output_root).resolve()

    if not input_root.exists():
        raise FileNotFoundError(f"Input root does not exist: {input_root}")

    if shutil.which(dcm2niix_path) is None:
        raise FileNotFoundError(
            f"dcm2niix not found: {dcm2niix_path}. "
            "Install it and ensure it is available on PATH."
        )

    output_root.mkdir(parents=True, exist_ok=True)

    image_dirs = []
    for path in input_root.rglob("*"):
        if path.is_dir():
            dcm_files = [p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".dcm"]
            if dcm_files:
                image_dirs.append(path)

    if not image_dirs:
        return

    jobs = [
        (
            image_dir,
            input_root,
            output_root,
            dcm2niix_path,
            overwrite,
        )
        for image_dir in sorted(image_dirs)
    ]

    counts = {
        "done": 0,
        "skipped": 0,
        "failed": 0,
        "unexpected_layout": 0,
    }

    if parallel:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(convert_one_dicom_dir, job) for job in jobs]

            for future in as_completed(futures):
                _, status = future.result()
                counts[status] = counts.get(status, 0) + 1
    else:
        for job in jobs:
            _, status = convert_one_dicom_dir(job)
            counts[status] = counts.get(status, 0) + 1

    print(
        "DICOM conversion finished. "
        f"Done: {counts['done']}, "
        f"skipped: {counts['skipped']}, "
        f"failed: {counts['failed']}, "
        f"unexpected layout: {counts['unexpected_layout']}."
    )

