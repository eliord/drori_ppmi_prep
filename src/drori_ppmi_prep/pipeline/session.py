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
from drori_ppmi_prep.segmentation.massp import (
    AHEAD_TEMPLATE_ARTICLE_ID,
    DEFAULT_MASSP_COHORT,
    DEFAULT_MASSP_VERSION,
    MASSP_COHORT_CHOICES,
    MASSP_VERSION_CHOICES,
    default_template_filename_for_massp,
    get_massp_resource,
    massp_cache_subdir,
    resolve_massp_resource,
    run_massp_atlas_segmentation,
)
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


def _tail_nonempty_lines(path, max_lines=5):
    path = Path(path)
    if not path.exists() or not path.is_file():
        return []
    try:
        lines = [line.strip() for line in path.read_text(errors="replace").splitlines()]
    except OSError:
        return []
    lines = [line for line in lines if line]
    return lines[-max_lines:]


def failure_details(log_paths=(), expected_paths=()):
    lines = []
    missing_outputs = [Path(path) for path in expected_paths if not Path(path).exists()]
    for path in missing_outputs[:5]:
        lines.append(f"Missing expected output: {path}")
    for path in [Path(path) for path in log_paths]:
        if path.exists():
            lines.append(f"Log: {path}")
            tail = _tail_nonempty_lines(path)
            if tail:
                lines.append(f"Last log line: {tail[-1]}")
    return lines


def print_done_or_skipped(status, details=None):
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
        for line in details or []:
            print(f"      {line}")


