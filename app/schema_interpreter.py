import os
import json
import httpx
from typing import Optional

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = "claude-sonnet-4-20250514"

SYSTEM_PROMPT = """You are a dataset schema extractor for SynGen, a synthetic data platform.
The user describes a dataset in natural language. Extract a structured JSON schema ONLY.
Output ONLY valid JSON — no markdown fences, no prose, no explanation.

Output this exact structure:
{
  "name": "descriptive dataset name",
  "rows": <number from prompt, default 500>,
  "attributes": [
    {
      "name": "snake_case_field_name",
      "type": "integer|float|categorical|boolean|name|email|phone|company|city|uuid|date",
      "distribution": "normal|uniform|lognormal|poisson|exponential",
      "mean": <number>,
      "std": <number>,
      "min": <number>,
      "max": <number>,
      "values": ["val1", "val2"],
      "probabilities": [0.6, 0.4],
      "true_rate": <0.0-1.0 for boolean>,
      "start": "2020-01-01",
      "end": "2024-12-31"
    }
  ],
  "relationships": [
    {
      "from": "field_a",
      "to": "field_b",
      "direction": "positive|negative",
      "strength": "weak|moderate|strong",
      "note": "plain english explanation"
    }
  ]
}

Rules:
- type "integer": use distribution (normal/uniform/poisson), mean, std, min, max
- type "float": same as integer but decimal output
- type "categorical": must have values list; optionally probabilities
- type "boolean": use true_rate (0.0-1.0)
- type "name|email|phone|company|city|uuid": no distribution needed
- type "date": use start/end ISO strings
- rows: extract from prompt; if unspecified, use 500
- Only add relationships that are explicitly stated or strongly implied
- Output ONLY the JSON object
"""


async def interpret_prompt(prompt: str, rows: Optional[int] = None) -> dict:
    if not ANTHROPIC_API_KEY:
        return _fallback_schema(prompt, rows)

    user_msg = prompt
    if rows and rows != 500:
        user_msg = f"{prompt}\n\nNote: Generate {rows} rows."

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 2000,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": user_msg}],
            },
        )
        response.raise_for_status()
        data = response.json()
        text = "".join(
            block.get("text", "") for block in data.get("content", [])
        ).strip()
        text = text.replace("```json", "").replace("```", "").strip()
        schema = json.loads(text)
        if rows:
            schema["rows"] = rows
        return schema


def _fallback_schema(prompt: str, rows: Optional[int] = None) -> dict:
    """Returns a demo schema when no API key is configured."""
    return {
        "name": "Demo Customer Dataset",
        "rows": rows or 500,
        "attributes": [
            {"name": "customer_id", "type": "uuid"},
            {"name": "name", "type": "name"},
            {"name": "email", "type": "email"},
            {"name": "age", "type": "integer", "distribution": "normal", "mean": 35, "std": 10, "min": 18, "max": 80},
            {"name": "gender", "type": "categorical", "values": ["Male", "Female", "Non-binary"], "probabilities": [0.48, 0.48, 0.04]},
            {"name": "city", "type": "city"},
            {"name": "annual_income", "type": "float", "distribution": "lognormal", "mean": 60000, "std": 20000, "min": 20000},
            {"name": "total_purchases", "type": "integer", "distribution": "poisson", "mean": 12, "min": 0},
            {"name": "churn", "type": "boolean", "true_rate": 0.15},
        ],
        "relationships": [
            {"from": "annual_income", "to": "total_purchases", "direction": "positive", "strength": "moderate", "note": "Higher income → more purchases"},
            {"from": "total_purchases", "to": "churn", "direction": "negative", "strength": "strong", "note": "More purchases → less likely to churn"},
        ],
    }
