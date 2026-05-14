from pathlib import Path
import shutil
import subprocess


def run_fsl_first(
    input_image,
    output_dir,
    first_cmd="run_first_all",
    overwrite=False,
    brain_extracted=False,
):
    input_image = Path(input_image)
    output_dir = Path(output_dir)

    if not input_image.exists():
        return None, "missing"

    if shutil.which(first_cmd) is None:
        return None, "missing_command"

    expected_output = output_dir / "first_all_fast_firstseg.nii.gz"
    if expected_output.exists() and not overwrite:
        return output_dir, "skipped"

    if output_dir.exists() and overwrite:
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    out_basename = output_dir / "first"

    cmd = [
        first_cmd,
        "-i", str(input_image),
        "-o", str(out_basename),
    ]

    if brain_extracted:
        cmd.append("-b")

    result = subprocess.run(
        cmd,
        text=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        return None, "failed"

    if expected_output.exists():
        return output_dir, "done"

    return None, "failed"
