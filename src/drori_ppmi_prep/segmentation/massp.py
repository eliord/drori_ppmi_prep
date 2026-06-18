from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


AHEAD_TEMPLATE_ARTICLE_ID = "12301106"
AHEAD_TEMPLATE_FILENAME = "ahead_med_qr1.nii.gz"
AHEAD_MNI09B_TEMPLATE_FILENAME = "ahead_med_qr1_mni09b.nii.gz"


@dataclass(frozen=True)
class MASSPResource:
    version: str
    cohort: str
    article_id: str
    filename: str
    label_filename: str
    description: str
    doi: str


MASSP_RESOURCES = {
    ("2021", "old"): MASSPResource(
        version="2021",
        cohort="old",
        article_id="19646346",
        filename="massp2021-parcellation_decade-61to80.nii.gz",
        label_filename="massp2021_labels.txt",
        description="MASSP 2021 Older Probabilistic Atlas (61 to 80 years)",
        doi="10.21942/uva.19646346",
    ),
    ("2021", "young"): MASSPResource(
        version="2021",
        cohort="young",
        article_id="19646328",
        filename="massp2021-parcellation_decade-18to40.nii.gz",
        label_filename="massp2021_labels.txt",
        description="MASSP 2021 Younger Probabilistic Atlas (18 to 40 years)",
        doi="10.21942/uva.19646328",
    ),
    ("2.0", "old"): MASSPResource(
        version="2.0",
        cohort="old",
        article_id="27292209",
        filename="ahead-massp2_avg-bestlabel_decade-61to80.nii.gz",
        label_filename="massp_2p0-label-list.txt",
        description="MASSP 2.0 Older Probabilistic Atlas (61 to 80 years)",
        doi="10.21942/uva.27292209",
    ),
    ("2.0", "young"): MASSPResource(
        version="2.0",
        cohort="young",
        article_id="27291963",
        filename="ahead-massp2_avg-bestlabel_decade-18to40.nii.gz",
        label_filename="massp_2p0-label-list.txt",
        description="MASSP 2.0 Younger Probabilistic Atlas (18 to 40 years)",
        doi="10.21942/uva.27291963",
    ),
}

DEFAULT_MASSP_VERSION = "2021"
DEFAULT_MASSP_COHORT = "old"
MASSP_VERSION_CHOICES = ("2021", "2.0")
MASSP_COHORT_CHOICES = ("old", "young")

DEFAULT_MASSP_RESOURCE = MASSP_RESOURCES[(DEFAULT_MASSP_VERSION, DEFAULT_MASSP_COHORT)]
MASSP_ATLAS_ARTICLE_ID = DEFAULT_MASSP_RESOURCE.article_id
MASSP_ATLAS_FILENAME = DEFAULT_MASSP_RESOURCE.filename


def get_massp_resource(version=DEFAULT_MASSP_VERSION, cohort=DEFAULT_MASSP_COHORT):
    key = (str(version), str(cohort))
    try:
        return MASSP_RESOURCES[key]
    except KeyError as exc:
        available = ", ".join(
            f"{version}/{cohort}"
            for version, cohort in sorted(MASSP_RESOURCES)
        )
        raise ValueError(
            f"Unsupported MASSP resource {version}/{cohort}. "
            f"Available resources: {available}"
        ) from exc


def default_template_filename_for_massp(version=DEFAULT_MASSP_VERSION):
    if str(version) == "2.0":
        return AHEAD_MNI09B_TEMPLATE_FILENAME
    return AHEAD_TEMPLATE_FILENAME


def massp_cache_subdir(version=DEFAULT_MASSP_VERSION, cohort=DEFAULT_MASSP_COHORT):
    return f"massp{version.replace('.', 'p')}_{cohort}"


def transformed_output_name(source_path: str | Path):
    name = Path(source_path).name
    if name.endswith(".nii.gz"):
        return f"{name[:-7]}_2ref.nii.gz"
    return f"{Path(name).stem}_2ref{Path(name).suffix}"


def massp_readme_text(resource: MASSPResource, template_filename: str):
    return f"""This segmentation is based on nonlinear registration of the AHEAD average R1 image and {resource.description} to the subject T1 reference space.
The AHEAD R1 template ({template_filename}) is registered to the subject brainmasked T1 image with ANTs affine + SyN registration.
The MASSP parcellation is transformed with ANTs using nearest-neighbor interpolation.
Atlas source: https://doi.org/{resource.doi}
Template source: https://doi.org/10.21942/uva.12301106
License: CC BY 4.0. Please cite the source datasets when using this output.
"""


