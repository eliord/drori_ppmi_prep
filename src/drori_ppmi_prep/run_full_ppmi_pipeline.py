import argparse
from pathlib import Path

from drori_ppmi_prep.metadata_builder import build_ppmi_metadata_csv
from drori_ppmi_prep.extend_metadata_from_dicom import enrich_metadata_with_dicom_info
from drori_ppmi_prep.dicom_conversion import convert_ppmi_dicoms_to_nifti
from drori_ppmi_prep.build_analysis_dir import build_analysis_dataset_from_metadata
from drori_ppmi_prep.run_synthstrip_native import process_image
from drori_ppmi_prep.run_t1_space_registrations import run_t1_space_registrations


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Run the full PPMI pipeline: build metadata, convert DICOM to NIfTI, "
            "create the analysis dataset, and run SynthStrip."
        )
    )
    parser.add_argument(
        "ppmi_root",
        help="Root directory of the PPMI DICOM dataset",
    )
    parser.add_argument(
        "idaSearch_dir",
        help="Directory containing the idaSearch CSV files",
    )
    parser.add_argument(
        "output_root",
        help="Output root directory for all pipeline products",
    )
    parser.add_argument(
        "--file-pattern",
        default="*.csv",
        help="Glob pattern for selecting idaSearch CSV files",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force overwriting existing outputs where supported",
    )

    args = parser.parse_args()

    total_steps = 5

    ppmi_root = Path(args.ppmi_root)
    idaSearch_dir = Path(args.idaSearch_dir)
    output_root = Path(args.output_root)

    metadata_csv = output_root / "ppmi_metadata.csv"
    nifti_root = output_root / "PPMI_nifti"
    analysis_root = output_root / "PPMI_analysis"

    output_root.mkdir(parents=True, exist_ok=True)

    print(f"Step 1/{total_steps}: Building metadata CSV...")
    print(f"  idaSearch directory: {idaSearch_dir}")
    print(f"  Output metadata CSV: {metadata_csv}")

    build_ppmi_metadata_csv(
        input_dir=idaSearch_dir,
        output_csv=metadata_csv,
        file_pattern=args.file_pattern,
    )

    print("  Base metadata created.")
    print("  Enriching metadata from DICOM headers...")
    print("  This may take a while.")

    enrich_metadata_with_dicom_info(
        metadata_csv=metadata_csv,
        ppmi_root=ppmi_root,
        output_csv=metadata_csv,
    )

    print(f"Step 1/{total_steps} complete.\n")

    print(f"Step 2/{total_steps}: Converting DICOMs to NIfTI...")
    print(f"  DICOM root: {ppmi_root}")
    print(f"  NIfTI output root: {nifti_root}")
    print("  This may take a while.")

    convert_ppmi_dicoms_to_nifti(
        input_root=ppmi_root,
        output_root=nifti_root,
        overwrite=args.force,
    )

    print(f"Step 2/{total_steps} complete.\n")

    print(f"Step 3/{total_steps}: Building analysis dataset...")
    print(f"  Metadata CSV: {metadata_csv}")
    print(f"  NIfTI root: {nifti_root}")
    print(f"  Analysis output root: {analysis_root}")

    summary_df = build_analysis_dataset_from_metadata(
        metadata_csv=metadata_csv,
        nifti_root=nifti_root,
        output_root=analysis_root,
        overwrite=args.force,
    )

    print(f"Step 3/{total_steps} complete.\n")

    print(f"Step 4/{total_steps}: Running SynthStrip on analysis dataset...")
    print(f"  Analysis root: {analysis_root}")
    print("  This may take a while.")

    processed_sessions = 0

    for subject_dir in sorted(analysis_root.iterdir()):
        if not subject_dir.is_dir():
            continue

        for session_dir in sorted(subject_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            print(f"Processing SynthStrip for session: {session_dir}")
            process_image(session_dir, "T1", overwrite=args.force)
            process_image(session_dir, "T2", overwrite=args.force)
            process_image(session_dir, "PD", overwrite=args.force)
            processed_sessions += 1

    print(f"Step 4/{total_steps} complete.\n")

    print(f"Step 5/{total_steps}: Registering PD and T2 to T1 space...")
    print(f"  Analysis root: {analysis_root}")
    print("  This may take a while.")

    run_t1_space_registrations(
        analysis_root=analysis_root,
        overwrite=args.force,
    )

    print(f"Step 5/{total_steps} complete.\n")

    print("Pipeline finished successfully.")
    print(f"  Metadata CSV: {metadata_csv}")
    print(f"  NIfTI root: {nifti_root}")
    print(f"  Analysis root: {analysis_root}")
    print(f"  SynthStrip processed sessions: {processed_sessions}")
    print(f"  Processed rows: {len(summary_df)}")


if __name__ == "__main__":
    main()
