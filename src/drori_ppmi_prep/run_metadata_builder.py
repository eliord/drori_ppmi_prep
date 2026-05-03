import argparse
from pathlib import Path

from drori_ppmi_prep.metadata_builder import build_ppmi_metadata_csv
from drori_ppmi_prep.extend_metadata_from_dicom import enrich_metadata_with_dicom_info


def main():
    parser = argparse.ArgumentParser(
        description="Build PPMI metadata CSV and enrich it with DICOM information."
    )
    parser.add_argument(
        "idaSearch_dir",
        help="Directory containing the idaSearch CSV files from the ppmi download",
    )
    parser.add_argument(
        "ppmi_root",
        help="Root directory of the PPMI DICOM dataset",
    )
    parser.add_argument(
        "output_csv",
        help="Final output CSV path",
    )
    parser.add_argument(
        "--file-pattern",
        default="*.csv",
        help="Glob pattern for selecting input CSV files",
    )

    args = parser.parse_args()
    output_csv = Path(args.output_csv)

    print("Step 1/2: Building base metadata table from idaSearch CSV files...")
    print(f"  Input CSV directory: {args.idaSearch_dir}")
    print(f"  Output CSV: {output_csv}")

    # Step 1: build base metadata CSV
    build_ppmi_metadata_csv(
        input_dir=args.idaSearch_dir,
        output_csv=output_csv,
        file_pattern=args.file_pattern,
    )
    print("Step 1/2 complete.")
    print("Step 2/2: Enriching metadata from DICOM headers...")
    print("  This step may take a while for large datasets.")
    print(f"  PPMI root: {args.ppmi_root}")
    print(f"  Metadata CSV: {output_csv}")

    # Step 2: enrich metadata from DICOMs
    enrich_metadata_with_dicom_info(
        metadata_csv=output_csv,
        ppmi_root=args.ppmi_root,
        output_csv=output_csv,
    )

    print("Step 2/2 complete.")
    print(f"Done. Final metadata written to: {output_csv}")


if __name__ == "__main__":
    main()
