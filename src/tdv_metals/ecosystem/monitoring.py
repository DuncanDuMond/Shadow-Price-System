"""Optional Evidently report over aligned numeric research features."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pandas as pd

from ._optional import require_module


def evidently_drift_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    columns: Sequence[str] | None = None,
) -> dict[str, object]:
    """Compare two batches; return a serializable report without external writes.

    Columns default to numeric columns shared by both frames. Time keys and
    identifiers should be excluded because distribution tests are not useful
    for those values.
    """
    if reference.empty or current.empty:
        raise ValueError("reference and current must both contain rows")
    if columns is None:
        chosen = [column for column in reference.columns if column in current.columns
                  and pd.api.types.is_numeric_dtype(reference[column])
                  and pd.api.types.is_numeric_dtype(current[column])]
    else:
        chosen = list(columns)
    if not chosen or len(chosen) != len(set(chosen)):
        raise ValueError("provide at least one unique numeric feature column")
    for column in chosen:
        if column not in reference or column not in current:
            raise ValueError(f"drift column {column} is missing from one batch")
        if not pd.api.types.is_numeric_dtype(reference[column]) or not pd.api.types.is_numeric_dtype(current[column]):
            raise ValueError(f"drift column {column} must be numeric in both batches")
    evidently = require_module("evidently", "evidently")
    presets = require_module("evidently.presets", "evidently")
    report = evidently.Report([presets.DataDriftPreset(columns=chosen)])
    snapshot = report.run(current_data=current[chosen], reference_data=reference[chosen])
    return {
        "reference_rows": len(reference),
        "current_rows": len(current),
        "columns": chosen,
        "current_missing": {column: int(current[column].isna().sum()) for column in chosen},
        "reference_missing": {column: int(reference[column].isna().sum()) for column in chosen},
        "evidently": json.loads(snapshot.json()),
    }
