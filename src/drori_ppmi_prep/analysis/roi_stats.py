from __future__ import annotations

import json
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import nibabel as nib
import numpy as np
import pandas as pd


IMAGE_PATHS = {
    "t1_space": {
        "t1": "t1_space/T1.nii.gz",
        "t2": "t1_space/T2.nii.gz",
        "pd": "t1_space/PD.nii.gz",
    },
    "mri_unbias_deg2": {
        "t1": "t1_space/mri_unbias_deg2/T1.nii.gz",
        "t2": "t1_space/mri_unbias_deg2/T2.nii.gz",
        "pd": "t1_space/mri_unbias_deg2/PD.nii.gz",
    },
}
INTENSITY_STATS = ("median", "mean", "mad", "std")

ASEG_LABELS = {
    2: "Left-Cerebral-White-Matter",
    3: "Left-Cerebral-Cortex",
    4: "Left-Lateral-Ventricle",
    5: "Left-Inf-Lat-Vent",
    7: "Left-Cerebellum-White-Matter",
    8: "Left-Cerebellum-Cortex",
    10: "Left-Thalamus",
    11: "Left-Caudate",
    12: "Left-Putamen",
    13: "Left-Pallidum",
    14: "3rd-Ventricle",
    15: "4th-Ventricle",
    16: "Brain-Stem",
    17: "Left-Hippocampus",
    18: "Left-Amygdala",
    24: "CSF",
    26: "Left-Accumbens-area",
    28: "Left-VentralDC",
    41: "Right-Cerebral-White-Matter",
    42: "Right-Cerebral-Cortex",
    43: "Right-Lateral-Ventricle",
    44: "Right-Inf-Lat-Vent",
    46: "Right-Cerebellum-White-Matter",
    47: "Right-Cerebellum-Cortex",
    49: "Right-Thalamus",
    50: "Right-Caudate",
    51: "Right-Putamen",
    52: "Right-Pallidum",
    53: "Right-Hippocampus",
    54: "Right-Amygdala",
    58: "Right-Accumbens-area",
    60: "Right-VentralDC",
}
SYNTHSEG_LABELS = dict(ASEG_LABELS)
APARC_NAMES = (
    "unknown",
    "bankssts",
    "caudalanteriorcingulate",
    "caudalmiddlefrontal",
    "corpuscallosum",
    "cuneus",
    "entorhinal",
    "fusiform",
    "inferiorparietal",
    "inferiortemporal",
    "isthmuscingulate",
    "lateraloccipital",
    "lateralorbitofrontal",
    "lingual",
    "medialorbitofrontal",
    "middletemporal",
    "parahippocampal",
    "paracentral",
    "parsopercularis",
    "parsorbitalis",
    "parstriangularis",
    "pericalcarine",
    "postcentral",
    "posteriorcingulate",
    "precentral",
    "precuneus",
    "rostralanteriorcingulate",
    "rostralmiddlefrontal",
    "superiorfrontal",
    "superiorparietal",
    "superiortemporal",
    "supramarginal",
    "frontalpole",
    "temporalpole",
    "transversetemporal",
    "insula",
)
DKT_APARC_INDICES = tuple(
    index
    for index in range(len(APARC_NAMES))
    if index not in {0, 1, 4, 32, 33}
)
DKT_APARC_ASEG_LABELS = {
    **ASEG_LABELS,
    30: "Left-vessel",
    31: "Left-choroid-plexus",
    62: "Right-vessel",
    63: "Right-choroid-plexus",
    72: "5th-Ventricle",
    77: "WM-hypointensities",
    80: "non-WM-hypointensities",
    85: "Optic-Chiasm",
    251: "CC_Posterior",
    252: "CC_Mid_Posterior",
    253: "CC_Central",
    254: "CC_Mid_Anterior",
    255: "CC_Anterior",
    **{1000 + index: f"ctx-lh-{APARC_NAMES[index]}" for index in DKT_APARC_INDICES},
    **{2000 + index: f"ctx-rh-{APARC_NAMES[index]}" for index in DKT_APARC_INDICES},
}
FIRST_LABELS = {
    key: ASEG_LABELS[key]
    for key in (10, 11, 12, 13, 16, 17, 18, 26, 49, 50, 51, 52, 53, 54, 58)
}
DBSEGMENT_LABELS = {
    1: "Brain-mask",
    2: "Caudate-L",
    3: "Caudate-R",
    4: "GPe-L",
    5: "GPe-R",
    6: "GPi-L",
    7: "GPi-R",
    8: "Habenular-nuclei-L",
    9: "Habenular-nuclei-R",
    10: "Internal-capsule-L",
    11: "Internal-capsule-R",
    12: "Nucleus-accumbens-L",
    13: "Nucleus-accumbens-R",
    14: "Putamen-L",
    15: "Putamen-R",
    16: "Red-nucleus-L",
    17: "Red-nucleus-R",
    18: "SNc-L",
    19: "SNc-R",
    20: "SNr-L",
    21: "SNr-R",
    22: "STN-L",
    23: "STN-R",
    24: "Thalamus-L",
    25: "Thalamus-R",
    26: "VPL-L",
    27: "VPL-R",
    28: "Lateral-ventricle-L",
    29: "Lateral-ventricle-R",
    30: "VIM-L",
    31: "VIM-R",
}
DBSEGMENT_GP_SN_LABELS = {
    4: "GP-L",
    5: "GP-R",
    18: "SN-L",
    19: "SN-R",
}
MASSP_LABELS = {
    index + 1: label_name
    for index, label_name in enumerate(
        (
            "Str-L",
            "Str-R",
            "STN-L",
            "STN-R",
            "SN-L",
            "SN-R",
            "RN-L",
            "RN-R",
            "GPi-L",
            "GPi-R",
            "GPe-L",
            "GPe-R",
            "Tha-L",
            "Tha-R",
            "LV-L",
            "LV-R",
            "3V",
            "4V",
            "Amg-L",
            "Amg-R",
            "ic-L",
            "ic-R",
            "VTA-L",
            "VTA-R",
            "fx",
            "PAG-L",
            "PAG-R",
            "PPN-L",
            "PPN-R",
            "Cl-L",
            "Cl-R",
        )
    )
}

