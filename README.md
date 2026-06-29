# drori_ppmi_prep

Utilities for preparing PPMI MRI data for analysis. The package builds metadata
from IDA search CSVs, converts PPMI DICOM folders to NIfTI, creates a normalized
analysis directory, and runs session-level preprocessing and segmentation.

## Citation

This pipeline was developed by Elior Drori at the Mezer Lab, Hebrew University
of Jerusalem, as part of Drori et al. (2025).

If you use this pipeline in your work, please cite:

```text
Drori E, Kurer N, Mezer AA.
Sensorimotor basal ganglia circuit asymmetry explains lateralized motor dysfunction in early Parkinson’s disease.
bioRxiv. 2025. https://doi.org/10.64898/2026.03.16.711841
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
- ANTs, for MASSP atlas nonlinear registration:
  https://github.com/ANTsX/ANTs
- MATLAB, for the optional standalone mrGrad analysis command:
  https://www.mathworks.com/products/matlab.html

## Testing

Install the development dependency and run the test suite from the repository
root:

```bash
pip install -e ".[dev]"
python -m pytest
```

The included tests cover package logic that does not require external imaging
tools, such as metadata image selection, label erosion, DBSegment-derived
segmentations, and ROI lookup-table naming.

## Data Download And Provenance

Before running the pipeline, download the imaging data directly from the PPMI
database. The downloaded image archive should contain the PPMI DICOM directory
tree, and the corresponding IDA image-search CSV files should be downloaded as
well. These CSV files are required because the pipeline uses them to build the
cohort metadata table and to map PPMI image identifiers to subject/session
records.

If clinical or demographic cohort tables are needed, download the relevant PPMI
study-table CSV files separately and pass their root directory with
`--study-tables-root`.

For reproducibility, the exact PPMI search criteria used for a publication
should be documented with the project. Drori et al. (2026) used the following
PPMI 3T Siemens TrioTim image search:

```text
PPMI image collection, Advanced Search:
- Tick "display in result" for all available fields.
- Research Group: Control, PD, SWEDD, Prodromal
- Modality: MRI
- Manufacturer: SIEMENS
- Mfg Model: TrioTim

T1 search:
- Slice Thickness (mm): 1
- Weighting: T1

T2/PD search:
- Slice Thickness (mm): 3
- Weighting: T2, PD

After each search:
- Save the CSV with all available data fields using "CSV Download".
- Download DICOMs using "Add To Collection".

Clinical data:
- Download relevant tables from PPMI Study Data. Most important is MDS-UPDRS-III.
- Study Data tables are downloaded for the full PPMI database and later
  filtered to the imaging cohort by the pipeline.
