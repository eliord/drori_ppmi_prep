from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


def run_synthstrip(
    input_nii: str | Path,
    output_nii: str | Path,
    mask_nii: str | Path | None = None,
    synthstrip_cmd: str = "mri_synthstrip",
    overwrite: bool = False,
    no_csf: bool = False,
) -> None:
    input_nii = Path(input_nii)
    output_nii = Path(output_nii)
    mask_nii = Path(mask_nii) if mask_nii is not None else None

    if not input_nii.exists():
        raise FileNotFoundError(f"Input image not found: {input_nii}")

    if shutil.which(synthstrip_cmd) is None:
        raise FileNotFoundError(
            f"{synthstrip_cmd} not found on PATH. Install SynthStrip first."
        )

    if output_nii.exists() and not overwrite:
        return

    output_nii.parent.mkdir(parents=True, exist_ok=True)
    if mask_nii is not None:
        mask_nii.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        synthstrip_cmd,
        "-i", str(input_nii),
        "-o", str(output_nii),
    ]

    if mask_nii is not None:
        cmd += ["-m", str(mask_nii)]

    if no_csf:
        cmd += ["--no-csf"]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"SynthStrip failed for {input_nii}\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
