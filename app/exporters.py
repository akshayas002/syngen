import csv
import json
import io
from typing import Any

import pandas as pd


def _to_dataframe(data: list) -> pd.DataFrame:
    """Convert list of dicts to DataFrame, coercing booleans to strings for Excel safety."""
    return pd.DataFrame(data)


def export_csv(data: list) -> bytes:
    if not data:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(data[0].keys()), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")


def export_json(data: list) -> bytes:
    return json.dumps(data, indent=2, default=str).encode("utf-8")


def export_excel(data: list, sheet_name: str = "SynGen Data") -> bytes:
    if not data:
        return b""
    df = _to_dataframe(data)
    # Convert boolean columns to Yes/No so Excel renders them cleanly
    for col in df.columns:
        if df[col].dtype == object:
            pass  # already string-like
        elif str(df[col].dtype) == "bool":
            df[col] = df[col].map({True: "Yes", False: "No"})

    safe_sheet = sheet_name[:31]  # Excel sheet name limit
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=safe_sheet)
        ws = writer.sheets[safe_sheet]
        for col_cells in ws.columns:
            max_len = max(
                (len(str(cell.value)) if cell.value is not None else 0)
                for cell in col_cells
            )
            ws.column_dimensions[col_cells[0].column_letter].width = min(max_len + 2, 40)
    return buf.getvalue()


def export_parquet(data: list) -> bytes:
    if not data:
        return b""
    df = _to_dataframe(data)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()
