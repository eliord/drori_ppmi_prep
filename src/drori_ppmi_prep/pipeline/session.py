import argparse
import json
from pathlib import Path

from drori_ppmi_prep.preprocessing.native_synthstrip import run_native_synthstrip
from drori_ppmi_prep.segmentation.directory_builder import link_t1_synthstrip_files_to_t1_space
from drori_ppmi_prep.registration.t1_space import register_session_to_t1_space
from drori_ppmi_prep.segmentation.first import run_fsl_first
from drori_ppmi_prep.segmentation.utils import erode_label_segmentation
from drori_ppmi_prep.segmentation.dbsegment import run_dbsegment
from drori_ppmi_prep.segmentation.synthseg import run_synthseg
from drori_ppmi_prep.segmentation.freesurfer import (
    run_freesurfer,
    link_freesurfer_to_session,
    export_all_freesurfer_mgz_to_orig_space,
)
from drori_ppmi_prep.preprocessing.bias_correction import run_t1_space_bias_correction
from drori_ppmi_prep.pipeline.paths import validate_output_root_path


def load_ppmi_config(output_root):
    output_root = validate_output_root_path(output_root)
    config_path = output_root / "ppmi_config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    return json.loads(config_path.read_text())


def print_done_or_skipped(status):
    if status == "done":
        print("    DONE")
    elif status == "skipped":
        print("    SKIPPED: already done")
    elif status == "missing":
        print("    SKIPPED: missing input")
    elif status == "missing_command":
        print("    SKIPPED: command not found")
    else:
        print("    FAILED")


