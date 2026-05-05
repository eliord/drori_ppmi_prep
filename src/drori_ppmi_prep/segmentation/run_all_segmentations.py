from __future__ import annotations

from pathlib import Path
import os
from typing import Any

from drori_ppmi_prep.segmentation.fsl_first import run_fsl_first
from drori_ppmi_prep.segmentation.freesurfer import run_freesurfer_recon_all


def _safe_symlink(src: Path, dst: Path, overwrite: bool = False) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)

    if dst.exists() or dst.is_symlink():
        if not overwrite:
            return
        if dst.is_dir() and not dst.is_symlink():
            raise IsADirectoryError(f"Refusing to overwrite directory symlink target: {dst}")
        dst.unlink()

    os.symlink(src, dst)


def run_segmentations_on_analysis_dataset(
    analysis_root: str | Path,
    output_root: str | Path,
    tools: dict[str, dict[str, Any]],
    overwrite: bool = False,
) -> None:
    """
    Run one or more segmentation tools on all sessions in the analysis dataset.

    Parameters
    ----------
    analysis_root
        Root of PPMI_analysis, expected layout:
            analysis_root/SUBJECT_ID/SESSION_ID/t1_space/T1.nii.gz
    output_root
        Global output root. Used by tools that write outside the session tree,
        e.g. FreeSurfer group outputs.
    tools
        Dictionary of tool configs. Example:

            {
                "fslfirst": {
                    "enabled": True,
                    "first_cmd": "run_first_all",
                    "brain_extracted": False,
                    "boundary_correction": "auto",
                    "structures": None,
                    "input_relpath": "t1_space/T1.nii.gz",
                },
                "freesurfer": {
                    "enabled": True,
                    "recon_all_cmd": "recon-all",
                    "version": "8.2.0",
                    "directive": "-all",
                    "extra_args": [],
                    "input_relpath": "t1_space/T1.nii.gz",
                },
            }

    Notes
    -----
    - FSL FIRST output:
        SUBJECT/SESSION/t1_space/segmentation/fslfirst/
    - FreeSurfer output:
        output_root/group_analysis/Freesurfer_v(version)/SUBJECT_SESSION/
      plus a symlink:
        SUBJECT/SESSION/t1_space/segmentation/freesurfer -> actual output dir
    """
    analysis_root = Path(analysis_root)
    output_root = Path(output_root)

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    output_root.mkdir(parents=True, exist_ok=True)

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            subject_id = subject_dir.name
            session_id = session_dir.name
            print(f"Processing segmentations for session: {subject_id}/{session_id}")

            # -------- FSL FIRST --------
            first_cfg = tools.get("fslfirst", {})
            if first_cfg.get("enabled", False):
                input_relpath = first_cfg.get("input_relpath", "t1_space/T1.nii.gz")
                input_image = session_dir / input_relpath
                output_dir = session_dir / "t1_space" / "segmentation" / "fslfirst"

                print(f"  Running FSL FIRST on: {input_image}")
                run_fsl_first(
                    input_image=input_image,
                    output_dir=output_dir,
                    first_cmd=first_cfg.get("first_cmd", "run_first_all"),
                    overwrite=overwrite,
                    brain_extracted=first_cfg.get("brain_extracted", False),
                    boundary_correction=first_cfg.get("boundary_correction", "auto"),
                    structures=first_cfg.get("structures"),
                    affine_matrix=first_cfg.get("affine_matrix"),
                )

            # -------- FreeSurfer --------
            fs_cfg = tools.get("freesurfer", {})
            if fs_cfg.get("enabled", False):
                input_relpath = fs_cfg.get("input_relpath", "t1_space/T1.nii.gz")
                input_image = session_dir / input_relpath
                version = fs_cfg.get("version", "unknown")
                subject_name = f"{subject_id}_{session_id}"

                subjects_dir = (
                    output_root
                    / "group_analysis"
                    / f"Freesurfer_v{version}"
                )

                print(f"  Running FreeSurfer recon-all on: {input_image}")
                fs_subject_dir = run_freesurfer_recon_all(
                    input_image=input_image,
                    subjects_dir=subjects_dir,
                    subject_id=subject_name,
                    recon_all_cmd=fs_cfg.get("recon_all_cmd", "recon-all"),
                    overwrite=overwrite,
                    directive=fs_cfg.get("directive", "-all"),
                    extra_args=fs_cfg.get("extra_args", []),
                )

                link_path = session_dir / "t1_space" / "segmentation" / "freesurfer"
                print(f"  Linking FreeSurfer output to: {link_path}")
                _safe_symlink(fs_subject_dir, link_path, overwrite=overwrite)