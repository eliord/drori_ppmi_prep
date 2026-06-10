from __future__ import annotations

import csv
import json
import re
import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

import numpy as np
import pandas as pd
from scipy.io import savemat


MRGRAD_VERSION = "v2.0.3"
MRGRAD_ARCHIVE_URL = (
    "https://github.com/MezerLab/mrGrad/archive/refs/tags/v2.0.3.zip"
)
PRESET_DIR = Path(__file__).parent / "mrgrad_presets"
DEFAULT_PRESETS = (
    "putamen-fslfirst-10seg",
    "gpe-dbsegment-5seg",
)
REQUIRED_CONFIG_KEYS = {
    "analysis_name",
    "segmentation",
    "maps",
    "roi",
    "roi_names",
    "n_segments",
    "segmenting_method",
    "max_change",
    "allow_missing",
    "output_mode",
    "output_name",
}


def resolve_dataset_paths(output_root):
    output_root = Path(output_root)
    config_path = output_root / "ppmi_config.json"

    if config_path.exists():
        config = json.loads(config_path.read_text())
        return Path(config["analysis_root"]), Path(config["metadata_csv"])

    return output_root / "PPMI_analysis", output_root / "ppmi_metadata.csv"


def download_mrgrad_release(cache_root):
    cache_root = Path(cache_root)
    toolbox_dir = cache_root / f"mrGrad-{MRGRAD_VERSION}"

    if (toolbox_dir / "mrGrad.m").exists():
        return toolbox_dir

    cache_root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="mrgrad_") as tmp:
        tmp = Path(tmp)
        archive_path = tmp / f"mrGrad-{MRGRAD_VERSION}.zip"

        with urlopen(MRGRAD_ARCHIVE_URL) as response, archive_path.open("wb") as f:
            shutil.copyfileobj(response, f)

        with zipfile.ZipFile(archive_path) as archive:
            for member in archive.infolist():
                member_path = Path(member.filename)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ValueError(f"Unsafe path in mrGrad archive: {member.filename}")
            archive.extractall(tmp / "extracted")

        extracted_dirs = [
            path
            for path in (tmp / "extracted").iterdir()
            if path.is_dir() and (path / "mrGrad.m").exists()
        ]
        if len(extracted_dirs) != 1:
            raise RuntimeError("Could not locate mrGrad.m in downloaded release archive.")

        if toolbox_dir.exists():
            shutil.rmtree(toolbox_dir)
        shutil.move(str(extracted_dirs[0]), toolbox_dir)

    return toolbox_dir


def resolve_mrgrad_dir(mrgrad_dir, cache_root, allow_download=True):
    if mrgrad_dir is not None:
        mrgrad_dir = Path(mrgrad_dir)
        return mrgrad_dir if (mrgrad_dir / "mrGrad.m").exists() else None

    cached_dir = Path(cache_root) / f"mrGrad-{MRGRAD_VERSION}"
    if (cached_dir / "mrGrad.m").exists():
        return cached_dir

    if not allow_download:
        return None

    return download_mrgrad_release(cache_root)


def list_mrgrad_presets():
    return sorted(path.stem for path in PRESET_DIR.glob("*.json"))


def load_mrgrad_preset(name):
    preset_path = PRESET_DIR / f"{name}.json"
    if not preset_path.exists():
        raise ValueError(
            f"Unknown mrGrad preset: {name}. Available presets: "
            f"{', '.join(list_mrgrad_presets())}"
        )
    return load_mrgrad_config(preset_path)


def load_mrgrad_config(path):
    path = Path(path)
    config = json.loads(path.read_text())
    validate_mrgrad_config(config)
    return config


