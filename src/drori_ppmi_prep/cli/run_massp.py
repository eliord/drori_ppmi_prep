import argparse
from pathlib import Path

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


def run_massp_segmentations(
    analysis_root,
    output_root=None,
    atlas_path=None,
    template_path=None,
    massp_version=DEFAULT_MASSP_VERSION,
    massp_cohort=DEFAULT_MASSP_COHORT,
    allow_download=True,
    ants_registration_cmd="antsRegistration",
    ants_apply_cmd="antsApplyTransforms",
    overwrite=False,
):
    analysis_root = Path(analysis_root)
    output_root = Path(output_root) if output_root is not None else analysis_root.parent
    massp_resource = get_massp_resource(massp_version, massp_cohort)
    template_filename = default_template_filename_for_massp(massp_version)
    cache_dir = (
        output_root
        / "group_analysis"
        / "atlases"
        / massp_cache_subdir(massp_version, massp_cohort)
    )

    if not analysis_root.exists():
        raise FileNotFoundError(f"Analysis root not found: {analysis_root}")

    resolved_template = resolve_massp_resource(
        template_path,
        cache_dir,
        AHEAD_TEMPLATE_ARTICLE_ID,
        template_filename,
        allow_download=allow_download,
    )
    resolved_atlas = resolve_massp_resource(
        atlas_path,
        cache_dir,
        massp_resource.article_id,
        massp_resource.filename,
        allow_download=allow_download,
    )

    processed_sessions = 0
    skipped_sessions = 0
    failed_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            print(f"Running MASSP atlas registration for session: {session_dir}")
            _, status = run_massp_atlas_segmentation(
                target_image=session_dir / "t1_space/segmentation/synthstrip/T1_brainmask.nii.gz",
                output_dir=session_dir / "t1_space/segmentation/massp/ahead2sub_ants",
                atlas_path=resolved_atlas,
                template_path=resolved_template,
                massp_resource=massp_resource,
                ants_registration_cmd=ants_registration_cmd,
                ants_apply_cmd=ants_apply_cmd,
                overwrite=overwrite,
            )

            if status in {"done", "skipped"}:
                processed_sessions += 1
            elif status in {"missing", "missing_command"}:
                skipped_sessions += 1
            else:
                failed_sessions += 1

    print(
        "Done. "
        f"Processed {processed_sessions} sessions, "
        f"skipped {skipped_sessions} sessions, "
        f"failed {failed_sessions} sessions."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run MASSP atlas nonlinear registration in all analysis sessions."
    )
    parser.add_argument("analysis_root")
    parser.add_argument("--output-root", default=None)
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
    parser.add_argument("--massp-no-download", action="store_true")
    parser.add_argument("--ants-registration-cmd", default="antsRegistration")
    parser.add_argument("--ants-apply-cmd", default="antsApplyTransforms")
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()
    run_massp_segmentations(
        analysis_root=args.analysis_root,
        output_root=args.output_root,
        atlas_path=args.massp_atlas,
        template_path=args.massp_template,
        massp_version=args.massp_version,
        massp_cohort=args.massp_cohort,
        allow_download=not args.massp_no_download,
        ants_registration_cmd=args.ants_registration_cmd,
        ants_apply_cmd=args.ants_apply_cmd,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
