import shutil
import shlex
import os
import subprocess
import tempfile
from pathlib import Path


def remove_dbsegment_logs(output_dir):
    for log_file in [
        output_dir / "dbsegment_command.txt",
        output_dir / "dbsegment_stdout.log",
        output_dir / "dbsegment_stderr.log",
    ]:
        if log_file.exists():
            log_file.unlink()


def run_dbsegment(
    input_image,
    output_dir,
    model_path=None,
    dbsegment_cmd="DBSegment",
    overwrite=False,
    use_cuda=True,
):
    input_image = Path(input_image)
    output_dir = Path(output_dir)

    if not input_image.exists():
        return None, "missing"

    output_file = output_dir / "T1.nii.gz"

    if output_file.exists() and not overwrite:
        return output_file, "skipped"

    output_dir.mkdir(parents=True, exist_ok=True)
    command_log = output_dir / "dbsegment_command.txt"
    stdout_log = output_dir / "dbsegment_stdout.log"
    stderr_log = output_dir / "dbsegment_stderr.log"

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

        env = os.environ.copy()
        if not use_cuda:
            env["CUDA_VISIBLE_DEVICES"] = ""

        env_prefix = "CUDA_VISIBLE_DEVICES='' " if not use_cuda else ""
        command_log.write_text(env_prefix + shlex.join(cmd) + "\n")

        with stdout_log.open("w") as stdout_f, stderr_log.open("w") as stderr_f:
            try:
                result = subprocess.run(
                    cmd,
                    text=True,
                    stdout=stdout_f,
                    stderr=stderr_f,
                    env=env,
                )
            except Exception as e:
                stderr_f.write(f"{type(e).__name__}: {e}\n")
                return None, "failed"

        if output_file.exists():
            remove_dbsegment_logs(output_dir)
            return output_file, "done"

        if result.returncode != 0:
            return None, "failed"

    return output_file, "failed"
