from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


def run_synthseg(
    input_image,
    output_dir,
    synthseg_cmd="mri_synthseg",
    overwrite=False,
):
    input_image = Path(input_image)
    output_dir = Path(output_dir)

    if not input_image.exists():
        return None, "missing"

    output_file = output_dir / "synthseg.nii.gz"
    if output_file.exists() and not overwrite:
        return output_file, "skipped"

    if shutil.which(synthseg_cmd) is None:
        return None, "missing_command"

    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        synthseg_cmd,
        "--i", str(input_image),
        "--o", str(output_file),
    ]

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if result.returncode != 0:
        return None, "failed"

    if output_file.exists():
        return output_file, "done"

    return None, "failed"
