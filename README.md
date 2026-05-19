# drori_ppmi_prep

Utilities for preparing PPMI MRI data for analysis. The package builds metadata
from IDA search CSVs, converts PPMI DICOM folders to NIfTI, creates a normalized
analysis directory, and runs session-level preprocessing and segmentation.

## Citation

This pipeline was developed by Elior Drori at the Mezer Lab, Hebrew University
of Jerusalem, as part of Drori et al. (2026).

If you use this pipeline in your work, please cite:

```text
Drori E, Kurer N, Mezer AA.
Sensorimotor basal ganglia circuit asymmetry explains lateralized motor dysfunction in early Parkinson’s disease.
bioRxiv. 2026. https://doi.org/10.64898/2026.03.16.711841
```

## Installation

Install the package in editable mode from the repository root:

```bash
pip install -e .
```

Python dependencies are declared in `pyproject.toml` and installed
automatically by `pip`, including `mri-unbias` from the Mezer Lab GitHub
repository.

External tools are also required for the full pipeline:

- `dcm2niix` for DICOM to NIfTI conversion
- FreeSurfer / SynthStrip, typically `mri_synthstrip` and `recon-all`
- FSL, for `flirt` and `run_first_all`
- `DBSegment`, if DBSegment outputs are requested

## Expected Input Layout

The DICOM dataset is expected to follow the PPMI directory structure:

```text
PPMI/SUBJECT_ID/SEQUENCE_NAME/SESSION_ID/IMAGE_ID/*.dcm
```

The IDA search directory should contain the CSV files downloaded with the PPMI
image data.

## Main Commands

Run the full pipeline:

```bash
drori-ppmi-run-pipeline PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT
```

Build only the shared infrastructure:

```bash
drori-ppmi-build-infrastructure PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT
```

Run preprocessing for one subject/session after infrastructure has been built:

```bash
drori-ppmi-run-session OUTPUT_ROOT SUBJECT_ID SESSION_ID
```

Individual steps are also available:

```bash
drori-ppmi-build-metadata IDASEARCH_DIR PPMI_ROOT OUTPUT_CSV
drori-ppmi-convert PPMI_ROOT NIFTI_OUTPUT_ROOT
drori-ppmi-build-analysis METADATA_CSV NIFTI_ROOT ANALYSIS_ROOT
drori-ppmi-register-to-t1 ANALYSIS_ROOT
drori-ppmi-run-first ANALYSIS_ROOT
drori-ppmi-run-dbsegment ANALYSIS_ROOT
drori-ppmi-run-synthseg ANALYSIS_ROOT
drori-ppmi-run-freesurfer ANALYSIS_ROOT
drori-ppmi-check-outputs OUTPUT_ROOT
```

Use `--help` on any command to see available options, including alternate tool
paths, overwrite behavior, parallel execution, and segmentation skip flags.

Example full-pipeline command with common flags:

```bash
drori-ppmi-run-pipeline PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT \
  --parallel \
  --max-workers 8 \
  --skip-infrastructure-if-exists \
  --force \
  --dcm2niix-cmd dcm2niix \
  --synthstrip-cmd mri_synthstrip \
  --flirt-cmd flirt \
  --first-cmd run_first_all \
  --skip-freesurfer
```

For example, use `--skip-first`, `--skip-dbsegment`, `--skip-synthseg`,
`--skip-freesurfer`, or `--skip-bias-correction` to disable optional processing
during the full pipeline. When `--parallel` is used, DBSegment is run CPU-only
automatically to avoid concurrent CUDA use. Use `--skip-infrastructure-if-exists`
to rerun session-level processing without rebuilding metadata, NIfTI conversion,
and the analysis directory when those outputs already exist.

## Pipeline Steps

The full pipeline first builds the shared dataset infrastructure:

