import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import contextlib
import os

from drori_ppmi_prep.cli.check_outputs import (
    build_native_source_availability,
    check_analysis_outputs,
    print_summary,
    summarize,
)
from drori_ppmi_prep.pipeline.infrastructure import run_build_infrastructure
from drori_ppmi_prep.pipeline.paths import validate_output_root_path
from drori_ppmi_prep.pipeline.session import run_session_pipeline


def print_banner():
    print("=" * 70)
    print("DRORI PPMI MRI PREPROCESSING PIPELINE (2026)")
    print("=" * 70)
    print()


def load_ppmi_config(output_root):
    output_root = validate_output_root_path(output_root)
    config_path = output_root / "ppmi_config.json"

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    return json.loads(config_path.read_text())


def infrastructure_outputs_exist(output_root):
    output_root = validate_output_root_path(output_root)
    required_paths = [
        output_root / "ppmi_config.json",
        output_root / "ppmi_metadata.csv",
        output_root / "PPMI_nifti",
        output_root / "PPMI_analysis",
    ]
    return all(path.exists() for path in required_paths)


def run_one_session(job):
    (
        output_root,
        subject_id,
        session_id,
        force,
        synthstrip_cmd,
        flirt_cmd,
        first_cmd,
        synthseg_cmd,
        freesurfer_cmd,
        mri_vol2vol_cmd,
        dbsegment_cmd,
        dbsegment_use_cuda,
        run_first,
        run_synthseg,
        run_freesurfer,
        run_dbsegment,
        run_bias_correction,
        quiet,
    ) = job

    def _run():
        run_session_pipeline(
            output_root=output_root,
            subject_id=subject_id,
            session_id=session_id,
            force=force,
            synthstrip_cmd=synthstrip_cmd,
            flirt_cmd=flirt_cmd,
            first_cmd=first_cmd,
            synthseg_cmd=synthseg_cmd,
            freesurfer_cmd=freesurfer_cmd,
            mri_vol2vol_cmd=mri_vol2vol_cmd,
            dbsegment_cmd=dbsegment_cmd,
            dbsegment_use_cuda=dbsegment_use_cuda,
            run_first_segmentation=run_first,
            run_synthseg_segmentation=run_synthseg,
            run_freesurfer_segmentation=run_freesurfer,
            run_dbsegment_segmentation=run_dbsegment,
            run_bias_correction=run_bias_correction,
        )

    if quiet:
        print(f" [START] {subject_id} / {session_id}", flush=True)
        with open(os.devnull, "w") as devnull:
            with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
                _run()
        print(f" [DONE ] {subject_id} / {session_id}", flush=True)

    else:
        _run()

    return subject_id, session_id


def main():
    print_banner()
    parser = argparse.ArgumentParser(
        description=(
            "Run the full PPMI pipeline: build infrastructure, then run "
            "session-level preprocessing for all sessions."
        )
    )

    parser.add_argument("ppmi_root")
    parser.add_argument("idaSearch_dir")
    parser.add_argument("output_root")

    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--skip-infrastructure-if-exists",
        action="store_true",
        help=(
            "Skip metadata, DICOM conversion, and analysis-directory building "
            "when the expected infrastructure outputs already exist."
        ),
    )

    parser.add_argument("--dcm2niix-cmd", default="dcm2niix")
    parser.add_argument("--synthstrip-cmd", default="mri_synthstrip")
    parser.add_argument("--flirt-cmd", default="flirt")
    parser.add_argument("--first-cmd", default="run_first_all")
    parser.add_argument("--synthseg-cmd", default="mri_synthseg")
    parser.add_argument("--dbsegment-cmd", default="DBSegment")
    parser.add_argument(
        "--dbsegment-cpu",
        action="store_true",
        help=(
            "Run DBSegment with CUDA disabled. This is applied automatically "
            "when --parallel is used."
        ),
    )
    parser.add_argument("--freesurfer-cmd", default="recon-all")
    parser.add_argument("--mri-vol2vol-cmd", default="mri_vol2vol")
    parser.add_argument("--file-pattern", default="*.csv")

    parser.add_argument("--skip-freesurfer", action="store_true")
    parser.add_argument("--skip-dbsegment", action="store_true")
    parser.add_argument("--skip-first", action="store_true")
    parser.add_argument("--skip-synthseg", action="store_true")
    parser.add_argument("--skip-bias-correction", action="store_true")

    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run session-level preprocessing in parallel.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=None,
        help="Number of parallel workers. Defaults to the number of CPU cores.",
    )

    args = parser.parse_args()

    output_root = Path(args.output_root)

    if args.skip_infrastructure_if_exists and infrastructure_outputs_exist(output_root):
        print("-" * 70)
        print("Skipping dataset infrastructure build: existing outputs found.")
        print("-" * 70)
    else:
        run_build_infrastructure(
            ppmi_root=args.ppmi_root,
            idaSearch_dir=args.idaSearch_dir,
            output_root=args.output_root,
            file_pattern=args.file_pattern,
            dcm2niix_cmd=args.dcm2niix_cmd,
            force=args.force,
            parallel=args.parallel,
            max_workers=args.max_workers,
        )

    print()
    print("-" * 70)
    print("Running session-level preprocessing for all sessions...")
    print("-" * 70)

    config = load_ppmi_config(output_root)
    analysis_root = Path(config["analysis_root"])

    jobs = []

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            jobs.append(
                (
                    output_root,
                    subject_dir.name,
                    session_dir.name,
                    args.force,
                    args.synthstrip_cmd,
                    args.flirt_cmd,
                    args.first_cmd,
                    args.synthseg_cmd,
                    args.freesurfer_cmd,
                    args.mri_vol2vol_cmd,
                    args.dbsegment_cmd,
                    not (args.parallel or args.dbsegment_cpu),
                    not args.skip_first,
                    not args.skip_synthseg,
                    not args.skip_freesurfer,
                    not args.skip_dbsegment,
                    not args.skip_bias_correction,
                    args.parallel
                )
            )

    print(f"Found {len(jobs)} sessions.")
    print(f"Parallel mode: {args.parallel}")

    if args.parallel:
        print(f"Max workers: {args.max_workers or 'default'}")

    print()

    processed_sessions = 0

    if args.parallel:
        with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [executor.submit(run_one_session, job) for job in jobs]

            for future in as_completed(futures):
                subject_id, session_id = future.result()
                processed_sessions += 1
    else:
        for job in jobs:
            subject_id, session_id = run_one_session(job)
            processed_sessions += 1

    print()
    print("=" * 70)
    print("PIPELINE FINISHED")
    print("=" * 70)
    print(f"Output root       : {output_root}")
    print(f"Processed sessions: {processed_sessions}")
    print()

    print("-" * 70)
    print("Checking analysis outputs...")
    print("-" * 70)
    native_source_availability = build_native_source_availability(
        config["metadata_csv"],
        config["nifti_root"],
    )
    rows = check_analysis_outputs(analysis_root, native_source_availability)
    summary = summarize(rows)
    print_summary(analysis_root, rows, summary)
    print()


if __name__ == "__main__":
    main()
