# File: data_store.py
# Author Jan Wrede
# Copyright (c) 2025 nudgebg
# Licensed under the MIT License. See LICENSE file for details.
import os
import shutil
import pandas as pd

ALL_DATA_TYPES = ["cgm", "bolus", "basal", "age", "carbs"]


def save(df: pd.DataFrame, study_name: str, data_type: str, base_path: str) -> None:
    """Write a DataFrame to the partitioned Parquet store.

    Data is written to:
        base_path/<data_type>/study_name=<study_name>/patient_id=<id>/*.parquet

    Args:
        df:          DataFrame to save. Must contain a 'patient_id' column.
        study_name:  Study identifier (e.g. "Flair"). Written as a partition column.
        data_type:   One of 'cgm', 'bolus', 'basal', 'age', 'carbs'
        base_path:   Root output directory (e.g. "data/out").
    """
    df = df.assign(study_name=study_name)
    df.to_parquet(
        os.path.join(base_path, data_type),
        index=False,
        partition_cols=["study_name", "patient_id"],
        engine="pyarrow",
        compression="snappy",
        existing_data_behavior="delete_matching",
    )


def cleanup(study_name: str, base_path: str, data_types: list[str] | None = None) -> list[str]:
    """Remove existing output for a study to ensure a clean write.

    Deletes:
        base_path/<data_type>/study_name=<study_name>/

    Args:
        study_name:  Study whose output should be removed.
        base_path:   Root output directory (e.g. "data/out").
        data_types:  Data types to remove. Defaults to all four types.

    Returns:
        List of directory paths that were actually removed.
    """
    dts = data_types if data_types is not None else ALL_DATA_TYPES
    removed = []
    for dt in dts:
        d = os.path.join(base_path, dt, f"study_name={study_name}")
        if os.path.isdir(d):
            shutil.rmtree(d)
            removed.append(d)
    return removed


def load(
    base_path: str,
    data_types: list[str] | None = None,
    studies: list[str] | str | None = None,
    patients: list[str] | str | None = None,
    categorical_keys: bool = False,
) -> dict[str, pd.DataFrame]:
    """Load data from the partitioned Parquet store.

    Reads from:
        base_path/<data_type>/study_name=<X>/patient_id=<Z>/*.parquet

    The returned DataFrames include a 'study_name' column populated from the
    Hive partition. Each data type has its own schema:
        cgm:   patient_id (str), study_name (str), datetime (datetime64), cgm (float, mg/dL)
        bolus: patient_id (str), study_name (str), datetime (datetime64), bolus (float, U),
               delivery_duration (timedelta64)
        basal: patient_id (str), study_name (str), datetime (datetime64), basal_rate (float, U/hr)
        age:   patient_id (str), study_name (str), age (int)
        carbs: patient_id (str), study_name (str), datetime (datetime64), carbs (float, g),

    Args:
        base_path:   Root output directory (e.g. "data/out").
        data_types:  Data types to load. Defaults to all four ('cgm', 'bolus', 'basal', 'age', 'carbs').
        studies:     Filter by study name(s). None loads all studies.
        patients:    Filter by patient ID(s). None loads all patients.
        categorical_keys: Keep study_name and patient_id as the Categoricals pyarrow
                     returns instead of casting them to str. Uses far less memory on large
                     studies, but the categories include studies and patients that were
                     filtered out (use observed=True in groupby), and patient_id categories
                     may not be strings.

    Returns:
        Dict mapping data_type → DataFrame. Always returns a dict, even for a single data type.
    """
    dts = data_types if data_types is not None else ALL_DATA_TYPES

    filters = []
    if studies is not None:
        filters.append(("study_name", "in", [studies] if isinstance(studies, str) else studies))
    if patients is not None:
        filters.append(("patient_id", "in", [patients] if isinstance(patients, str) else patients))

    result = {}
    for dt in dts:
        df = pd.read_parquet(os.path.join(base_path, dt), filters=filters or None)
        # Partition columns are Categorical by default from pyarrow; cast to string to avoid use errors
        if not categorical_keys:
            for col in ("study_name", "patient_id"):
                if col in df.columns:
                    df[col] = df[col].astype(str)
        result[dt] = df
    return result
