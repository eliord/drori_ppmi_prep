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
)


def main():
    parser = argparse.ArgumentParser(
        description="Download the AHEAD template and selected MASSP atlas."
    )
    parser.add_argument(
        "output_root",
        help="Pipeline output root where group_analysis/atlases/<selected_massp_resource> will be created.",
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

    args = parser.parse_args()
    massp_resource = get_massp_resource(args.massp_version, args.massp_cohort)
    template_filename = default_template_filename_for_massp(args.massp_version)
    cache_dir = (
        Path(args.output_root)
        / "group_analysis"
        / "atlases"
        / massp_cache_subdir(args.massp_version, args.massp_cohort)
    )

    template = resolve_massp_resource(
        None,
        cache_dir,
        AHEAD_TEMPLATE_ARTICLE_ID,
        template_filename,
        allow_download=True,
    )
    atlas = resolve_massp_resource(
        None,
        cache_dir,
        massp_resource.article_id,
        massp_resource.filename,
        allow_download=True,
    )

    if template is None or atlas is None:
        raise RuntimeError("Failed to download one or more MASSP resources from Figshare.")

    print(f"AHEAD template: {template}")
    print(f"MASSP atlas   : {atlas}")


if __name__ == "__main__":
    main()
