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


def main():
    parser = argparse.ArgumentParser(
        description="Run MASSP atlas registration for a single target image.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Default ANTs workflow:
  antsRegistration:
    Rigid + Affine + SyN registration of the AHEAD R1 template to --target-image.
    Uses MI for rigid/affine stages and CC for the SyN stage.

  antsApplyTransforms:
    Applies the resulting warp and affine transforms to the MASSP atlas with
    NearestNeighbor interpolation.

Use --ants-registration-cmd and --ants-apply-cmd to point to non-default ANTs
executables or wrappers.
""",
    )
    parser.add_argument(
        "--target-image",
        required=True,
        help="Subject/reference image to register the MASSP atlas into.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help=(
            "MASSP output parent directory. The command writes outputs under "
            "OUTPUT_DIR/ahead2sub_ants."
        ),
    )
    parser.add_argument(
        "--cache-dir",
        default=None,
        help=(
            "Directory for cached MASSP resources. Defaults to "
            "OUTPUT_DIR/atlases/<selected_massp_resource>."
        ),
    )
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
    parser.add_argument("--atlas", default=None, help="Path to MASSP atlas NIfTI.")
    parser.add_argument("--template", default=None, help="Path to AHEAD R1 template NIfTI.")
    parser.add_argument(
        "--no-download",
        action="store_true",
        help="Require --atlas and --template or existing cache files; do not download.",
    )
    parser.add_argument(
        "--ants-registration-cmd",
        default="antsRegistration",
        help="ANTs registration executable. Default: antsRegistration.",
    )
    parser.add_argument(
        "--ants-apply-cmd",
        default="antsApplyTransforms",
        help="ANTs transform-application executable. Default: antsApplyTransforms.",
    )
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    final_output_dir = output_dir / "ahead2sub_ants"
    massp_resource = get_massp_resource(args.massp_version, args.massp_cohort)
    template_filename = default_template_filename_for_massp(args.massp_version)
    cache_dir = (
        Path(args.cache_dir)
        if args.cache_dir is not None
        else output_dir / "atlases" / massp_cache_subdir(args.massp_version, args.massp_cohort)
    )

    resolved_template = resolve_massp_resource(
        args.template,
        cache_dir,
        AHEAD_TEMPLATE_ARTICLE_ID,
        template_filename,
        allow_download=not args.no_download,
    )
    resolved_atlas = resolve_massp_resource(
        args.atlas,
        cache_dir,
        massp_resource.article_id,
        massp_resource.filename,
        allow_download=not args.no_download,
    )

    if resolved_template is None:
        raise FileNotFoundError(
            "AHEAD template not found. Provide --template or allow download."
        )
    if resolved_atlas is None:
        raise FileNotFoundError(
            "MASSP atlas not found. Provide --atlas or allow download."
        )

    output_file, status = run_massp_atlas_segmentation(
        target_image=args.target_image,
        output_dir=final_output_dir,
        atlas_path=resolved_atlas,
        template_path=resolved_template,
        massp_resource=massp_resource,
        ants_registration_cmd=args.ants_registration_cmd,
        ants_apply_cmd=args.ants_apply_cmd,
        overwrite=args.overwrite,
    )

    print(f"MASSP status: {status}")
    print(f"MASSP atlas : {massp_resource.version} / {massp_resource.cohort}")
    print(f"Output dir  : {final_output_dir}")
    if output_file is not None:
        print(f"Atlas output: {output_file}")

    return 0 if status in {"done", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
