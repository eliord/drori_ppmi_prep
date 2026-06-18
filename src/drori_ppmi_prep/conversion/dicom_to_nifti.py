from __future__ import annotations
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import gzip
import shutil
import subprocess
from typing import Union


def is_gzip_file(path):
    with open(path, "rb") as f:
        return f.read(2) == b"\x1f\x8b"


def gzip_nifti_file(path):
    path = Path(path)

    if path.name.endswith(".nii.gz"):
        if is_gzip_file(path):
            return path

        output_path = path
    elif path.suffix == ".nii":
        output_path = path.with_suffix(".nii.gz")
    else:
        return None

    tmp_path = output_path.with_name(output_path.name + ".tmp")

    with open(path, "rb") as src, gzip.open(tmp_path, "wb") as dst:
        shutil.copyfileobj(src, dst)

    tmp_path.replace(output_path)

    if path != output_path and path.exists():
        path.unlink()

    return output_path


def find_expected_nifti_outputs(out_dir, image_id):
    candidates = []

    for stem in [image_id, f"{image_id}_e1", f"{image_id}_e2"]:
        candidates.append(out_dir / f"{stem}.nii.gz")

    return sorted(path for path in candidates if path.exists())


def find_related_nifti_outputs(out_dir, image_id):
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

    existing_outputs = find_expected_nifti_outputs(out_dir, image_id)

    if existing_outputs and not overwrite:
        gz_outputs = [
            gzip_nifti_file(path)
            for path in existing_outputs
        ]
        gz_outputs = sorted(path for path in gz_outputs if path is not None)
        if gz_outputs:
            return gz_outputs[0], "skipped"

    if overwrite:
        for output_path in find_related_nifti_outputs(out_dir, image_id):
            output_path.unlink()

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

    new_outputs = find_expected_nifti_outputs(out_dir, image_id)

    if new_outputs:
        gz_outputs = [
            gzip_nifti_file(path)
            for path in new_outputs
        ]
        gz_outputs = sorted(path for path in gz_outputs if path is not None)
        if gz_outputs:
            return gz_outputs[0], "done"

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


def convert_dicom_dir_to_nifti(
    dicom_dir: Union[str, Path],
    output_dir: Union[str, Path],
    filename: str,
    dcm2niix_path: str = "dcm2niix",
    overwrite: bool = False,
):
    """Convert one arbitrary DICOM directory to one or more gzipped NIfTI files."""
    dicom_dir = Path(dicom_dir)
    output_dir = Path(output_dir)

    if not dicom_dir.exists():
        raise FileNotFoundError(f"DICOM directory does not exist: {dicom_dir}")

    if shutil.which(dcm2niix_path) is None:
        raise FileNotFoundError(
            f"dcm2niix not found: {dcm2niix_path}. "
            "Install it and ensure it is available on PATH."
        )

    output_dir.mkdir(parents=True, exist_ok=True)

    existing_outputs = find_expected_nifti_outputs(output_dir, filename)
    if existing_outputs and not overwrite:
        return [gzip_nifti_file(path) for path in existing_outputs], "skipped"

    if overwrite:
        for output_path in find_related_nifti_outputs(output_dir, filename):
            output_path.unlink()

    cmd = [
        dcm2niix_path,
        "-z", "y",
        "-b", "n",
        "-o", str(output_dir),
        "-f", filename,
        str(dicom_dir),
    ]

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        return [], "failed"

    outputs = [
        gzip_nifti_file(path)
        for path in find_expected_nifti_outputs(output_dir, filename)
    ]
    outputs = [path for path in outputs if path is not None]
    if outputs:
        return outputs, "done"

    return [], "failed"
