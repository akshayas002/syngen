import csv
import json
import io
import pandas as pd


def export_csv(data: list[dict]) -> bytes:
    if not data:
        return b""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=data[0].keys())
    writer.writeheader()
    writer.writerows(data)
    return buf.getvalue().encode("utf-8")


def export_json(data: list[dict]) -> bytes:
    return json.dumps(data, indent=2, default=str).encode("utf-8")


def export_excel(data: list[dict]) -> bytes:
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="SynGen Data")
        ws = writer.sheets["SynGen Data"]
        for col in ws.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)
    return buf.getvalue()


def export_parquet(data: list[dict]) -> bytes:
    df = pd.DataFrame(data)
    buf = io.BytesIO()
    df.to_parquet(buf, index=False, engine="pyarrow")
    return buf.getvalue()
