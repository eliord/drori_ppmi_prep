from __future__ import annotations

from pathlib import Path
import shutil
import subprocess


def run_flirt_registration(
    moving_image: str | Path,
    reference_image: str | Path,
    output_matrix: str | Path,
    output_image: str | Path | None = None,
    flirt_cmd: str = "flirt",
    dof: int = 9,
    cost: str = "corratio",
    interp: str = "trilinear",
    overwrite: bool = False,
) -> None:
    """
    Run FLIRT registration and save the transform matrix.
    Optionally also save the registered image.
    """
    moving_image = Path(moving_image)
    reference_image = Path(reference_image)
    output_matrix = Path(output_matrix)
    output_image = Path(output_image) if output_image is not None else None

    if not moving_image.exists():
        raise FileNotFoundError(f"Moving image not found: {moving_image}")
    if not reference_image.exists():
        raise FileNotFoundError(f"Reference image not found: {reference_image}")

    if shutil.which(flirt_cmd) is None:
        raise FileNotFoundError(f"{flirt_cmd} not found on PATH. Install/configure FSL first.")

    if output_image is None:
        if output_matrix.exists() and not overwrite:
            return
    else:
        if output_matrix.exists() and output_image.exists() and not overwrite:
            return

    output_matrix.parent.mkdir(parents=True, exist_ok=True)
    if output_image is not None:
        output_image.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        flirt_cmd,
        "-in", str(moving_image),
        "-ref", str(reference_image),
        "-omat", str(output_matrix),
        "-dof", str(dof),
        "-cost", cost,
        "-interp", interp,
    ]

    if output_image is not None:
        cmd += ["-out", str(output_image)]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"FLIRT registration failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def apply_flirt_transform(
    moving_image: str | Path,
    reference_image: str | Path,
    transform_matrix: str | Path,
    output_image: str | Path,
    flirt_cmd: str = "flirt",
    interp: str = "trilinear",
    overwrite: bool = False,
) -> None:
    """
    Apply a precomputed FLIRT transform matrix to an image.
    """
    moving_image = Path(moving_image)
    reference_image = Path(reference_image)
    transform_matrix = Path(transform_matrix)
    output_image = Path(output_image)

    if not moving_image.exists():
        raise FileNotFoundError(f"Moving image not found: {moving_image}")
    if not reference_image.exists():
        raise FileNotFoundError(f"Reference image not found: {reference_image}")
    if not transform_matrix.exists():
        raise FileNotFoundError(f"Transform matrix not found: {transform_matrix}")

    if shutil.which(flirt_cmd) is None:
        raise FileNotFoundError(f"{flirt_cmd} not found on PATH. Install/configure FSL first.")

    if output_image.exists() and not overwrite:
        return

    output_image.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        flirt_cmd,
        "-in", str(moving_image),
        "-ref", str(reference_image),
        "-out", str(output_image),
        "-applyxfm",
        "-init", str(transform_matrix),
        "-interp", interp,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"FLIRT applyxfm failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )


def register_then_apply_to_others(
    registration_moving_image: str | Path,
    registration_reference_image: str | Path,
    output_matrix: str | Path,
    apply_jobs: list[tuple[str | Path, str | Path]],
    registration_output_image: str | Path | None = None,
    flirt_cmd: str = "flirt",
    dof: int = 9,
    cost: str = "corratio",
    interp: str = "trilinear",
    overwrite: bool = False,
) -> None:
    """
    Compute a transform from one moving/reference pair, then apply it to other images.

    Parameters
    ----------
    registration_moving_image
        Image used as the moving image for estimating the transform.
    registration_reference_image
        Image used as the reference image for estimating the transform.
    output_matrix
        Output FLIRT transform matrix.
    apply_jobs
        List of (moving_image, output_image) pairs to which the estimated transform
        will be applied, always using registration_reference_image as the reference.
    registration_output_image
        Optional registered output image for the registration pair.
    """
    run_flirt_registration(
        moving_image=registration_moving_image,
        reference_image=registration_reference_image,
        output_matrix=output_matrix,
        output_image=registration_output_image,
        flirt_cmd=flirt_cmd,
        dof=dof,
        cost=cost,
        interp=interp,
        overwrite=overwrite,
    )

    for moving_image, output_image in apply_jobs:
        apply_flirt_transform(
            moving_image=moving_image,
            reference_image=registration_reference_image,
            transform_matrix=output_matrix,
            output_image=output_image,
            flirt_cmd=flirt_cmd,
            interp=interp,
            overwrite=overwrite,
        )
