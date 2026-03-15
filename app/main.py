from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import io
import json

from app.schema_interpreter import interpret_prompt
from app.data_generator import DataGenerator
from app.exporters import export_csv, export_json, export_excel, export_parquet

app = FastAPI(title="SynGen API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class PromptRequest(BaseModel):
    prompt: str
    rows: Optional[int] = 500


class GenerateRequest(BaseModel):
    schema: dict
    rows: Optional[int] = 500
    format: Optional[str] = "csv"


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/interpret")
async def interpret(req: PromptRequest):
    try:
        schema = await interpret_prompt(req.prompt, req.rows)
        return {"schema": schema}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    try:
        gen = DataGenerator(req.schema)
        data = gen.generate(req.rows)
        preview = data[:10]
        stats = gen.compute_stats(data)
        return {
            "preview": preview,
            "stats": stats,
            "total_rows": len(data),
            "columns": list(data[0].keys()) if data else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/{fmt}")
async def export(fmt: str, req: GenerateRequest):
    if fmt not in ("csv", "json", "excel", "parquet"):
        raise HTTPException(status_code=400, detail="Unsupported format")
    try:
        gen = DataGenerator(req.schema)
        data = gen.generate(req.rows)

        if fmt == "csv":
            content = export_csv(data)
            media_type = "text/csv"
            filename = "syngen_dataset.csv"
        elif fmt == "json":
            content = export_json(data)
            media_type = "application/json"
            filename = "syngen_dataset.json"
        elif fmt == "excel":
            content = export_excel(data)
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "syngen_dataset.xlsx"
        elif fmt == "parquet":
            content = export_parquet(data)
            media_type = "application/octet-stream"
            filename = "syngen_dataset.parquet"

        return StreamingResponse(
            io.BytesIO(content),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/examples")
async def get_examples():
    return {
        "examples": [
            {
                "label": "E-commerce customers",
                "prompt": "Generate a dataset of 1000 e-commerce customers with age, gender, annual_income, city, total_purchases, and churn. Higher income customers should have more purchases. Churn is more likely for customers with few purchases.",
            },
            {
                "label": "HR employees",
                "prompt": "Create 500 employee records with name, department, years_of_experience, salary, performance_score, and is_remote. Salary increases with experience. Performance follows a normal distribution.",
            },
            {
                "label": "Financial transactions",
                "prompt": "Generate 2000 financial transactions with transaction_id, amount, category (food, transport, entertainment, utilities, shopping), merchant, and is_fraudulent. Fraud rate is about 2% and fraudulent transactions tend to have higher amounts.",
            },
            {
                "label": "University students",
                "prompt": "Create 800 student records with student_id, name, age, gpa, study_hours_per_week, major, and scholarship. Higher study hours correlate with higher gpa. Scholarship is awarded to top students.",
            },
        ]
    }