SEGMENTATIONS = {
    "freesurfer": {
        "path": (
            "t1_space/segmentation/freesurfer/t1_space_outputs/"
            "aparc.DKTatlas+aseg.nii.gz"
        ),
        "labels": "freesurfer",
    },
    "synthstrip": {
        "path": "t1_space/segmentation/synthstrip/T1_brainmask_mask.nii.gz",
        "labels": {1: "Brain-mask"},
    },
    "synthseg": {
        "path": "t1_space/segmentation/synthseg/synthseg.nii.gz",
        "labels": SYNTHSEG_LABELS,
    },
    "fslfirst": {
        "path": "t1_space/segmentation/fslfirst/first_all_fast_firstseg.nii.gz",
        "labels": FIRST_LABELS,
    },
    "fslfirst_eroded": {
        "path": "t1_space/segmentation/fslfirst/first_all_fast_firstseg_eroded.nii.gz",
        "labels": FIRST_LABELS,
    },
    "dbsegment": {
        "path": "t1_space/segmentation/dbsegment/T1.nii.gz",
        "labels": DBSEGMENT_LABELS,
    },
    "dbsegment_GP_SN": {
        "path": "t1_space/segmentation/dbsegment/derivatives/GP_SN_seg.nii.gz",
        "labels": DBSEGMENT_GP_SN_LABELS,
    },
    "massp": {
        "path": (
            "t1_space/segmentation/massp/ahead2sub_ants/"
            "massp2021-parcellation_decade-61to80_2ref.nii.gz"
        ),
        "labels": MASSP_LABELS,
    },
}


def resolve_dataset_paths(output_root):
    output_root = Path(output_root)
    config_path = output_root / "ppmi_config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config = json.loads(config_path.read_text())
    return Path(config["analysis_root"]), Path(config["metadata_csv"])


def parse_freesurfer_lut(path):
    labels = {}
    with Path(path).open() as f:
        for line in f:
            fields = line.split()
            if len(fields) >= 2 and fields[0].isdigit():
                labels[int(fields[0])] = fields[1]
    return labels


def resolve_freesurfer_lut(path=None):
    candidates = []
    if path is not None:
        candidates.append(Path(path))
    freesurfer_home = os.environ.get("FREESURFER_HOME")
    if freesurfer_home:
        candidates.append(Path(freesurfer_home) / "FreeSurferColorLUT.txt")

    for candidate in candidates:
        if candidate.exists():
            lut = parse_freesurfer_lut(candidate)
            return {
                label: lut.get(label, fallback_name)
                for label, fallback_name in DKT_APARC_ASEG_LABELS.items()
            }

    return dict(DKT_APARC_ASEG_LABELS)


def _load_image(path):
    try:
        image = nib.load(str(path))
        data = np.asanyarray(image.dataobj)
        if data.ndim != 3:
            return None, None
        return image, data
    except Exception:
        return None, None


def _intensity_values(values):
    values = values[np.isfinite(values)]
    if values.size == 0:
        return {stat: np.nan for stat in INTENSITY_STATS}

    median = float(np.median(values))
    return {
        "median": median,
        "mean": float(np.mean(values)),
        "mad": float(np.median(np.abs(values - median))),
        "std": float(np.std(values)),
    }


