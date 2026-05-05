from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess


def run_freesurfer_recon_all(
    input_image: str | Path,
    subjects_dir: str | Path,
    subject_id: str,
    recon_all_cmd: str = "recon-all",
    overwrite: bool = False,
    directive: str = "-all",
    extra_args: list[str] | None = None,
) -> Path:
    """
    Run FreeSurfer recon-all on a single input image.

    Parameters
    ----------
    input_image
        Input MRI image path.
    subjects_dir
        FreeSurfer SUBJECTS_DIR where the output subject folder will be created.
    subject_id
        FreeSurfer subject ID (folder name inside subjects_dir).
    recon_all_cmd
        recon-all executable name or full path.
    overwrite
        If False and the output subject folder already exists, do nothing.
    directive
        Usually '-all', but can be changed if needed.
    extra_args
        Optional additional recon-all arguments.

    Returns
    -------
    Path
        Path to the created FreeSurfer subject directory.
    """
    input_image = Path(input_image)
    subjects_dir = Path(subjects_dir)
    subject_dir = subjects_dir / subject_id

    if not input_image.exists():
        raise FileNotFoundError(f"Input image not found: {input_image}")

    if shutil.which(recon_all_cmd) is None:
        raise FileNotFoundError(
            f"{recon_all_cmd} not found on PATH. Install/configure FreeSurfer first."
        )

    subjects_dir.mkdir(parents=True, exist_ok=True)

    if subject_dir.exists():
        if not overwrite:
            return subject_dir
        shutil.rmtree(subject_dir)

    cmd = [
        recon_all_cmd,
        "-subjid", subject_id,
        "-sd", str(subjects_dir),
        "-i", str(input_image),
        directive,
    ]

    if extra_args:
        cmd.extend(extra_args)

    env = os.environ.copy()
    env["SUBJECTS_DIR"] = str(subjects_dir)

    result = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if result.returncode != 0:
        raise RuntimeError(
            f"FreeSurfer recon-all failed.\n"
            f"Command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    return subject_dir