def run_session_pipeline(
    output_root,
    subject_id,
    session_id,
    force=False,
    synthstrip_cmd="mri_synthstrip",
    flirt_cmd="flirt",
    first_cmd="run_first_all",
    synthseg_cmd="mri_synthseg",
    ants_registration_cmd="antsRegistration",
    ants_apply_cmd="antsApplyTransforms",
    freesurfer_cmd="recon-all",
    mri_vol2vol_cmd="mri_vol2vol",
    dbsegment_cmd="DBSegment",
    massp_atlas_path=None,
    massp_template_path=None,
    massp_version=DEFAULT_MASSP_VERSION,
    massp_cohort=DEFAULT_MASSP_COHORT,
    massp_download=True,
    dbsegment_model_path=None,
    dbsegment_use_cuda=True,
    run_first_segmentation=True,
    run_synthseg_segmentation=True,
    run_massp_segmentation=True,
    run_freesurfer_segmentation=True,
    run_dbsegment_segmentation=True,
    run_bias_correction=True,
    force_bias_correction=False,
    restart_incomplete_freesurfer=False,
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
            + int(run_massp_segmentation)
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

        eroded_output = erode_label_segmentation(
            segmentation_file=output_dir / "first_all_fast_firstseg.nii.gz",
            output_file=output_dir / "first_all_fast_firstseg_eroded.nii.gz",
            iterations=1,
            overwrite=force,
        )
        if eroded_output is None:
            status = "failed"

        print_done_or_skipped(
            status,
            failure_details(
                log_paths=[
                    output_dir / "fsl_first_command.txt",
                    output_dir / "fsl_first_stdout.log",
                    output_dir / "fsl_first_stderr.log",
                ],
                expected_paths=[
                    output_dir / "first_all_fast_firstseg.nii.gz",
                    output_dir / "first_all_fast_firstseg_eroded.nii.gz",
                ],
            ),
        )
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

        print_done_or_skipped(
            status,
            failure_details(
                log_paths=[
                    session_dir / "t1_space" / "segmentation" / "dbsegment" / "dbsegment_command.txt",
                    session_dir / "t1_space" / "segmentation" / "dbsegment" / "dbsegment_stdout.log",
                    session_dir / "t1_space" / "segmentation" / "dbsegment" / "dbsegment_stderr.log",
                ],
                expected_paths=[
                    session_dir / "t1_space" / "segmentation" / "dbsegment" / "T1.nii.gz",
                    session_dir / "t1_space" / "segmentation" / "dbsegment" / "derivatives" / "GP_SN_seg.nii.gz",
                ],
            ),
        )
        step += 1

    if run_synthseg_segmentation:
        print(f"  ({step}/{total_steps}): Running SynthSeg ({synthseg_cmd})... ", end="", flush=True)

        _, status = run_synthseg(
            input_image=session_dir / "t1_space" / "T1.nii.gz",
            output_dir=session_dir / "t1_space" / "segmentation" / "synthseg",
            synthseg_cmd=synthseg_cmd,
            overwrite=force,
        )

        print_done_or_skipped(
            status,
            failure_details(
                log_paths=[
                    session_dir / "t1_space" / "segmentation" / "synthseg" / "synthseg_command.txt",
                    session_dir / "t1_space" / "segmentation" / "synthseg" / "synthseg_stdout.log",
                    session_dir / "t1_space" / "segmentation" / "synthseg" / "synthseg_stderr.log",
                ],
                expected_paths=[
                    session_dir / "t1_space" / "segmentation" / "synthseg" / "synthseg.nii.gz",
                ],
            ),
        )
        step += 1

    if run_massp_segmentation:
        print(f"  ({step}/{total_steps}): Running MASSP atlas registration ({ants_registration_cmd})... ", end="", flush=True)

        massp_resource = get_massp_resource(massp_version, massp_cohort)
        template_filename = default_template_filename_for_massp(massp_version)
        massp_cache_dir = (
            output_root
            / "group_analysis"
            / "atlases"
            / massp_cache_subdir(massp_version, massp_cohort)
        )
        try:
            resolved_massp_template = resolve_massp_resource(
                massp_template_path,
                massp_cache_dir,
                AHEAD_TEMPLATE_ARTICLE_ID,
                template_filename,
                allow_download=massp_download,
            )
            resolved_massp_atlas = resolve_massp_resource(
                massp_atlas_path,
                massp_cache_dir,
                massp_resource.article_id,
                massp_resource.filename,
                allow_download=massp_download,
            )
        except Exception:
            resolved_massp_template = None
            resolved_massp_atlas = None

        _, status = run_massp_atlas_segmentation(
            target_image=session_dir / "t1_space" / "segmentation" / "synthstrip" / "T1_brainmask.nii.gz",
            output_dir=session_dir / "t1_space" / "segmentation" / "massp" / "ahead2sub_ants",
            atlas_path=resolved_massp_atlas,
            template_path=resolved_massp_template,
            massp_resource=massp_resource,
            ants_registration_cmd=ants_registration_cmd,
            ants_apply_cmd=ants_apply_cmd,
            overwrite=force,
        )

        massp_output_dir = session_dir / "t1_space" / "segmentation" / "massp" / "ahead2sub_ants"
        print_done_or_skipped(
            status,
            failure_details(
                log_paths=[
                    massp_output_dir / "massp_registration_command.txt",
                    massp_output_dir / "massp_registration_stdout.log",
                    massp_output_dir / "massp_registration_stderr.log",
                    massp_output_dir / "massp_apply_command.txt",
                    massp_output_dir / "massp_apply_stdout.log",
                    massp_output_dir / "massp_apply_stderr.log",
                ],
            ),
        )
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
            restart_incomplete=restart_incomplete_freesurfer,
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
                if export_status not in {"done", "skipped"}:
                    status = export_status

        freesurfer_logs = [
            subjects_dir / f"{freesurfer_subject_id}_recon-all_command.txt",
            subjects_dir / f"{freesurfer_subject_id}_recon-all_stdout.log",
            subjects_dir / f"{freesurfer_subject_id}_recon-all_stderr.log",
            subjects_dir / freesurfer_subject_id / "scripts" / "recon-all.log",
            subjects_dir / freesurfer_subject_id / "scripts" / "recon-all.error",
        ]
        freesurfer_expected = [
            subjects_dir / freesurfer_subject_id / "mri" / "aparc+aseg.mgz",
            subjects_dir / freesurfer_subject_id / "mri" / "aparc.DKTatlas+aseg.mgz",
            session_dir / "t1_space" / "segmentation" / "freesurfer" / "t1_space_outputs" / "aparc+aseg.nii.gz",
            session_dir / "t1_space" / "segmentation" / "freesurfer" / "t1_space_outputs" / "aparc.DKTatlas+aseg.nii.gz",
        ]
        print_done_or_skipped(
            status,
            failure_details(log_paths=freesurfer_logs, expected_paths=freesurfer_expected),
        )

        step += 1

    if run_bias_correction:
        print(
            f"  ({step}/{total_steps}): Running polynomial bias correction (mri-unbias)... ",
            end="",
            flush=True,
        )

        _, status = run_t1_space_bias_correction(
            session_dir=session_dir,
            overwrite=force or force_bias_correction,
            degree=2,
        )

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
    parser.add_argument("--skip-massp", action="store_true")
    parser.add_argument("--skip-freesurfer", action="store_true")
    parser.add_argument("--skip-dbsegment", action="store_true")
    parser.add_argument("--skip-bias-correction", action="store_true")
    parser.add_argument(
        "--restart-incomplete-freesurfer",
        action="store_true",
        help="Delete and restart only incomplete FreeSurfer subject directories.",
    )
    parser.add_argument(
        "--force-bias-correction",
        action="store_true",
        help="Recreate only the polynomial bias-correction outputs.",
    )

    parser.add_argument("--synthstrip-cmd", default="mri_synthstrip")
    parser.add_argument("--flirt-cmd", default="flirt")
    parser.add_argument("--first-cmd", default="run_first_all")
    parser.add_argument("--synthseg-cmd", default="mri_synthseg")
    parser.add_argument("--ants-registration-cmd", default="antsRegistration")
    parser.add_argument("--ants-apply-cmd", default="antsApplyTransforms")
    parser.add_argument("--massp-atlas", default=None)
    parser.add_argument("--massp-template", default=None)
    parser.add_argument(
        "--massp-cohort",
        choices=MASSP_COHORT_CHOICES,
        default=DEFAULT_MASSP_COHORT,
        help=f"MASSP atlas age cohort. Default: {DEFAULT_MASSP_COHORT}.",
    )
    parser.add_argument(
        "--massp-version",
        choices=MASSP_VERSION_CHOICES,
        default=DEFAULT_MASSP_VERSION,
        help=f"MASSP atlas version. Default: {DEFAULT_MASSP_VERSION}.",
    )
    parser.add_argument(
        "--massp-no-download",
        action="store_true",
        help="Do not automatically download the MASSP atlas or AHEAD template if missing.",
    )

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
        ants_registration_cmd=args.ants_registration_cmd,
        ants_apply_cmd=args.ants_apply_cmd,
        freesurfer_cmd=args.freesurfer_cmd,
        mri_vol2vol_cmd=args.mri_vol2vol_cmd,
        massp_atlas_path=args.massp_atlas,
        massp_template_path=args.massp_template,
        massp_version=args.massp_version,
        massp_cohort=args.massp_cohort,
        massp_download=not args.massp_no_download,
        run_first_segmentation=not args.skip_first,
        run_synthseg_segmentation=not args.skip_synthseg,
        run_massp_segmentation=not args.skip_massp,
        run_freesurfer_segmentation=not args.skip_freesurfer,

        dbsegment_cmd=args.dbsegment_cmd,
        dbsegment_use_cuda=not args.dbsegment_cpu,
        run_dbsegment_segmentation=not args.skip_dbsegment,
        run_bias_correction=not args.skip_bias_correction,
        force_bias_correction=args.force_bias_correction,
        restart_incomplete_freesurfer=args.restart_incomplete_freesurfer,
    )


if __name__ == "__main__":
    main()