```

## Expected Input Layout

The DICOM dataset is expected to follow the PPMI directory structure:

```text
PPMI/SUBJECT_ID/SEQUENCE_NAME/SESSION_ID/IMAGE_ID/*.dcm
```

The IDA search directory should contain the search CSV files exported from the
same PPMI/IDA query used to download the image data.

## Main Commands

Run the full pipeline:

```bash
drori-ppmi-run-pipeline PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT
```

Build only the shared infrastructure:

```bash
drori-ppmi-build-infrastructure PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT
```

Expensive infrastructure stages can be skipped when their outputs already
exist:

```bash
drori-ppmi-build-infrastructure PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT \
  --skip-dicom-conversion \
  --skip-analysis-build
```

Run preprocessing for one subject/session after infrastructure has been built:

```bash
drori-ppmi-run-session OUTPUT_ROOT SUBJECT_ID SESSION_ID
```

Individual steps are also available:

```bash
drori-ppmi-build-metadata IDASEARCH_DIR PPMI_ROOT OUTPUT_CSV
drori-ppmi-build-cohort-tables OUTPUT_ROOT STUDY_TABLES_ROOT
drori-ppmi-convert PPMI_ROOT NIFTI_OUTPUT_ROOT
drori-ppmi-build-analysis METADATA_CSV NIFTI_ROOT ANALYSIS_ROOT
drori-ppmi-register-to-t1 ANALYSIS_ROOT
drori-ppmi-run-first ANALYSIS_ROOT
drori-ppmi-run-dbsegment ANALYSIS_ROOT
drori-ppmi-run-synthseg ANALYSIS_ROOT
drori-ppmi-download-massp OUTPUT_ROOT
drori-ppmi-run-massp ANALYSIS_ROOT
drori-ppmi-run-freesurfer ANALYSIS_ROOT
drori-ppmi-check-outputs OUTPUT_ROOT
drori-ppmi-run-mrgrad OUTPUT_ROOT
drori-ppmi-run-roi-stats OUTPUT_ROOT
```

Use `--help` on any command to see available options, including alternate tool
paths, overwrite behavior, parallel execution, and segmentation skip flags.

## General-Purpose CLIs

Some commands expose reusable processing steps without assuming a PPMI dataset
layout. These are useful for applying individual pipeline components to other
projects.

Convert one DICOM directory to NIfTI:

```bash
drori-dicom-to-nifti \
  --dicom-dir dicoms/T1 \
  --output-dir nifti \
  --filename T1
```

This is a thin wrapper around `dcm2niix -z y -b n -o OUTPUT_DIR -f FILENAME
DICOM_DIR`, with an additional check that outputs are gzipped `.nii.gz` files.

Run SynthStrip for one image:

```bash
drori-synthstrip \
  --input T1.nii.gz \
  --output T1_brainmask.nii.gz \
  --mask T1_brainmask_mask.nii.gz
```

Run FSL FIRST for one image, with optional erosion:

```bash
drori-fslfirst \
  --input T1_brainmask.nii.gz \
  --output-dir segmentation/fslfirst \
  --brain-extracted \
  --erode
```

Run DBSegment for one image:

```bash
drori-dbsegment \
  --input T1_brainmask.nii.gz \
  --output-dir segmentation/dbsegment \
  --cpu
```

The DBSegment command also creates the derived whole GP/SN segmentation under
`segmentation/dbsegment/derivatives/GP_SN_seg.nii.gz`.

Erode a label segmentation:

```bash
drori-erode-labels \
  --segmentation first_all_fast_firstseg.nii.gz \
  --output first_all_fast_firstseg_eroded.nii.gz \
  --label 12 \
  --label 51
```

If `--label` is omitted, all nonzero labels are eroded independently. The
erosion uses the same 6-neighbor structure as MATLAB `strel("sphere", 1)`.

Create a binary mask from selected segmentation labels:

```bash
drori-label-mask \
  --segmentation aparc+aseg.nii.gz \
  --output wm_mask_eroded.nii.gz \
  --label 2 \
  --label 41 \
  --erode
```

The mask command is generic: the input can be FreeSurfer, SynthSeg, or another
label segmentation, as long as the requested labels are meaningful for that
segmentation.

Run FreeSurfer SynthSeg for one image:

```bash
drori-synthseg \
  --input T1.nii.gz \
  --output-dir segmentation/synthseg
```

SynthSeg runs with FreeSurfer's `--cpu` option to avoid incompatible CUDA/DNN environments.

Run FreeSurfer for one image and export outputs to a reference image space:

```bash
drori-freesurfer \
  --input T1.nii.gz \
  --subjects-dir group_analysis/FreeSurfer \
  --subject-id sub-01_ses-01 \
  --reference-image t1_space/T1.nii.gz \
  --output-dir t1_space/segmentation/freesurfer/t1_space_outputs
```

Export an existing FreeSurfer subject without rerunning `recon-all`:

```bash
drori-freesurfer \
  --subjects-dir group_analysis/FreeSurfer \
  --subject-id sub-01_ses-01 \
  --reference-image t1_space/T1.nii.gz \
  --output-dir t1_space/segmentation/freesurfer/t1_space_outputs \
  --export-only
```

Run MASSP atlas registration for one target image:

```bash
drori-massp \
  --target-image T1_brainmask.nii.gz \
  --output-dir segmentation/massp
```

The default MASSP resource is `--massp-version 2021 --massp-cohort old`, which
uses the MASSP 2021 Older Probabilistic Atlas. Other supported combinations are
available through the same flags:

```bash
drori-massp \
  --target-image T1_brainmask.nii.gz \
  --output-dir segmentation/massp \
  --massp-version 2.0 \
  --massp-cohort young
```

For MASSP 2.0, the package uses the discrete `avg-bestlabel` atlas file
(`ahead-massp2_avg-bestlabel_*`) rather than the probabilistic maps or max-label
variants.

By default, missing AHEAD/MASSP resources are downloaded into
`segmentation/massp/atlases/<selected_massp_resource>/`, and outputs are
written under:

```text
segmentation/massp/ahead2sub_ants/
  ahead_med_qr1_2ref.nii.gz
  <selected_massp_atlas>_2ref.nii.gz
  ahead2sub_0GenericAffine.mat
  ahead2sub_1Warp.nii.gz
  ahead2sub_1InverseWarp.nii.gz
  README.txt
```

Use manually managed atlas/template files:

```bash
drori-massp \
  --target-image T1_brainmask.nii.gz \
  --output-dir segmentation/massp \
  --template /path/to/ahead_med_qr1.nii.gz \
  --atlas /path/to/massp2021-parcellation_decade-61to80.nii.gz \
  --no-download
```

Run polynomial bias correction for one image:

```bash
drori-mri-unbias \
  --image T1.nii.gz \
  --mask wm_mask_eroded.nii.gz \
  --brain-mask T1_brainmask_mask.nii.gz \
  --corrected T1_unbiased.nii.gz \
  --bias-field T1_bias.nii.gz \
  --degree 2
```

This is equivalent to calling the `mri_unbias` package CLI directly:

```bash
mri-unbias \
  T1.nii.gz \
  wm_mask_eroded.nii.gz \
  --brain-mask T1_brainmask_mask.nii.gz \
  --corrected T1_unbiased.nii.gz \
  --bias-field T1_bias.nii.gz \
  --degree 2
```

Example full-pipeline command with common flags:

```bash
drori-ppmi-run-pipeline PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT \
  --parallel \
  --max-workers 8 \
  --skip-infrastructure-if-exists \
  --force \
  --study-tables-root /path/to/Study \
  --dcm2niix-cmd dcm2niix \
  --synthstrip-cmd mri_synthstrip \
  --flirt-cmd flirt \
  --first-cmd run_first_all \
  --skip-freesurfer
```

For example, use `--skip-first`, `--skip-dbsegment`, `--skip-synthseg`,
`--skip-massp`, `--skip-freesurfer`, `--skip-bias-correction`, or
`--skip-roi-stats` to disable optional processing during the full pipeline.
Use `--skip-session-pipeline` to bypass all session-level steps and continue
directly to group analyses. When
`--parallel` is used, DBSegment is run CPU-only automatically to avoid
concurrent CUDA use. Use
`--skip-infrastructure-if-exists` to rerun session-level processing without
rebuilding metadata, NIfTI conversion, and the analysis directory when those
outputs already exist. Use `--force-bias-correction` to recreate only the
`mri_unbias_deg2` outputs without forcing the other session-level steps. Use
`--study-tables-root PATH` to generate cohort-specific clinical tables during
infrastructure building; missing study tables are reported and skipped.
`--restart-incomplete-freesurfer` to delete and restart only incomplete
FreeSurfer subject directories while leaving completed reconstructions intact.

The PPMI session pipeline uses the AHEAD template and MASSP 2021 Older Adults
atlas from Figshare by default (`--massp-version 2021 --massp-cohort old`). Use
`--massp-version {2021,2.0}` and `--massp-cohort {old,young}` to choose another
supported MASSP resource. For MASSP 2.0, the selected atlas is the discrete
`avg-bestlabel` parcellation. Missing resources are downloaded into
`OUTPUT_ROOT/group_analysis/atlases/<selected_massp_resource>/`. Use
`--massp-atlas`, `--massp-template`, or `--massp-no-download` to use manually
managed files.

## mrGrad Analyses

mrGrad analyses are optional group-level analyses and are not run by the full
preprocessing pipeline. Run them separately after preprocessing outputs are
available:

```bash
drori-ppmi-run-mrgrad OUTPUT_ROOT
```

The command downloads and caches the pinned `mrGrad v2.0.3` MATLAB toolbox from
https://github.com/MezerLab/mrGrad when needed. Use `--mrgrad-dir PATH` to
provide an existing toolbox checkout or `--mrgrad-no-download` to disable the
automatic download.

Built-in presets:

```text
putamen-fslfirst-10seg  eroded FSL FIRST putamen labels 12 and 51, 10 segments
gpe-dbsegment-5seg     DBSegment-derived GPe labels 4 and 5, 5 segments
```

Both presets sample corrected T1, T2, and PD images using equidistance
segments, `max_change = [2 3 1]` for each ROI, mrGrad `extended` output mode,
and `allow_missing = true`. The mrGrad input preserves the row order from
`ppmi_metadata.csv` and includes every metadata row, including sessions with
missing inputs. Metadata rows without a session ID use a unique placeholder
such as `3305_missing-session_row-177`. Results are written under:

```text
group_analysis/mrGrad/mrgrad-putamen-fslfirst-10seg/
  mrGrad_putamen.mat
  mrGrad_putamen.csv
  mrgrad_input.mat
  mrgrad_input_sessions.csv
  run_mrgrad.m
  mrGradSeg/
group_analysis/mrGrad/mrgrad-gpe-dbsegment-5seg/
  mrGrad_GPe.mat
  mrGrad_GPe.csv
  ...
```

List or inspect presets:

```bash
drori-ppmi-run-mrgrad --list-presets
drori-ppmi-run-mrgrad --show-preset gpe-dbsegment-5seg
```

Run selected presets or a custom JSON configuration:

```bash
drori-ppmi-run-mrgrad OUTPUT_ROOT --preset putamen-fslfirst-10seg
drori-ppmi-run-mrgrad OUTPUT_ROOT --config my_mrgrad_analysis.json
```

## Clinical Cohort Tables

If PPMI study tables were downloaded, the infrastructure step can create
cohort-specific clinical tables with the same rows as `ppmi_metadata.csv`:

```bash
drori-ppmi-build-infrastructure PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT \
  --study-tables-root /path/to/Study
```

To rebuild metadata, cohort tables, and `ppmi_config.json` without scanning the
DICOM conversion or analysis-link stages:

```bash
drori-ppmi-build-infrastructure PPMI_ROOT IDASEARCH_DIR OUTPUT_ROOT \
  --study-tables-root /path/to/Study \
  --skip-dicom-conversion \
  --skip-analysis-build
```

They can also be generated independently:

```bash
drori-ppmi-build-cohort-tables OUTPUT_ROOT /path/to/Study
```

Tables are written under `OUTPUT_ROOT/cohort_tables/`. Each output starts with
`RowID`, `SubjectID`, and `SessionID`, then appends the matched clinical row. For
visit-sensitive study tables, the clinical visit closest to the MRI date is
selected. Study table files may include a suffix before `.csv`; for example,
`Other_Clinical_Features_12Mar2024.csv` can satisfy the
`Other_Clinical_Features.csv` table definition. The search is recursive under
`--study-tables-root`, so the source files do not need to be in the exact PPMI
subdirectories expected by the built-in table definitions. Missing study tables
are reported and skipped.

Derived clinical metrics are written under `cohort_tables/calculated/`,
including motor scores from UPDRS III, disease-duration estimates, and RBD
score when the required source tables and columns are available.

The cohort-table step also creates `ppmi_cohort_imaging_QA.csv` with columns
`RowID`, `SubjectID`, `SessionID`, `image_QA`, `fslfirst_QA`, `massp_QA`,
`abnormality_QA`, and `motion_QA`. QA columns are initialized as missing
values so they can be filled manually after visual inspection.

## Pipeline Steps

The full pipeline first builds the shared dataset infrastructure:

1. Build `ppmi_metadata.csv` from the IDA search CSV files.
   Raw candidate image IDs are retained as `T1_1`, `T1_2`, `T2_1`, etc.; the
   unsuffixed `T1`, `T2`, and `PD` columns store the selected analysis images.
   Non-preferred descriptions such as `GRAPPA_ND` are avoided when possible;
   among equal-quality repeats, the later candidate is selected.
2. Enrich the metadata table with selected DICOM header fields.
3. Convert each PPMI DICOM image directory to NIfTI with `dcm2niix`.
4. Build `PPMI_analysis/` with one subject/session folder per metadata row and
   standardized `T1.nii.gz`, `T2.nii.gz`, and `PD.nii.gz` links.
5. Optionally build cohort-specific clinical tables from downloaded PPMI study
   tables when `--study-tables-root` is provided.
6. Write `ppmi_config.json`, which stores the resolved paths used by later
   session-level commands.

Use `--skip-dicom-enrichment`, `--skip-dicom-conversion`, or
`--skip-analysis-build` to skip selected infrastructure stages. The full
pipeline accepts the same flags and passes them to the infrastructure step.

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
5. Optionally run DBSegment on the T1 reference and derive a combined GP/SN
   segmentation from the DBSegment subregion labels: left GP `(4, 6) -> 4`,
   right GP `(5, 7) -> 5`, left SN `(18, 20) -> 18`, and right SN
   `(19, 21) -> 19`.
6. Optionally run FreeSurfer SynthSeg on the T1 reference.
7. Optionally run MASSP atlas segmentation by nonlinearly registering the AHEAD
   R1 template to the brain-masked T1 reference with ANTs and applying the
   transform to the selected MASSP parcellation with nearest-neighbor
   interpolation. The default is MASSP 2021 older adults; use
   `--massp-version` and `--massp-cohort` to select another supported atlas.
8. Optionally run FreeSurfer `recon-all` on the T1 reference, link the
   FreeSurfer `mri/` directory into the session segmentation directory, and
   export FreeSurfer `.mgz` volumes back into the session T1 space under
   `freesurfer/t1_space_outputs/`.
9. Optionally run polynomial degree-2 bias correction on available
   `t1_space/T1.nii.gz`, `PD.nii.gz`, and `T2.nii.gz` images using the
   eroded FreeSurfer labels 2 and 41 as the white-matter mask and the
   SynthStrip T1 brain mask as the brain mask when available.

After all session-level jobs finish, the full pipeline optionally writes
ROI-statistics tables.

## ROI Statistics

The full pipeline writes group-level ROI tables after session processing. They
can also be generated independently:

```bash
drori-ppmi-run-roi-stats OUTPUT_ROOT
```

Use repeated `--segmentation NAME` options to regenerate only selected tables:

```bash
drori-ppmi-run-roi-stats OUTPUT_ROOT --overwrite --parallel --segmentation dbsegment --segmentation fslfirst
```

Valid segmentation names are `freesurfer`, `synthstrip`, `synthseg`,
`fslfirst`, `fslfirst_eroded`, `dbsegment`, `dbsegment_whole`, and `massp`.
Images and statistics can be filtered as well:

```bash
drori-ppmi-run-roi-stats OUTPUT_ROOT --overwrite --segmentation dbsegment --image t1 --stat mean --stat volume
```

Valid image names are `t1`, `t2`, and `pd`. Valid statistics are `median`,
`mean`, `mad`, `std`, and `volume`.
The command prints coarse progress every 50 completed sessions by default. Use
`--progress-interval N` to change this or `--quiet` to disable progress output.

Tables are written under `group_analysis/ROI_stats/t1_space/` for uncorrected
T1-space images and under `group_analysis/ROI_stats/t1_space/mri_unbias_deg2/`
for corrected images. Each CSV preserves the metadata session rows and starts
with `RowID`, `SubjectID`, and `SessionID`. Missing images, segmentations, ROIs, or
incompatible grids are represented as `NaN`.

For each segmentation and each available `t1`, `t2`, and `pd` image, the
command creates `median`, `mean`, `mad`, and `std` tables. Here `mad` is the
median absolute deviation. It also creates one `volume` table per segmentation;
volume values are in mm3. Volume tables under corrected-image folders are
symlinks to the corresponding `t1_space` volume tables because volume does not
depend on image intensity. For example:

```text
group_analysis/ROI_stats/t1_space/
  fslfirst_t1_median.csv
  fslfirst_t2_std.csv
  fslfirst_volume.csv
  mri_unbias_deg2/
    fslfirst_t1_median.csv
```

The command includes FreeSurfer `aparc.DKTatlas+aseg`, SynthStrip, SynthSeg,
FSL FIRST, eroded FSL FIRST, DBSegment, the DBSegment whole GP/SN derivative, and
MASSP. ROI columns are named by ROI name, with hyphens converted to
underscores. For FreeSurfer
`aparc.DKTatlas+aseg`, names are read from
`$FREESURFER_HOME/FreeSurferColorLUT.txt` when available. A different LUT can
be supplied with `--freesurfer-lut PATH`. The remaining stable lookup tables
are built into this package.

## Output Structure

The infrastructure step writes outputs under `OUTPUT_ROOT`:

```text
OUTPUT_ROOT/
  ppmi_config.json
  ppmi_metadata.csv
  cohort_tables/
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
      T1.nii.gz
      derivatives/
        GP_SN_seg.nii.gz
    synthseg/
      synthseg.nii.gz
    massp/
      ahead2sub_ants/
        ahead_med_qr1_2ref.nii.gz
        massp2021-parcellation_decade-61to80_2ref.nii.gz
        ahead2sub_0GenericAffine.mat
        ahead2sub_1Warp.nii.gz
        ahead2sub_1InverseWarp.nii.gz
        README.txt
    freesurfer/
      t1_space_outputs/
  mri_unbias_deg2/
    README.txt
    wm_mask.nii.gz
    wm_mask_eroded.nii.gz
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
- `segmentation/`: FSL FIRST, DBSegment, SynthSeg, MASSP, FreeSurfer, and segmentation utilities
