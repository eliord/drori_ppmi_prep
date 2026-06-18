import argparse

from drori_ppmi_prep.segmentation.utils import (
    create_label_mask,
    erode_label_segmentation,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a binary mask from selected labels in any label segmentation "
            "(for example FreeSurfer or SynthSeg white-matter labels)."
        )
    )
    parser.add_argument("--segmentation", required=True, help="Input label NIfTI.")
    parser.add_argument("--output", required=True, help="Output binary mask NIfTI.")
    parser.add_argument(
        "--label",
        dest="labels",
        type=int,
        action="append",
        required=True,
        help="Label to include in the mask. Can be repeated.",
    )
    parser.add_argument(
        "--erode",
        action="store_true",
        help="Erode the binary mask before writing the final output.",
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()
    output = create_label_mask(
        segmentation_file=args.segmentation,
        output_file=args.output,
        labels=args.labels,
        overwrite=args.overwrite,
    )

    if output is None:
        print("FAILED")
        return 1

    if args.erode:
        eroded_output = erode_label_segmentation(
            segmentation_file=output,
            output_file=output,
            labels=[1],
            iterations=args.iterations,
            overwrite=True,
        )
        if eroded_output is None:
            print("FAILED")
            return 1

    print(f"Label mask: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
