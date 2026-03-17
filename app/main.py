from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import io
from dotenv import load_dotenv

load_dotenv()

try:
    from app.schema_interpreter import interpret_prompt
    from app.data_engine import DataEngine
    from app.exporters import export_csv, export_json, export_excel, export_parquet
except ModuleNotFoundError:
    from schema_interpreter import interpret_prompt
    from data_engine import DataEngine
    from exporters import export_csv, export_json, export_excel, export_parquet

app = FastAPI(title="SynGen API", version="2.0.0", docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


# ── Pydantic Models ──────────────────────────────────────────
# Pydantic v2 reserves "schema" as a BaseModel attribute.
# Use alias="schema" so the JSON API still accepts {"schema": ...}
# but internally we store it as dataset_schema to avoid the conflict.

class PromptRequest(BaseModel):
    prompt: str
    rows: Optional[int] = 500


class GenerateRequest(BaseModel):
    dataset_schema: Dict[str, Any] = Field(..., alias="schema")
    rows: Optional[int] = 500
    model_config = {"populate_by_name": True}


class ExportRequest(BaseModel):
    dataset_schema: Dict[str, Any] = Field(..., alias="schema")
    rows: Optional[int] = 500
    export_format: Optional[str] = Field("csv", alias="format")
    model_config = {"populate_by_name": True}


class EditSchemaRequest(BaseModel):
    dataset_schema: Dict[str, Any] = Field(..., alias="schema")
    field_index: int
    field: Dict[str, Any]
    model_config = {"populate_by_name": True}


class AddFieldRequest(BaseModel):
    dataset_schema: Dict[str, Any] = Field(..., alias="schema")
    field: Dict[str, Any]
    model_config = {"populate_by_name": True}


class RemoveFieldRequest(BaseModel):
    dataset_schema: Dict[str, Any] = Field(..., alias="schema")
    field_index: int
    model_config = {"populate_by_name": True}


# ── Routes ──────────────────────────────────────────

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/interpret")
async def interpret(req: PromptRequest):
    try:
        result = interpret_prompt(req.prompt, req.rows)
        return {"schema": result, "model": "llama-3.3-70b-versatile (Groq)"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate")
async def generate(req: GenerateRequest):
    try:
        s = req.dataset_schema
        engine = DataEngine(s)
        rows = req.rows or s.get("rows", 500)
        data = engine.generate(rows)
        stats = engine.compute_stats(data)
        return {
            "preview":    data[:15],
            "stats":      stats,
            "total_rows": len(data),
            "columns":    list(data[0].keys()) if data else [],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/{fmt}")
async def export(fmt: str, req: ExportRequest):
    if fmt not in ("csv", "json", "excel", "parquet"):
        raise HTTPException(status_code=400, detail="Unsupported format.")
    try:
        s = req.dataset_schema
        engine = DataEngine(s)
        rows = req.rows or s.get("rows", 500)
        data = engine.generate(rows)
        dataset_name = s.get("name", "SynGen")

        if fmt == "csv":
            content, mime, ext = export_csv(data), "text/csv", "csv"
        elif fmt == "json":
            content, mime, ext = export_json(data), "application/json", "json"
        elif fmt == "excel":
            content = export_excel(data, dataset_name)
            mime, ext = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"
        else:
            content, mime, ext = export_parquet(data), "application/octet-stream", "parquet"

        safe_name = dataset_name.replace(" ", "_").replace("/", "-")[:40]
        return StreamingResponse(
            io.BytesIO(content), media_type=mime,
            headers={"Content-Disposition": f'attachment; filename="{safe_name}.{ext}"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/schema/add-field")
async def add_field(req: AddFieldRequest):
    s = req.dataset_schema
    s.setdefault("attributes", []).append(req.field)
    return {"schema": s}


@app.post("/api/schema/remove-field")
async def remove_field(req: RemoveFieldRequest):
    s = req.dataset_schema
    attrs = s.get("attributes", [])
    if 0 <= req.field_index < len(attrs):
        attrs.pop(req.field_index)
    return {"schema": s}


@app.post("/api/schema/edit-field")
async def edit_field(req: EditSchemaRequest):
    s = req.dataset_schema
    attrs = s.get("attributes", [])
    if 0 <= req.field_index < len(attrs):
        attrs[req.field_index] = req.field
    return {"schema": s}


@app.get("/api/examples")
async def get_examples():
    return {"examples": [
        {"label": "E-commerce Customers", "icon": "🛒",
         "prompt": "Generate 1000 e-commerce customer records with customer_id, name, email, age, gender, city, country, annual_income, total_purchases, avg_order_value, signup_date, is_premium, and churn. Higher income customers make more purchases. Active buyers are less likely to churn."},
        {"label": "HR Employees", "icon": "👥",
         "prompt": "Create 500 employee records with employee_id, name, email, department, job_title, years_of_experience, salary, performance_score, is_remote, hire_date, and attrition. Salary increases with experience. High performers are less likely to leave."},
        {"label": "Financial Transactions", "icon": "💳",
         "prompt": "Generate 2000 financial transactions with transaction_id, amount, category, merchant, customer_id, timestamp, payment_method, status, and is_fraudulent. Fraud rate is about 2 percent. Fraudulent transactions tend to have higher amounts."},
        {"label": "Healthcare Patients", "icon": "🏥",
         "prompt": "Generate 800 patient records with patient_id, name, age, gender, blood_type, diagnosis, admission_date, discharge_date, treatment_cost, insurance_type, and readmitted. Older patients have higher treatment costs."},
        {"label": "IoT Sensor Readings", "icon": "📡",
         "prompt": "Create 5000 IoT sensor readings with device_id, timestamp, temperature, humidity, pressure, battery_level, signal_strength, location, and alert_triggered. Alerts trigger when temperature is very high or battery is low."},
        {"label": "Social Media Posts", "icon": "📱",
         "prompt": "Generate 1200 social media posts with post_id, user_id, platform, content_type, likes, comments, shares, reach, posted_at, and is_viral. Viral posts have very high reach and engagement."},
    ]}


@app.get("/api/field-types")
async def field_types():
    return {"types": [
        {"value": "integer",     "label": "Integer",        "group": "Numeric"},
        {"value": "float",       "label": "Float",          "group": "Numeric"},
        {"value": "categorical", "label": "Categorical",    "group": "Categorical"},
        {"value": "boolean",     "label": "Boolean",        "group": "Categorical"},
        {"value": "name",        "label": "Full Name",      "group": "Faker"},
        {"value": "email",       "label": "Email",          "group": "Faker"},
        {"value": "phone",       "label": "Phone",          "group": "Faker"},
        {"value": "company",     "label": "Company",        "group": "Faker"},
        {"value": "city",        "label": "City",           "group": "Faker"},
        {"value": "country",     "label": "Country",        "group": "Faker"},
        {"value": "uuid",        "label": "UUID",           "group": "Identifier"},
        {"value": "date",        "label": "Date",           "group": "Temporal"},
        {"value": "url",         "label": "URL",            "group": "Web"},
        {"value": "ip_address",  "label": "IP Address",     "group": "Web"},
        {"value": "text",        "label": "Text (sentence)", "group": "Text"},
        {"value": "color",       "label": "Color Hex",      "group": "Misc"},
    ]}


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}
