import argparse
from pathlib import Path
import os
import shutil


def link_t1_synthstrip_files_to_t1_space(session_dir):
    session_dir = Path(session_dir)

    src_dir = session_dir / "segmentation_native" / "synthstrip"
    segmentation_dir = session_dir / "t1_space" / "segmentation"
    dst_dir = segmentation_dir / "synthstrip"

    segmentation_dir.mkdir(parents=True, exist_ok=True)

    if not src_dir.exists():
        if dst_dir.exists() or dst_dir.is_symlink():
            if dst_dir.is_symlink():
                dst_dir.unlink()
            else:
                shutil.rmtree(dst_dir)
        return

    if dst_dir.exists() or dst_dir.is_symlink():
        if dst_dir.is_symlink():
            dst_dir.unlink()
        else:
            shutil.rmtree(dst_dir)

    dst_dir.mkdir(parents=True, exist_ok=True)

    for src in src_dir.iterdir():
        if not src.is_file():
            continue

        if not (src.name.startswith("T1_") and src.name.endswith(".nii.gz")):
            continue

        dst = dst_dir / src.name
        os.symlink(src, dst)


def run_link_synthstrip_to_t1_space(analysis_root):
    analysis_root = Path(analysis_root)

    for subject_dir in analysis_root.iterdir():
        if not subject_dir.is_dir():
            continue

        for session_dir in subject_dir.iterdir():
            if not session_dir.is_dir():
                continue

            link_t1_synthstrip_files_to_t1_space(session_dir)


def main():
    parser = argparse.ArgumentParser(
        description="Create t1_space/segmentation and, when available, link T1 SynthStrip files into t1_space/segmentation/synthstrip."
    )
    parser.add_argument("analysis_root")
    args = parser.parse_args()

    run_link_synthstrip_to_t1_space(args.analysis_root)


if __name__ == "__main__":
    main()
