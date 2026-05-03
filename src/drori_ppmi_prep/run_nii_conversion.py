import argparse

from drori_ppmi_prep.dicom_conversion import convert_ppmi_dicoms_to_nifti


def main():
    parser = argparse.ArgumentParser(
        description="Convert a PPMI DICOM dataset to NIfTI while preserving directory structure."
    )
    parser.add_argument(
        "input_root",
        help="Path to the PPMI directory",
    )
    parser.add_argument(
        "output_root",
        help="Path to the output directory for NIfTI files",
    )
    parser.add_argument(
        "--dcm2niix-path",
        default="dcm2niix",
        help="Path to the dcm2niix executable (default:dcm2niix)",
    )
    parser.add_argument(
        "--synthstrip-cmd",
        default="mri_synthstrip",
        help="SynthStrip executable name or full path (default:mri_synthstrip)",
    )
    parser.add_argument(
        "--flirt-cmd",
        default="flirt",
        help="FLIRT executable name or full path (default:flirt)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files",
    )

    args = parser.parse_args()

    convert_ppmi_dicoms_to_nifti(
        input_root=args.input_root,
        output_root=args.output_root,
        dcm2niix_path=args.dcm2niix_path,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
