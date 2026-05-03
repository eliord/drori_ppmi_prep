from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


def run_fsl_first(
    input_image: str | Path,
    output_dir: str | Path,
    first_cmd: str = "run_first_all",
    overwrite: bool = False,
    brain_extracted: bool = False,
    boundary_correction: str = "auto",
    structures: list[str] | None = None,
    affine_matrix: str | Path | None = None,
) -> None:
    """
    Run FSL FIRST on a single input image and write outputs into output_dir.

    Parameters
    ----------
    input_image
        Path to the input image.
    output_dir
        Directory where FIRST outputs will be written.
    first_cmd
        FIRST executable name or full path.
    overwrite
        Whether to overwrite existing outputs.
    brain_extracted
        If True, pass '-b' to FIRST.
    boundary_correction
        Value for FIRST '-m' option.
    structures
        Optional list of structures to segment.
    affine_matrix
        Optional affine matrix passed with '-a'.

    Notes
    -----
    FIRST writes outputs from an output basename, not just a directory.
    This function uses:

        output_dir / "fslfirst"

    as the basename.
    """
    input_image = Path(input_image)
    output_dir = Path(output_dir)

    if not input_image.exists():
        raise FileNotFoundError(f"Input image not found: {input_image}")

    if shutil.which(first_cmd) is None:
        raise FileNotFoundError(
            f"{first_cmd} not found on PATH. Install/configure FSL FIRST first."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    out_basename = output_dir / "fslfirst"

    expected_main_output = output_dir / "first_all_fast_firstseg.nii.gz"
    if expected_main_output.exists() and not overwrite:
        return

    if overwrite:
        for p in output_dir.iterdir():
            if p.is_file() or p.is_symlink():
                p.unlink()

    cmd = [
        first_cmd,
        "-i", str(input_image),
        "-o", str(out_basename),
        "-m", boundary_correction,
    ]

    if brain_extracted:
        cmd.append("-b")

    if structures:
        cmd += ["-s", ",".join(structures)]

    if affine_matrix is not None:
        affine_matrix = Path(affine_matrix)
        if not affine_matrix.exists():
            raise FileNotFoundError(f"Affine matrix not found: {affine_matrix}")
        cmd += ["-a", str(affine_matrix)]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"FIRST segmentation failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
