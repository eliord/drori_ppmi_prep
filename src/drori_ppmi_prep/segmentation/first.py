from pathlib import Path
import shlex
import shutil
import subprocess

import nibabel as nib


def is_valid_first_segmentation(path):
    path = Path(path)
    if not path.exists():
        return False

    try:
        return len(nib.load(str(path)).shape) == 3
    except Exception:
        return False


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
    if is_valid_first_segmentation(expected_output) and not overwrite:
        return output_dir, "skipped"

    if output_dir.exists() and (overwrite or expected_output.exists()):
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

    (output_dir / "fsl_first_command.txt").write_text(shlex.join(cmd) + "\n")
    with (output_dir / "fsl_first_stdout.log").open("w") as stdout_f:
        with (output_dir / "fsl_first_stderr.log").open("w") as stderr_f:
            result = subprocess.run(
                cmd,
                text=True,
                stdout=stdout_f,
                stderr=stderr_f,
            )

    if result.returncode != 0:
        return None, "failed"

    if is_valid_first_segmentation(expected_output):
        return output_dir, "done"

    return None, "failed"
