import shutil
import subprocess
import tempfile
from pathlib import Path


def run_dbsegment(
    input_image,
    output_dir,
    model_path=None,
    dbsegment_cmd="DBSegment",
    overwrite=False,
):
    input_image = Path(input_image)
    output_dir = Path(output_dir)

    if not input_image.exists():
        return None, "missing"

    output_file = output_dir / "T1.nii.gz"

    if output_file.exists() and not overwrite:
        return output_file, "skipped"

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="dbsegment_") as tmpdir:
        tmpdir = Path(tmpdir)
        tmpfile = tmpdir / "T1.nii.gz"

        shutil.copy2(input_image, tmpfile)

        cmd = [
            dbsegment_cmd,
            "-i",
            str(tmpdir),
            "-o",
            str(output_dir),
        ]

        if model_path is not None:
            cmd.extend(["-mp", str(Path(model_path))])

        result = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )

        if result.returncode != 0:
            return None, "failed"

        if output_file.exists():
            return output_file, "done"

    return output_file, "failed"