def _session_stats(job):
    row_index, analysis_root, subject_id, session_id, segmentations = job
    session_dir = Path(analysis_root) / subject_id / session_id
    result = {"row_index": row_index, "stats": {}}

    images = {}
    for image_set, paths in IMAGE_PATHS.items():
        images[image_set] = {
            image_name: _load_image(session_dir / relative_path)
            for image_name, relative_path in paths.items()
        }

    for segmentation_name, config in segmentations.items():
        segmentation_image, segmentation_data = _load_image(session_dir / config["path"])
        labels = config["labels"]
        segmentation_result = {"volume": {}, "images": {}}
        result["stats"][segmentation_name] = segmentation_result

        if segmentation_data is None:
            continue

        segmentation_data = np.rint(segmentation_data).astype(np.int32)
        voxel_volume = float(abs(np.linalg.det(segmentation_image.affine[:3, :3])))

        for label in labels:
            segmentation_result["volume"][label] = (
                float(np.count_nonzero(segmentation_data == label)) * voxel_volume
            )

        for image_set, image_data_by_name in images.items():
            segmentation_result["images"][image_set] = {}
            for image_name, (image, image_data) in image_data_by_name.items():
                if (
                    image_data is None
                    or image_data.shape != segmentation_data.shape
                    or not np.allclose(image.affine, segmentation_image.affine)
                ):
                    continue
                image_result = {}
                segmentation_result["images"][image_set][image_name] = image_result
                for label in labels:
                    image_result[label] = _intensity_values(
                        image_data[segmentation_data == label]
                    )

    return result


def _metadata_rows(metadata_csv):
    metadata = pd.read_csv(metadata_csv, dtype={"SubjectID": str, "SessionID": str})
    required = {"SubjectID", "SessionID"}
    if not required <= set(metadata.columns):
        raise ValueError("Metadata CSV must contain SubjectID and SessionID columns.")
    return metadata[["SubjectID", "SessionID"]].copy()


def _normalize_subject_id(value):
    value = str(value).strip()
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
    except ValueError:
        pass
    return value


def _output_files(output_root, segmentations):
    output_root = Path(output_root)
    files = []
    for segmentation_name in segmentations:
        files.append(
            output_root
            / "group_analysis"
            / "ROI_stats"
            / "t1_space"
            / f"{segmentation_name}_volume.csv"
        )
        for image_set in IMAGE_PATHS:
            output_dir = output_root / "group_analysis" / "ROI_stats" / "t1_space"
            if image_set != "t1_space":
                output_dir = output_dir / image_set
            for image_name in IMAGE_PATHS[image_set]:
                for stat in INTENSITY_STATS:
                    files.append(output_dir / f"{segmentation_name}_{image_name}_{stat}.csv")
    return files


def run_roi_stats(
    output_root,
    freesurfer_lut=None,
    overwrite=False,
    parallel=False,
    max_workers=None,
):
    output_root = Path(output_root)
    analysis_root, metadata_csv = resolve_dataset_paths(output_root)
    metadata = _metadata_rows(metadata_csv)
    segmentations = {
        name: dict(config)
        for name, config in SEGMENTATIONS.items()
    }
    segmentations["freesurfer"]["labels"] = resolve_freesurfer_lut(freesurfer_lut)

    output_files = _output_files(output_root, segmentations)
    if not overwrite and all(path.exists() for path in output_files):
        return output_root / "group_analysis" / "ROI_stats", "skipped"

    jobs = [
        (
            row_index,
            str(analysis_root),
            _normalize_subject_id(row["SubjectID"]),
            str(row["SessionID"]),
            segmentations,
        )
        for row_index, row in metadata.iterrows()
    ]
    if parallel:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            session_results = list(executor.map(_session_stats, jobs))
    else:
        session_results = [_session_stats(job) for job in jobs]

    session_results = {result["row_index"]: result["stats"] for result in session_results}
    base_columns = metadata.reset_index(drop=True)

    def write_table(path, segmentation_name, labels, value_getter):
        roi_columns = {
            f"{label}_{label_name}": [
                value_getter(session_results[row_index].get(segmentation_name, {}), label)
                for row_index in metadata.index
            ]
            for label, label_name in labels.items()
        }
        table = pd.concat(
            [base_columns, pd.DataFrame(roi_columns, index=base_columns.index)],
            axis=1,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        table.to_csv(path, index=False)

    for segmentation_name, config in segmentations.items():
        labels = config["labels"]
        output_dir = output_root / "group_analysis" / "ROI_stats" / "t1_space"
        write_table(
            output_dir / f"{segmentation_name}_volume.csv",
            segmentation_name,
            labels,
            lambda result, label: result.get("volume", {}).get(label, np.nan),
        )
        for image_set in IMAGE_PATHS:
            image_output_dir = output_dir if image_set == "t1_space" else output_dir / image_set
            for image_name in IMAGE_PATHS[image_set]:
                for stat in INTENSITY_STATS:
                    write_table(
                        image_output_dir / f"{segmentation_name}_{image_name}_{stat}.csv",
                        segmentation_name,
                        labels,
                        lambda result, label, image_set=image_set, image_name=image_name, stat=stat: (
                            result.get("images", {})
                            .get(image_set, {})
                            .get(image_name, {})
                            .get(label, {})
                            .get(stat, np.nan)
                        ),
                    )

    return output_root / "group_analysis" / "ROI_stats", "done"
