import argparse

from drori_ppmi_prep.segmentation.utils import erode_label_segmentation


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Erode a label segmentation using the MATLAB strel('sphere', 1) "
            "6-neighbor structuring element."
        )
    )
    parser.add_argument("--segmentation", required=True, help="Input label NIfTI.")
    parser.add_argument("--output", required=True, help="Output eroded label NIfTI.")
    parser.add_argument(
        "--label",
        dest="labels",
        type=int,
        action="append",
        help=(
            "Label to erode. Can be repeated. Defaults to all nonzero labels."
        ),
    )
    parser.add_argument("--iterations", type=int, default=1)
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()
    output = erode_label_segmentation(
        segmentation_file=args.segmentation,
        output_file=args.output,
        labels=args.labels,
        iterations=args.iterations,
        overwrite=args.overwrite,
    )

    if output is None:
        print("FAILED")
        return 1

    print(f"Eroded segmentation: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
