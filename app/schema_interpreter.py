import os
import json
import re
from typing import Optional

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """You are SynGen's dataset schema extractor. The user describes a dataset in natural language.
Output ONLY a valid JSON object — no markdown fences, no explanation, no text before or after the JSON.

Required JSON structure:
{
  "name": "Human-readable dataset name",
  "domain": "ecommerce|finance|hr|healthcare|education|iot|social|custom",
  "rows": <integer, from prompt or default 500>,
  "attributes": [
    {
      "name": "snake_case_name",
      "label": "Human readable label",
      "type": "integer|float|categorical|boolean|name|email|phone|company|city|country|uuid|date|text|ip_address|url|color",
      "distribution": "normal|uniform|lognormal|poisson|exponential|beta|gamma|zipf",
      "mean": <number>,
      "std": <number>,
      "min": <number>,
      "max": <number>,
      "values": ["val1","val2"],
      "weights": [0.6, 0.4],
      "true_rate": <0.0-1.0>,
      "start": "YYYY-MM-DD",
      "end": "YYYY-MM-DD",
      "nullable": <0.0-0.2>,
      "unique": <boolean>,
      "prefix": "e.g. TXN-",
      "decimals": <integer>
    }
  ],
  "relationships": [
    {
      "from": "field_a",
      "to": "field_b",
      "direction": "positive|negative",
      "strength": "weak|moderate|strong",
      "note": "plain english"
    }
  ],
  "constraints": [
    {
      "type": "conditional",
      "if_field": "field_name",
      "if_value": "value",
      "then_field": "other_field",
      "then_value": "forced_value",
      "note": "description"
    }
  ]
}

Rules:
- Extract row count from prompt; default 500
- Use realistic means/stds for each domain
- Use lognormal for income/prices, poisson for counts, normal for age/scores
- domain must be one of the listed values
- Output ONLY the JSON object, nothing else"""


def _clean_json_text(text: str) -> str:
    """Strip markdown fences and any leading/trailing non-JSON text."""
    text = text.strip()
    # Remove ```json ... ``` or ``` ... ```
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Find the outermost JSON object
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start:end + 1]
    return text


def interpret_prompt(prompt: str, rows: Optional[int] = None) -> dict:
    if not GROQ_API_KEY:
        return _fallback_schema(rows)

    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")

    client = Groq(api_key=GROQ_API_KEY)
    user_msg = prompt
    if rows:
        user_msg += f"\n\nUse exactly {rows} rows."

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_msg},
            ],
            temperature=0.2,
            max_tokens=2500,
        )
    except Exception as e:
        raise RuntimeError(f"Groq API call failed: {e}")

    raw_text = response.choices[0].message.content or ""
    clean    = _clean_json_text(raw_text)

    try:
        schema = json.loads(clean)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"LLM returned invalid JSON: {e}\n\nRaw response:\n{raw_text[:500]}")

    # Always honour the UI row count if provided
    if rows:
        schema["rows"] = rows

    # Ensure required keys exist
    schema.setdefault("attributes", [])
    schema.setdefault("relationships", [])
    schema.setdefault("constraints", [])

    return schema


def _fallback_schema(rows: Optional[int] = None) -> dict:
    """Demo schema used when GROQ_API_KEY is not set."""
    return {
        "name": "E-commerce Customer Dataset",
        "domain": "ecommerce",
        "rows": rows or 500,
        "attributes": [
            {"name": "customer_id",    "label": "Customer ID",        "type": "uuid",        "unique": True},
            {"name": "name",           "label": "Full Name",          "type": "name"},
            {"name": "email",          "label": "Email",              "type": "email"},
            {"name": "age",            "label": "Age",                "type": "integer",  "distribution": "normal",    "mean": 34,    "std": 10,    "min": 18, "max": 75},
            {"name": "gender",         "label": "Gender",             "type": "categorical", "values": ["Male", "Female", "Non-binary"], "weights": [0.48, 0.48, 0.04]},
            {"name": "city",           "label": "City",               "type": "city"},
            {"name": "country",        "label": "Country",            "type": "country"},
            {"name": "annual_income",  "label": "Annual Income ($)",  "type": "float",    "distribution": "lognormal", "mean": 65000, "std": 25000, "min": 15000, "decimals": 2},
            {"name": "total_purchases","label": "Total Purchases",    "type": "integer",  "distribution": "poisson",   "mean": 14,    "min": 0},
            {"name": "avg_order_value","label": "Avg Order Value ($)","type": "float",    "distribution": "lognormal", "mean": 85,    "std": 40,    "min": 10, "decimals": 2},
            {"name": "signup_date",    "label": "Signup Date",        "type": "date",     "start": "2019-01-01", "end": "2024-12-31"},
            {"name": "is_premium",     "label": "Premium Member",     "type": "boolean",  "true_rate": 0.22},
            {"name": "churn",          "label": "Churned",            "type": "boolean",  "true_rate": 0.14},
        ],
        "relationships": [
            {"from": "annual_income",   "to": "total_purchases", "direction": "positive", "strength": "moderate", "note": "Higher income leads to more purchases"},
            {"from": "total_purchases", "to": "avg_order_value", "direction": "positive", "strength": "weak",     "note": "Frequent buyers tend to spend more per order"},
            {"from": "total_purchases", "to": "churn",           "direction": "negative", "strength": "strong",   "note": "Active buyers are less likely to churn"},
            {"from": "annual_income",   "to": "is_premium",      "direction": "positive", "strength": "moderate", "note": "Higher earners are more likely to subscribe"},
        ],
        "constraints": [],
    }