def validate_mrgrad_config(config):
    missing_keys = REQUIRED_CONFIG_KEYS - set(config)
    if missing_keys:
        raise ValueError(f"Missing mrGrad config keys: {sorted(missing_keys)}")

    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config["analysis_name"]):
        raise ValueError("mrGrad analysis_name may contain only letters, digits, _, -, and .")

    segmentation = Path(config["segmentation"])
    if (
        not config["segmentation"]
        or segmentation.is_absolute()
        or ".." in segmentation.parts
    ):
        raise ValueError("mrGrad segmentation must be a session-relative path.")

    maps = config["maps"]
    if not maps:
        raise ValueError("mrGrad config requires at least one map.")
    for map_config in maps:
        if not {"name", "path", "unit"} <= set(map_config):
            raise ValueError("Each mrGrad map requires name, path, and unit.")
        map_path = Path(map_config["path"])
        if map_path.is_absolute() or ".." in map_path.parts:
            raise ValueError("mrGrad map paths must be session-relative.")

    roi = config["roi"]
    roi_names = config["roi_names"]
    max_change = config["max_change"]
    if not roi or len(roi) != len(roi_names) or len(roi) != len(max_change):
        raise ValueError("mrGrad roi, roi_names, and max_change must have equal lengths.")
    if any(len(row) != 3 for row in max_change):
        raise ValueError("Each mrGrad max_change row must have three entries.")
    if config["output_mode"] not in {"minimal", "default", "extended"}:
        raise ValueError("mrGrad output_mode must be minimal, default, or extended.")
    output_name = Path(config["output_name"])
    if output_name.name != config["output_name"] or output_name.suffix != ".mat":
        raise ValueError("mrGrad output_name must be a .mat filename without directories.")


def normalize_subject_id(value):
    value = str(value).strip()
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return value


def collect_mrgrad_sessions(analysis_root, metadata_csv, config):
    analysis_root = Path(analysis_root)
    metadata_csv = Path(metadata_csv)
    if not metadata_csv.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {metadata_csv}")

    metadata = pd.read_csv(
        metadata_csv,
        dtype={"RowID": str, "SubjectID": str, "SessionID": str, "AnalysisDir": str},
    )
    required_columns = {"RowID", "SubjectID", "SessionID"}
    if not required_columns <= set(metadata.columns):
        raise ValueError("Metadata CSV must contain RowID, SubjectID, and SessionID columns.")

    rows = []
    for _, metadata_row in metadata.iterrows():
        row_id = normalize_subject_id(metadata_row["RowID"])
        subject_id = normalize_subject_id(metadata_row["SubjectID"])
        session_id = str(metadata_row["SessionID"]).strip()
        if not session_id or session_id.lower() == "nan":
            session_id = f"missing-session_row-{row_id}"
        analysis_dir = str(metadata_row.get("AnalysisDir", "")).strip()
        if not analysis_dir or analysis_dir.lower() == "nan":
            analysis_dir = str(Path(subject_id) / session_id)
        session_dir = analysis_root / analysis_dir

        row = {
            "subject_id": subject_id,
            "session_id": session_id,
            "analysis_id": f"{subject_id}_{session_id}",
            "segmentation": str(session_dir / config["segmentation"]),
        }
        for map_config in config["maps"]:
            row[map_config["name"]] = str(session_dir / map_config["path"])
        rows.append(row)

    return rows