1. Build `ppmi_metadata.csv` from the IDA search CSV files.
2. Enrich the metadata table with selected DICOM header fields.
3. Convert each PPMI DICOM image directory to NIfTI with `dcm2niix`.
4. Build `PPMI_analysis/` with one subject/session folder per metadata row and
   standardized `T1.nii.gz`, `T2.nii.gz`, and `PD.nii.gz` links.
5. Write `ppmi_config.json`, which stores the resolved paths used by later
   session-level commands.

For each analysis session, the session pipeline then runs:

1. Run SynthStrip on native `T1`, `T2`, and `PD` images, with both regular and
   no-CSF outputs written under `segmentation_native/synthstrip/`.
2. Link the native T1-reference SynthStrip outputs into
   `t1_space/segmentation/synthstrip/`.
3. Register brain-masked `PD` to the brain-masked T1 reference using FSL FLIRT,
   save `flirt9dof_PD_to_T1.mat`, and apply the transform to the native `PD`
   and `T2` images to create `t1_space/PD.nii.gz` and `t1_space/T2.nii.gz`.
4. Optionally run FSL FIRST on the T1 reference and erode
   `first_all_fast_firstseg.nii.gz` to create
   `first_all_fast_firstseg_eroded.nii.gz`.
5. Optionally run DBSegment on the T1 reference.
6. Optionally run FreeSurfer SynthSeg on the T1 reference.
7. Optionally run FreeSurfer `recon-all` on the T1 reference, link the
   FreeSurfer `mri/` directory into the session segmentation directory, and
   export FreeSurfer `.mgz` volumes back into the session T1 space under
   `freesurfer/t1_space_outputs/`.
8. Optionally run polynomial degree-2 bias correction on available
   `t1_space/T1.nii.gz`, `PD.nii.gz`, and `T2.nii.gz` images using the
   FreeSurfer `aparc+aseg.nii.gz` labels 2 and 41 as the white-matter mask.

## Output Structure

The infrastructure step writes outputs under `OUTPUT_ROOT`:

```text
OUTPUT_ROOT/
  ppmi_config.json
  ppmi_metadata.csv
  PPMI_nifti/
  PPMI_analysis/
  group_analysis/
```

Each analysis session is organized as:

```text
PPMI_analysis/SUBJECT_ID/SESSION_ID/
  T1.nii.gz
  T2.nii.gz
  PD.nii.gz
  segmentation_native/
  t1_space/
```

After T1-space registration and segmentation, `t1_space/` contains the
registered session images, transform matrix, and segmentation outputs:

```text
t1_space/
  T1.nii.gz
  T2.nii.gz
  PD.nii.gz
  flirt9dof_PD_to_T1.mat
  segmentation/
    synthstrip/
      T1_brainmask.nii.gz
      T1_brainmask_mask.nii.gz
      T1_brainmask_nocsf.nii.gz
      T1_brainmask_mask_nocsf.nii.gz
    fslfirst/
      first_all_fast_firstseg.nii.gz
      first_all_fast_firstseg_eroded.nii.gz
    dbsegment/
    synthseg/
      synthseg.nii.gz
    freesurfer/
      t1_space_outputs/
  mri_unbias_deg2/
    wm_labels_2_41_mask.nii.gz
    T1.nii.gz
    T1_bias.nii.gz
    PD.nii.gz
    PD_bias.nii.gz
    T2.nii.gz
    T2_bias.nii.gz
```

## Package Layout

Core code is under `src/drori_ppmi_prep/`:

- `cli/`: command-line entry points
- `pipeline/`: full, infrastructure, and session orchestration
- `metadata/`: metadata table construction and DICOM header enrichment
- `conversion/`: DICOM to NIfTI conversion
- `analysis/`: analysis-directory creation
- `preprocessing/`: SynthStrip and bias-correction helpers
- `registration/`: FSL FLIRT registration helpers
- `segmentation/`: FSL FIRST, DBSegment, SynthSeg, FreeSurfer, and segmentation utilities
