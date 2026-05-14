import argparse

from drori_ppmi_prep.analysis.dataset_builder import build_analysis_dataset_from_metadata


def main():
    parser = argparse.ArgumentParser(
        description="Build an analysis dataset from a metadata CSV and a NIfTI root directory."
    )
    parser.add_argument(
        "metadata_csv",
        help="Path to the enriched metadata CSV",
    )
    parser.add_argument(
        "nifti_root",
        help="Root directory of the NIfTI dataset",
    )
    parser.add_argument(
        "output_root",
        help="Output root directory for the analysis dataset",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing symlinks if they already exist",
    )

    args = parser.parse_args()

    print("Step 1/1: Building analysis dataset from metadata and NIfTI files...")
    print(f"  Metadata CSV: {args.metadata_csv}")
    print(f"  NIfTI root: {args.nifti_root}")
    print(f"  Output root: {args.output_root}")

    summary_df = build_analysis_dataset_from_metadata(
        metadata_csv=args.metadata_csv,
        nifti_root=args.nifti_root,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )

    print("Step 1/1 complete.")
    print(f"Created analysis dataset for {len(summary_df)} rows.")


if __name__ == "__main__":
    main()