def write_manifest(rows, manifest_path):
    manifest_path = Path(manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    with manifest_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    return manifest_path


def write_mrgrad_input(rows, config, input_path):
    input_path = Path(input_path)
    input_path.parent.mkdir(parents=True, exist_ok=True)
    map_names = [map_config["name"] for map_config in config["maps"]]

    savemat(
        input_path,
        {
            "Data": {
                "seg_list": np.asarray(
                    [[row["segmentation"]] for row in rows],
                    dtype=object,
                ),
                "map_list": np.asarray(
                    [[row[name] for name in map_names] for row in rows],
                    dtype=object,
                ),
                "subject_ids": np.asarray(
                    [[row["analysis_id"]] for row in rows],
                    dtype=object,
                ),
            }
        },
    )
    return input_path


def matlab_quote(value):
    return str(value).replace("'", "''")


def matlab_vector(values):
    return "[" + " ".join(str(value) for value in values) + "]"


def matlab_matrix(rows):
    return "[" + "; ".join(" ".join(str(value) for value in row) for row in rows) + "]"


def matlab_cellstr(values):
    return "{" + ", ".join(f"'{matlab_quote(value)}'" for value in values) + "}"


def write_mrgrad_runner(input_path, output_dir, toolbox_dir, runner_path, config, parallel=False):
    runner_path = Path(runner_path)
    runner_path.parent.mkdir(parents=True, exist_ok=True)

    runner_path.write_text(
        f"""addpath(genpath('{matlab_quote(toolbox_dir)}'));
load('{matlab_quote(input_path)}', 'Data');
[RG, T] = mrGrad(Data, ...
    'ROI', {matlab_vector(config['roi'])}, ...
    'roi_names', {matlab_cellstr(config['roi_names'])}, ...
    'n_segments', {matlab_vector(config['n_segments']) if isinstance(config['n_segments'], list) else config['n_segments']}, ...
    'segmentingMethod', '{matlab_quote(config['segmenting_method'])}', ...
    'max_change', {matlab_matrix(config['max_change'])}, ...
    'parameter_names', {matlab_cellstr([item['name'] for item in config['maps']])}, ...
    'units', {matlab_cellstr([item['unit'] for item in config['maps']])}, ...
    'allow_missing', {str(bool(config['allow_missing'])).lower()}, ...
    'output_mode', '{matlab_quote(config['output_mode'])}', ...
    'output_dir', '{matlab_quote(output_dir)}', ...
    'output_name', '{matlab_quote(config['output_name'])}', ...
    'Parallel', {str(bool(parallel)).lower()});
"""
    )
    return runner_path


def mrgrad_outputs_exist(output_dir, config):
    output_dir = Path(output_dir)
    output_mat = output_dir / config["output_name"]
    output_csv = output_mat.with_suffix(".csv")

    if not output_mat.exists() or not output_csv.exists():
        return False
    if config["output_mode"] != "extended":
        return True

    return any((output_dir / "mrGradSeg").glob("**/*.nii.gz"))


def run_mrgrad_analysis(
    output_root,
    config,
    mrgrad_dir=None,
    matlab_cmd="matlab",
    allow_download=True,
    overwrite=False,
    parallel=False,
):
    validate_mrgrad_config(config)
    output_root = Path(output_root).resolve()
    analysis_root, metadata_csv = resolve_dataset_paths(output_root)
    group_dir = output_root / "group_analysis" / "mrGrad"
    output_dir = group_dir / config["analysis_name"]
    toolbox_cache = group_dir / "toolbox"
    output_mat = output_dir / config["output_name"]

    if mrgrad_outputs_exist(output_dir, config) and not overwrite:
        return output_mat, "skipped"
    if not analysis_root.exists():
        return None, "missing"

    try:
        rows = collect_mrgrad_sessions(analysis_root, metadata_csv, config)
    except (FileNotFoundError, ValueError):
        return None, "missing"
    if not rows:
        return None, "missing"

    try:
        resolved_mrgrad_dir = resolve_mrgrad_dir(
            mrgrad_dir,
            toolbox_cache,
            allow_download=allow_download,
        )
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile):
        return None, "missing"
    if resolved_mrgrad_dir is None:
        return None, "missing"
    if shutil.which(matlab_cmd) is None:
        return None, "missing_command"

    output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(rows, output_dir / "mrgrad_input_sessions.csv")
    input_path = write_mrgrad_input(rows, config, output_dir / "mrgrad_input.mat")
    runner_path = write_mrgrad_runner(
        input_path,
        output_dir,
        resolved_mrgrad_dir,
        output_dir / "run_mrgrad.m",
        config,
        parallel=parallel,
    )
    stdout_log = output_dir / "mrgrad_stdout.log"
    stderr_log = output_dir / "mrgrad_stderr.log"
    command_log = output_dir / "mrgrad_command.txt"

    cmd = [matlab_cmd, "-batch", f"run('{runner_path}')"]
    command_log.write_text(shlex.join(cmd) + "\n")

    with stdout_log.open("w") as stdout_f, stderr_log.open("w") as stderr_f:
        result = subprocess.run(cmd, text=True, stdout=stdout_f, stderr=stderr_f)

    if result.returncode == 0 and mrgrad_outputs_exist(output_dir, config):
        return output_mat, "done"

    return None, "failed"


def run_mrgrad_presets(output_root, preset_names=None, **kwargs):
    preset_names = preset_names or DEFAULT_PRESETS
    return [
        (preset_name, *run_mrgrad_analysis(output_root, load_mrgrad_preset(preset_name), **kwargs))
        for preset_name in preset_names
    ]
