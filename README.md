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

Python dependencies are listed in `requirements.txt`.

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
drori-ppmi-run-freesurfer ANALYSIS_ROOT
```

Use `--help` on any command to see available options, including alternate tool
paths, overwrite behavior, parallel execution, and segmentation skip flags.

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

## Package Layout

Core code is under `src/drori_ppmi_prep/`:

- `cli/`: command-line entry points
- `pipeline/`: full, infrastructure, and session orchestration
- `metadata/`: metadata table construction and DICOM header enrichment
- `conversion/`: DICOM to NIfTI conversion
- `analysis/`: analysis-directory creation
- `preprocessing/`: SynthStrip helpers
- `registration/`: FSL FLIRT registration helpers
- `segmentation/`: FSL FIRST, FreeSurfer, DBSegment, and segmentation utilities
