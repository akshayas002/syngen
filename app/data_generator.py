import numpy as np
import random
import uuid
from datetime import datetime, timedelta
from faker import Faker
from typing import Any

fake = Faker()
rng = np.random.default_rng()

DEPARTMENTS = ["Engineering", "Marketing", "Sales", "Finance", "HR", "Operations", "Product", "Legal", "Design", "Support"]
MAJORS = ["Computer Science", "Data Science", "Mathematics", "Physics", "Business", "Economics", "Psychology", "Biology", "Engineering", "Statistics"]
CATEGORIES = ["Food & Dining", "Transportation", "Entertainment", "Utilities", "Shopping", "Healthcare", "Travel", "Education"]


class DataGenerator:
    def __init__(self, schema: dict):
        self.schema = schema
        self.attributes = schema.get("attributes", [])
        self.relationships = schema.get("relationships", [])

    def generate(self, rows: int) -> list[dict]:
        data = []
        for _ in range(rows):
            row = self._generate_row()
            data.append(row)
        self._apply_relationships(data)
        return data

    def _generate_row(self) -> dict:
        row = {}
        name_val = None
        for attr in self.attributes:
            val = self._sample(attr, name_val)
            if attr["type"] == "name":
                name_val = val
            row[attr["name"]] = val
        return row

    def _sample(self, attr: dict, name_val: str | None = None) -> Any:
        t = attr.get("type", "integer")

        if t == "name":
            return fake.name()
        if t == "email":
            if name_val:
                clean = name_val.lower().replace(" ", ".").replace("'", "")
                return f"{clean}@{random.choice(['gmail.com','yahoo.com','outlook.com','company.io'])}"
            return fake.email()
        if t == "phone":
            return fake.phone_number()
        if t == "company":
            return fake.company()
        if t == "city":
            return fake.city()
        if t == "uuid":
            return str(uuid.uuid4())
        if t == "date":
            start = datetime.fromisoformat(attr.get("start", "2020-01-01"))
            end = datetime.fromisoformat(attr.get("end", "2024-12-31"))
            delta = (end - start).days
            return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")
        if t == "boolean":
            return random.random() < attr.get("true_rate", 0.5)
        if t == "categorical":
            values = attr.get("values", ["A", "B"])
            probs = attr.get("probabilities")
            if probs and len(probs) == len(values):
                return random.choices(values, weights=probs, k=1)[0]
            return random.choice(values)

        dist = attr.get("distribution", "normal")
        mean = attr.get("mean", 50)
        std = attr.get("std", 15)
        lo = attr.get("min")
        hi = attr.get("max")

        if dist == "uniform":
            val = rng.uniform(lo if lo is not None else 0, hi if hi is not None else 100)
        elif dist == "lognormal":
            mu = np.log(max(mean, 1))
            sigma = std / max(mean, 1) if mean else 0.5
            sigma = min(sigma, 1.5)
            val = rng.lognormal(mu, sigma)
        elif dist == "poisson":
            val = rng.poisson(max(mean, 0.1))
        elif dist == "exponential":
            val = rng.exponential(max(mean, 1))
        else:
            val = rng.normal(mean, max(std, 0.01))

        if lo is not None:
            val = max(lo, val)
        if hi is not None:
            val = min(hi, val)

        return int(round(val)) if t == "integer" else round(float(val), 2)

    def _apply_relationships(self, data: list[dict]):
        attr_map = {a["name"]: a for a in self.attributes}
        for rel in self.relationships:
            frm = rel.get("from")
            to = rel.get("to")
            if frm not in attr_map or to not in attr_map:
                continue
            from_attr = attr_map[frm]
            to_attr = attr_map[to]
            numeric_types = {"integer", "float"}
            if from_attr["type"] not in numeric_types:
                continue

            from_vals = [r[frm] for r in data if isinstance(r.get(frm), (int, float))]
            if not from_vals:
                continue
            min_f, max_f = min(from_vals), max(from_vals)
            rng_f = max_f - min_f or 1

            strength_map = {"strong": 0.75, "moderate": 0.5, "weak": 0.25}
            strength = strength_map.get(rel.get("strength", "moderate"), 0.5)
            direction = 1 if rel.get("direction", "positive") == "positive" else -1

            to_vals = [r[to] for r in data if isinstance(r.get(to), (int, float))]
            if to_attr["type"] in numeric_types and to_vals:
                min_t, max_t = min(to_vals), max(to_vals)
                rng_t = max_t - min_t or 1
                for row in data:
                    if not isinstance(row.get(frm), (int, float)):
                        continue
                    norm = (row[frm] - min_f) / rng_f
                    noise = random.random()
                    blend = strength * norm + (1 - strength) * noise
                    if direction < 0:
                        blend = 1 - blend
                    new_val = min_t + blend * rng_t
                    if to_attr["type"] == "integer":
                        row[to] = int(round(new_val))
                    else:
                        row[to] = round(float(new_val), 2)

            elif to_attr["type"] == "boolean":
                true_rate = to_attr.get("true_rate", 0.5)
                for row in data:
                    if not isinstance(row.get(frm), (int, float)):
                        continue
                    norm = (row[frm] - min_f) / rng_f
                    noise = random.random()
                    blend = strength * norm + (1 - strength) * noise
                    threshold = 1 - true_rate if direction > 0 else true_rate
                    row[to] = blend > threshold

    def compute_stats(self, data: list[dict]) -> dict:
        stats = {}
        if not data:
            return stats
        for attr in self.attributes:
            name = attr["name"]
            vals = [r[name] for r in data if r.get(name) is not None]
            if not vals:
                continue
            if attr["type"] in ("integer", "float"):
                arr = np.array(vals, dtype=float)
                stats[name] = {
                    "type": attr["type"],
                    "mean": round(float(np.mean(arr)), 2),
                    "std": round(float(np.std(arr)), 2),
                    "min": round(float(np.min(arr)), 2),
                    "max": round(float(np.max(arr)), 2),
                    "median": round(float(np.median(arr)), 2),
                }
            elif attr["type"] == "categorical":
                from collections import Counter
                counts = Counter(vals)
                total = len(vals)
                stats[name] = {
                    "type": "categorical",
                    "distribution": {k: round(v / total * 100, 1) for k, v in counts.most_common()},
                }
            elif attr["type"] == "boolean":
                true_count = sum(1 for v in vals if v)
                stats[name] = {
                    "type": "boolean",
                    "true_pct": round(true_count / len(vals) * 100, 1),
                    "false_pct": round((len(vals) - true_count) / len(vals) * 100, 1),
                }
            else:
                stats[name] = {"type": attr["type"], "sample_count": len(vals)}
        return stats