def _download_file(url: str, output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")

    try:
        with urlopen(url) as response, tmp_path.open("wb") as f:
            shutil.copyfileobj(response, f)
    except URLError:
        if tmp_path.exists():
            tmp_path.unlink()
        return None

    tmp_path.replace(output_path)
    return output_path


def _figshare_file_download_url(article_id: str, filename: str):
    try:
        with urlopen(f"https://api.figshare.com/v2/articles/{article_id}/files") as response:
            files = json.loads(response.read().decode("utf-8"))
    except URLError:
        return None

    for file_info in files:
        if file_info.get("name") == filename:
            return file_info.get("download_url")

    return None


def resolve_massp_resource(
    path: str | Path | None,
    cache_dir: str | Path,
    article_id: str,
    filename: str,
    allow_download: bool = True,
):
    if path is not None:
        path = Path(path)
        return path if path.exists() else None

    cache_dir = Path(cache_dir)
    cached_path = cache_dir / filename
    if cached_path.exists():
        return cached_path

    if not allow_download:
        return None

    download_url = _figshare_file_download_url(article_id, filename)
    if download_url is None:
        return None

    return _download_file(download_url, cached_path)


def remove_massp_logs(output_dir: Path):
    for log_file in [
        output_dir / "massp_registration_command.txt",
        output_dir / "massp_apply_command.txt",
        output_dir / "massp_registration_stdout.log",
        output_dir / "massp_registration_stderr.log",
        output_dir / "massp_apply_stdout.log",
        output_dir / "massp_apply_stderr.log",
    ]:
        if log_file.exists():
            log_file.unlink()


def run_massp_atlas_segmentation(
    target_image,
    output_dir,
    atlas_path,
    template_path,
    massp_resource=None,
    ants_registration_cmd="antsRegistration",
    ants_apply_cmd="antsApplyTransforms",
    overwrite=False,
):
    target_image = Path(target_image)
    output_dir = Path(output_dir)
    atlas_path = Path(atlas_path) if atlas_path is not None else None
    template_path = Path(template_path) if template_path is not None else None

    if not target_image.exists() or atlas_path is None or template_path is None:
        return None, "missing"

    if not atlas_path.exists() or not template_path.exists():
        return None, "missing"

    template_output_name = transformed_output_name(template_path.name)
    atlas_output_name = transformed_output_name(atlas_path.name)
    warped_template = output_dir / template_output_name
    warped_atlas = output_dir / atlas_output_name
    readme_file = output_dir / "README.txt"
    transform_prefix = str(output_dir / "ahead2sub_")
    affine_transform = output_dir / "ahead2sub_0GenericAffine.mat"
    warp_transform = output_dir / "ahead2sub_1Warp.nii.gz"

    expected_outputs = [
        warped_template,
        warped_atlas,
        affine_transform,
        warp_transform,
        readme_file,
    ]
    if all(path.exists() for path in expected_outputs) and not overwrite:
        return warped_atlas, "skipped"

    if shutil.which(ants_registration_cmd) is None or shutil.which(ants_apply_cmd) is None:
        return None, "missing_command"

    output_dir.mkdir(parents=True, exist_ok=True)

    registration_cmd = [
        ants_registration_cmd,
        "--dimensionality", "3",
        "--float", "1",
        "--output", f"[{transform_prefix},{warped_template}]",
        "--interpolation", "BSpline",
        "--winsorize-image-intensities", "[0.005,0.995]",
        "--use-histogram-matching", "0",
        "--initial-moving-transform", f"[{target_image},{template_path},1]",
        "--transform", "Rigid[0.1]",
        "--metric", f"MI[{target_image},{template_path},1,32,Regular,0.25]",
        "--convergence", "[1000x500x250x100,1e-6,10]",
        "--shrink-factors", "8x4x2x1",
        "--smoothing-sigmas", "3x2x1x0vox",
        "--transform", "Affine[0.1]",
        "--metric", f"MI[{target_image},{template_path},1,32,Regular,0.25]",
        "--convergence", "[1000x500x250x100,1e-6,10]",
        "--shrink-factors", "8x4x2x1",
        "--smoothing-sigmas", "3x2x1x0vox",
        "--transform", "SyN[0.1,3,0]",
        "--metric", f"CC[{target_image},{template_path},1,4]",
        "--convergence", "[100x70x50x20,1e-6,10]",
        "--shrink-factors", "8x4x2x1",
        "--smoothing-sigmas", "3x2x1x0vox",
    ]
    apply_cmd = [
        ants_apply_cmd,
        "-d", "3",
        "-i", str(atlas_path),
        "-r", str(target_image),
        "-o", str(warped_atlas),
        "-n", "NearestNeighbor",
        "-t", str(warp_transform),
        "-t", str(affine_transform),
    ]

    (output_dir / "massp_registration_command.txt").write_text(
        shlex.join(registration_cmd) + "\n"
    )
    (output_dir / "massp_apply_command.txt").write_text(
        shlex.join(apply_cmd) + "\n"
    )

    with (output_dir / "massp_registration_stdout.log").open("w") as stdout_f:
        stderr_log = output_dir / "massp_registration_stderr.log"
        stderr_f = stderr_log.open("w")
        try:
            result = subprocess.run(
                registration_cmd,
                text=True,
                stdout=stdout_f,
                stderr=stderr_f,
            )
        finally:
            stderr_f.close()

    if result.returncode != 0 or not affine_transform.exists() or not warp_transform.exists():
        return None, "failed"

    with (output_dir / "massp_apply_stdout.log").open("w") as stdout_f:
        stderr_log = output_dir / "massp_apply_stderr.log"
        stderr_f = stderr_log.open("w")
        try:
            result = subprocess.run(
                apply_cmd,
                text=True,
                stdout=stdout_f,
                stderr=stderr_f,
            )
        finally:
            stderr_f.close()

    if readme_file.exists() and overwrite:
        readme_file.unlink()
    if not readme_file.exists():
        resource = massp_resource or DEFAULT_MASSP_RESOURCE
        readme_file.write_text(massp_readme_text(resource, template_path.name))

    if result.returncode == 0 and all(path.exists() for path in expected_outputs):
        remove_massp_logs(output_dir)
        return warped_atlas, "done"

    return None, "failed"