def run_session_pipeline(
    output_root,
    subject_id,
    session_id,
    force=False,
    synthstrip_cmd="mri_synthstrip",
    flirt_cmd="flirt",
    first_cmd="run_first_all",
    synthseg_cmd="mri_synthseg",
    freesurfer_cmd="recon-all",
    mri_vol2vol_cmd="mri_vol2vol",
    dbsegment_cmd="DBSegment",
    dbsegment_model_path=None,
    dbsegment_use_cuda=True,
    run_first_segmentation=True,
    run_synthseg_segmentation=True,
    run_freesurfer_segmentation=True,
    run_dbsegment_segmentation=True,
    run_bias_correction=True,
    force_bias_correction=False,
):
    config = load_ppmi_config(output_root)
    analysis_root = Path(config["analysis_root"])
    output_root = validate_output_root_path(output_root)

    session_dir = analysis_root / str(subject_id) / str(session_id)
    if not session_dir.exists():
        raise FileNotFoundError(f"Session directory not found: {session_dir}")

    total_steps = (
            2
            + int(run_first_segmentation)
            + int(run_synthseg_segmentation)
            + int(run_freesurfer_segmentation)
            + int(run_dbsegment_segmentation)
            + int(run_bias_correction)
    )

    print(f" [START] {subject_id} / {session_id}")
    step = 1

    print(f"  ({step}/{total_steps}): Running SynthStrip ({synthstrip_cmd})... ", end="", flush=True)
    _, status1 = run_native_synthstrip(session_dir, "T1", overwrite=force, synthstrip_cmd=synthstrip_cmd)
    _, status2 = run_native_synthstrip(session_dir, "T2", overwrite=force, synthstrip_cmd=synthstrip_cmd)
    _, status3 = run_native_synthstrip(session_dir, "PD", overwrite=force, synthstrip_cmd=synthstrip_cmd)

    statuses = [status1, status2, status3]
    if any(status == "failed" for status in statuses):
        print_done_or_skipped("failed")
    elif any(status == "done" for status in statuses):
        print_done_or_skipped("done")
    elif any(status == "missing_command" for status in statuses):
        print_done_or_skipped("missing_command")
    elif all(status == "skipped" for status in statuses):
        print_done_or_skipped("skipped")
    elif all(status == "missing" for status in statuses):
        print_done_or_skipped("missing")
    elif any(status == "skipped" for status in statuses):
        print_done_or_skipped("skipped")
    else:
        print_done_or_skipped("missing")

    link_t1_synthstrip_files_to_t1_space(session_dir)
    step += 1

    print(f"  ({step}/{total_steps}): Preparing T1 space / registering PD/T2 ({flirt_cmd})... ", end="", flush=True)
    _, status = register_session_to_t1_space(
        session_dir=session_dir,
        overwrite=force,
        flirt_cmd=flirt_cmd,
    )

    print_done_or_skipped(status)
    step += 1

    if run_first_segmentation:
        print(f"  ({step}/{total_steps}): Running FSL FIRST ({first_cmd})... ", end="", flush=True)

        input_image = session_dir / "t1_space" / "segmentation" / "synthstrip" / "T1_brainmask.nii.gz"
        output_dir = session_dir / "t1_space" / "segmentation" / "fslfirst"

        _, status = run_fsl_first(
            input_image=input_image,
            output_dir=output_dir,
            first_cmd=first_cmd,
            overwrite=force,
            brain_extracted=True,
        )

        erode_label_segmentation(
            segmentation_file=output_dir / "first_all_fast_firstseg.nii.gz",
            output_file=output_dir / "first_all_fast_firstseg_eroded.nii.gz",
            iterations=1,
            overwrite=force,
        )

        print_done_or_skipped(status)
        step += 1

    if run_dbsegment_segmentation:
        print(f"  ({step}/{total_steps}): Running DBSegment ({dbsegment_cmd})... ", end="", flush=True)

        dbsegment_model_path = output_root / "group_analysis" / "DBSegment"
        dbsegment_model_path.mkdir(parents=True, exist_ok=True)

        _, status = run_dbsegment(
            input_image=session_dir / "t1_space" / "segmentation" / "synthstrip" / "T1_brainmask.nii.gz",
            output_dir=session_dir / "t1_space" / "segmentation" / "dbsegment",
            model_path=dbsegment_model_path,
            dbsegment_cmd=dbsegment_cmd,
            overwrite=force,
            use_cuda=dbsegment_use_cuda,
        )

        print_done_or_skipped(status)
        step += 1

    if run_synthseg_segmentation:
        print(f"  ({step}/{total_steps}): Running SynthSeg ({synthseg_cmd})... ", end="", flush=True)

        _, status = run_synthseg(
            input_image=session_dir / "t1_space" / "T1.nii.gz",
            output_dir=session_dir / "t1_space" / "segmentation" / "synthseg",
            synthseg_cmd=synthseg_cmd,
            overwrite=force,
        )

        print_done_or_skipped(status)
        step += 1

    if run_bias_correction:
        print(f"  ({step}/{total_steps}): Running polynomial bias correction... ", end="", flush=True)

        _, status = run_t1_space_bias_correction(
            session_dir=session_dir,
            overwrite=force or force_bias_correction,
            degree=2,
        )

        print_done_or_skipped(status)
        step += 1

    if run_freesurfer_segmentation:
        print(f"  ({step}/{total_steps}): Running FreeSurfer ({freesurfer_cmd})... ", end="", flush=True)

        reference_t1 = session_dir / "t1_space" / "T1.nii.gz"
        subjects_dir = output_root / "group_analysis" / "FreeSurfer"
        freesurfer_subject_id = f"{subject_id}_{session_id}"

        freesurfer_subject_dir, freesurfer_status = run_freesurfer(
            input_image=reference_t1,
            subjects_dir=subjects_dir,
            subject_id=freesurfer_subject_id,
            recon_all_cmd=freesurfer_cmd,
            overwrite=force,
        )

        status = freesurfer_status

        if freesurfer_subject_dir is not None:
            freesurfer_mri_link = link_freesurfer_to_session(
                freesurfer_subject_dir=freesurfer_subject_dir,
                session_dir=session_dir,
            )

            if freesurfer_mri_link is not None:
                _, export_status = export_all_freesurfer_mgz_to_orig_space(
                    freesurfer_mri_dir=freesurfer_mri_link,
                    reference_t1=reference_t1,
                    output_dir=freesurfer_mri_link / "t1_space_outputs",
                    mri_vol2vol_cmd=mri_vol2vol_cmd,
                    overwrite=force,
                )
                if export_status in {"failed", "missing_command"}:
                    status = export_status

        print_done_or_skipped(status)

        step += 1

    print(f" [DONE ] {subject_id} / {session_id}")
    print(f"  Session dir: {session_dir}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Run session-level preprocessing for one PPMI session."
    )
    parser.add_argument("output_root")
    parser.add_argument("subject_id")
    parser.add_argument("session_id")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--skip-first", action="store_true")
    parser.add_argument("--skip-synthseg", action="store_true")
    parser.add_argument("--skip-freesurfer", action="store_true")
    parser.add_argument("--skip-dbsegment", action="store_true")
    parser.add_argument("--skip-bias-correction", action="store_true")
    parser.add_argument(
        "--force-bias-correction",
        action="store_true",
        help="Recreate only the polynomial bias-correction outputs.",
    )

    parser.add_argument("--synthstrip-cmd", default="mri_synthstrip")
    parser.add_argument("--flirt-cmd", default="flirt")
    parser.add_argument("--first-cmd", default="run_first_all")
    parser.add_argument("--synthseg-cmd", default="mri_synthseg")

    parser.add_argument("--dbsegment-cmd", default="DBSegment")
    parser.add_argument(
        "--dbsegment-cpu",
        action="store_true",
        help="Run DBSegment with CUDA disabled by setting CUDA_VISIBLE_DEVICES=''.",
    )

    parser.add_argument("--freesurfer-cmd", default="recon-all")
    parser.add_argument("--mri-vol2vol-cmd", default="mri_vol2vol")

    args = parser.parse_args()

    run_session_pipeline(
        output_root=args.output_root,
        subject_id=args.subject_id,
        session_id=args.session_id,
        force=args.force,
        synthstrip_cmd=args.synthstrip_cmd,
        flirt_cmd=args.flirt_cmd,
        first_cmd=args.first_cmd,
        synthseg_cmd=args.synthseg_cmd,
        freesurfer_cmd=args.freesurfer_cmd,
        mri_vol2vol_cmd=args.mri_vol2vol_cmd,
        run_first_segmentation=not args.skip_first,
        run_synthseg_segmentation=not args.skip_synthseg,
        run_freesurfer_segmentation=not args.skip_freesurfer,

        dbsegment_cmd=args.dbsegment_cmd,
        dbsegment_use_cuda=not args.dbsegment_cpu,
        run_dbsegment_segmentation=not args.skip_dbsegment,
        run_bias_correction=not args.skip_bias_correction,
        force_bias_correction=args.force_bias_correction,
    )


if __name__ == "__main__":
    main()
