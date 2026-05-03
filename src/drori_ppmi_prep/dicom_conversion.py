from pathlib import Path
import shutil
import subprocess
from typing import Union


def convert_ppmi_dicoms_to_nifti(
    input_root: Union[str, Path],
    output_root: Union[str, Path],
    dcm2niix_path: str = "dcm2niix",
    overwrite: bool = False,
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
        print(f"No DICOM series found under: {input_root}")
        return

    for image_dir in sorted(image_dirs):
        rel = image_dir.relative_to(input_root)
        parts = rel.parts

        if len(parts) != 4:
            print(f"Skipping unexpected directory layout: {image_dir}")
            continue

        subject_id, sequence_name, session_id, image_id = parts

        out_dir = output_root / subject_id / sequence_name / session_id
        out_dir.mkdir(parents=True, exist_ok=True)

        ext = ".nii.gz"
        out_file = out_dir / f"{image_id}{ext}"

        if out_file.exists() and not overwrite:
            print(f"Skipping existing file: {out_file}")
            continue

        cmd = [
            dcm2niix_path,
            "-z", "y",
            "-b", "n",
            "-o", str(out_dir),
            "-f", image_id,
            str(image_dir),
        ]

        print(f"Converting: {image_dir} -> {out_file}")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"Conversion failed for {image_dir}\n"
                f"Command: {' '.join(cmd)}\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
