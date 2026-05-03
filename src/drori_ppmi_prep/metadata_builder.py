from __future__ import annotations

from pathlib import Path
import re
import pandas as pd


def build_ppmi_metadata_csv(
    input_dir: str | Path,
    output_csv: str | Path,
    file_pattern: str = "*.csv",
) -> pd.DataFrame:
    input_dir = Path(input_dir)
    output_csv = Path(output_csv)

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    csv_files = sorted(input_dir.glob(file_pattern))
    if not csv_files:
        raise FileNotFoundError(
            f"No CSV files matching pattern '{file_pattern}' found in: {input_dir}"
        )

    frames = []
    for csv_file in csv_files:
        df = pd.read_csv(csv_file)
        frames.append(df)

    data = pd.concat(frames, ignore_index=True)

    required_columns = [
        "Subject ID",
        "Sex",
        "Weight",
        "Research Group",
        "Visit",
        "Study Date",
        "Age",
        "Description",
        "Imaging Protocol",
        "Image ID",
    ]
    missing = [col for col in required_columns if col not in data.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    def extract_weighting(protocol: object):
        if pd.isna(protocol):
            return None
        match = re.search(r"(?:^|;)Weighting=([^;]+)", str(protocol), flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip().upper()

    data["Weighting"] = data["Imaging Protocol"].apply(extract_weighting)
    data = data[data["Weighting"].isin({"T1", "T2", "PD"})].copy()

    data["Image ID"] = data["Image ID"].astype(str)

    study_dates = pd.to_datetime(data["Study Date"], errors="coerce")
    data["Study Date"] = study_dates.dt.strftime("%Y-%m-%d")
    data.loc[study_dates.isna(), "Study Date"] = pd.NA

    group_keys = ["Subject ID", "Visit"]

    source_base_columns = [
        "Subject ID",
        "Sex",
        "Weight",
        "Research Group",
        "Visit",
        "Study Date",
        "Age",
    ]

    output_base_columns = [
        "SubjectID",
        "Sex",
        "Weight",
        "ResearchGroup",
        "Visit",
        "StudyDate",
        "Age",
    ]

    base_col_map = dict(zip(source_base_columns, output_base_columns))
    weightings = ["T1", "T2", "PD"]

    rows = []

    for _, group in data.groupby(group_keys, sort=True):
        row = {}

        for src_col, out_col in base_col_map.items():
            non_null = group[src_col].dropna()
            row[out_col] = non_null.iloc[0] if not non_null.empty else pd.NA

        for weighting in weightings:
            sub = (
                group[group["Weighting"] == weighting]
                .sort_values(by=["Study Date", "Image ID"], kind="stable")
                .reset_index(drop=True)
            )

            for i, (_, scan) in enumerate(sub.iterrows()):
                image_id = scan["Image ID"]
                description = scan["Description"] if pd.notna(scan["Description"]) else ""

                if i == 0:
                    row[weighting] = image_id
                    if weighting in {"T1", "T2"}:
                        row[f"{weighting}_Description"] = description
                else:
                    row[f"{weighting}_{i}"] = image_id
                    if weighting in {"T1", "T2"}:
                        row[f"{weighting}_{i}_Description"] = description

        rows.append(row)

    metadata_df = pd.DataFrame(rows)

    max_extra_index = 0
    for col in metadata_df.columns:
        m = re.fullmatch(r"(T1|T2|PD)_(\d+)", col)
        if m and not col.endswith("_Description"):
            max_extra_index = max(max_extra_index, int(m.group(2)))

    ordered_cols = list(output_base_columns)

    ordered_cols += ["T1", "T2", "PD"]
    ordered_cols += ["T1_Description", "T2_Description"]

    for i in range(1, max_extra_index + 1):
        ordered_cols += [f"T1_{i}", f"T2_{i}", f"PD_{i}"]
        ordered_cols += [f"T1_{i}_Description", f"T2_{i}_Description"]

    for col in ordered_cols:
        if col not in metadata_df.columns:
            if re.fullmatch(r"(T1|T2|PD)(?:_\d+)?", col):
                metadata_df[col] = 0
            elif re.fullmatch(r"(T1|T2)(?:_\d+)?_Description", col):
                metadata_df[col] = ""
            else:
                metadata_df[col] = pd.NA

    metadata_df = metadata_df.loc[:, ordered_cols]

    image_cols = [
        c for c in metadata_df.columns
        if re.fullmatch(r"(T1|T2|PD)(?:_\d+)?", c)
    ]
    desc_cols = [
        c for c in metadata_df.columns
        if re.fullmatch(r"(T1|T2)(?:_\d+)?_Description", c)
    ]

    metadata_df[image_cols] = metadata_df[image_cols].fillna(0)
    metadata_df[desc_cols] = metadata_df[desc_cols].fillna("")

    metadata_df = metadata_df.sort_values(
        by=["SubjectID", "StudyDate"],
        kind="stable"
    ).reset_index(drop=True)

    metadata_df.insert(0, "RowID", range(1, len(metadata_df) + 1))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    metadata_df.to_csv(output_csv, index=False)

    return metadata_df
