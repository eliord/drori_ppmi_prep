import argparse

from drori_ppmi_prep.conversion.dicom_to_nifti import convert_dicom_dir_to_nifti


def main():
    parser = argparse.ArgumentParser(
        description="Convert one DICOM directory to gzipped NIfTI using dcm2niix."
    )
    parser.add_argument("--dicom-dir", required=True, help="Input DICOM directory.")
    parser.add_argument("--output-dir", required=True, help="Output directory.")
    parser.add_argument(
        "--filename",
        required=True,
        help="Output filename stem passed to dcm2niix with -f.",
    )
    parser.add_argument("--dcm2niix-cmd", default="dcm2niix")
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()
    outputs, status = convert_dicom_dir_to_nifti(
        dicom_dir=args.dicom_dir,
        output_dir=args.output_dir,
        filename=args.filename,
        dcm2niix_path=args.dcm2niix_cmd,
        overwrite=args.overwrite,
    )

    print(f"DICOM conversion status: {status}")
    for output in outputs:
        print(f"Output: {output}")

    return 0 if status in {"done", "skipped"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
