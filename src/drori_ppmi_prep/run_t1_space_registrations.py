from __future__ import annotations

import argparse
from pathlib import Path

from drori_ppmi_prep.fsl_flirt_utils import register_then_apply_to_others


def register_session_to_t1_space(
    session_dir: str | Path,
    overwrite: bool = False,
    flirt_cmd: str = "flirt",
    dof: int = 9,
    cost: str = "corratio",
    interp: str = "trilinear",
) -> None:
    session_dir = Path(session_dir)

    t1_native = session_dir / "T1.nii.gz"
    t2_native = session_dir / "T2.nii.gz"
    pd_native = session_dir / "PD.nii.gz"

    synthstrip_dir = session_dir / "segmentation_native" / "synthstrip"
    t1_brain = synthstrip_dir / "T1_brainmask.nii.gz"
    pd_brain = synthstrip_dir / "PD_brainmask.nii.gz"

    if not t1_native.exists():
        raise FileNotFoundError(f"Missing T1 image: {t1_native}")
    if not pd_native.exists():
        raise FileNotFoundError(f"Missing PD image: {pd_native}")
    if not t1_brain.exists():
        raise FileNotFoundError(f"Missing brainmasked T1 image: {t1_brain}")
    if not pd_brain.exists():
        raise FileNotFoundError(f"Missing brainmasked PD image: {pd_brain}")

    out_dir = session_dir / "t1_space"
    out_dir.mkdir(parents=True, exist_ok=True)

    t1_link = out_dir / "T1.nii.gz"
    if overwrite and (t1_link.exists() or t1_link.is_symlink()):
        t1_link.unlink()
    if not t1_link.exists():
        t1_link.symlink_to(t1_native.resolve())

    apply_jobs = [
        (pd_native, out_dir / "PD.nii.gz"),
    ]

    if t2_native.exists():
        apply_jobs.append((t2_native, out_dir / "T2.nii.gz"))

    register_then_apply_to_others(
        registration_moving_image=pd_brain,
        registration_reference_image=t1_brain,
        output_matrix=out_dir / "flirt9dof_PD_to_T1.mat",
        apply_jobs=apply_jobs,
        registration_output_image=None,
        flirt_cmd=flirt_cmd,
        dof=dof,
        cost=cost,
        interp=interp,
        overwrite=overwrite,
    )


def run_t1_space_registrations(
    analysis_root: str | Path,
    overwrite: bool = False,
    flirt_cmd: str = "flirt",
    dof: int = 9,
    cost: str = "corratio",
    interp: str = "trilinear",
) -> None:
    analysis_root = Path(analysis_root)

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    processed_sessions = 0
    skipped_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            print(f"Processing registration for session: {session_dir}")

            try:
                register_session_to_t1_space(
                    session_dir=session_dir,
                    overwrite=overwrite,
                    flirt_cmd=flirt_cmd,
                    dof=dof,
                    cost=cost,
                    interp=interp,
                )
                processed_sessions += 1
            except FileNotFoundError as e:
                print(f"  Skipping session: {e}")
                skipped_sessions += 1

    print(f"Done. Processed {processed_sessions} sessions, skipped {skipped_sessions} sessions.")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Register brainmasked PD to brainmasked T1 using FLIRT, then apply the "
            "transform to original PD and T2 for each analysis session."
        )
    )
    parser.add_argument("analysis_root", help="Root directory of the analysis dataset")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing outputs")
    parser.add_argument("--flirt-cmd", default="flirt", help="FLIRT executable name or full path")
    parser.add_argument("--dof", type=int, default=9, help="Degrees of freedom for FLIRT registration")
    parser.add_argument("--cost", default="corratio", help="FLIRT cost function")
    parser.add_argument("--interp", default="trilinear", help="Interpolation method")

    args = parser.parse_args()

    run_t1_space_registrations(
        analysis_root=args.analysis_root,
        overwrite=args.overwrite,
        flirt_cmd=args.flirt_cmd,
        dof=args.dof,
        cost=args.cost,
        interp=args.interp,
    )


if __name__ == "__main__":
    main()
