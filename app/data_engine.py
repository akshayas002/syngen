import uuid as uuid_lib
import random
import math
from datetime import datetime, timedelta
from collections import Counter
from typing import Any, Optional

from faker import Faker
import numpy as np

fake = Faker()
_rng = np.random.default_rng()   # prefixed to avoid shadowing in loops

COUNTRY_LIST = [
    "United States", "India", "United Kingdom", "Germany", "France", "Canada",
    "Australia", "Brazil", "Japan", "South Korea", "Mexico", "Netherlands",
    "Spain", "Italy", "Singapore", "Sweden", "Switzerland", "UAE",
    "South Africa", "Argentina",
]

COLOR_PALETTE = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD",
    "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9", "#F0B27A", "#82E0AA",
]


class DataEngine:
    """Advanced synthetic data generation engine."""

    def __init__(self, schema: dict):
        self._schema = schema
        self.attributes = schema.get("attributes", [])
        self.relationships = schema.get("relationships", [])
        self.constraints = schema.get("constraints", [])
        self._attr_map = {a["name"]: a for a in self.attributes}

    # ── PUBLIC ────────────────────────────────────────────────

    def generate(self, rows: int) -> list:
        data = [self._generate_row() for _ in range(rows)]
        self._apply_relationships(data)
        self._apply_constraints(data)
        self._enforce_unique(data)
        return data

    def compute_stats(self, data: list) -> dict:
        stats: dict = {}
        for attr in self.attributes:
            name = attr["name"]
            vals = [r[name] for r in data if r.get(name) is not None]
            if not vals:
                continue
            t = attr["type"]
            null_count = sum(1 for r in data if r.get(name) is None)

            if t in ("integer", "float"):
                arr = np.array(vals, dtype=float)
                p25, p75 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
                stats[name] = {
                    "type": t,
                    "label": attr.get("label", name),
                    "count": len(vals),
                    "null_count": null_count,
                    "mean":   round(float(np.mean(arr)),   3),
                    "std":    round(float(np.std(arr)),    3),
                    "min":    round(float(np.min(arr)),    3),
                    "p25":    round(p25,                   3),
                    "median": round(float(np.median(arr)), 3),
                    "p75":    round(p75,                   3),
                    "max":    round(float(np.max(arr)),    3),
                    "histogram": self._histogram(arr),
                }
            elif t == "categorical":
                c = Counter(vals)
                total = len(vals)
                stats[name] = {
                    "type": "categorical",
                    "label": attr.get("label", name),
                    "count": len(vals),
                    "null_count": null_count,
                    "unique": len(c),
                    "distribution": {k: round(v / total * 100, 1) for k, v in c.most_common()},
                }
            elif t == "boolean":
                true_count = sum(1 for v in vals if v)
                stats[name] = {
                    "type": "boolean",
                    "label": attr.get("label", name),
                    "count": len(vals),
                    "null_count": null_count,
                    "true_count":  true_count,
                    "false_count": len(vals) - true_count,
                    "true_pct":  round(true_count / len(vals) * 100, 1),
                    "false_pct": round((len(vals) - true_count) / len(vals) * 100, 1),
                }
            elif t == "date":
                stats[name] = {
                    "type": "date",
                    "label": attr.get("label", name),
                    "count": len(vals),
                    "null_count": null_count,
                    "min": min(vals),
                    "max": max(vals),
                }
            else:
                stats[name] = {
                    "type": t,
                    "label": attr.get("label", name),
                    "count": len(vals),
                    "null_count": null_count,
                }
        return stats

    # ── INTERNAL ──────────────────────────────────────────────

    def _generate_row(self) -> dict:
        row: dict = {}
        name_val: Optional[str] = None
        for attr in self.attributes:
            val = self._sample(attr, name_val)
            if attr["type"] == "name":
                name_val = val
            row[attr["name"]] = val
        return row

    def _sample(self, attr: dict, name_val: Optional[str] = None) -> Any:
        nullable = float(attr.get("nullable", 0.0))
        if nullable > 0 and random.random() < nullable:
            return None

        t = attr.get("type", "integer")

        # ── Faker / identity types ──────────────────
        if t == "name":
            return fake.name()
        if t == "email":
            if name_val:
                base = name_val.lower().replace(" ", ".").replace("'", "")[:12]
                domain = random.choice(["gmail.com", "yahoo.com", "outlook.com", "proton.me", "company.io"])
                return f"{base}{random.randint(1, 999)}@{domain}"
            return fake.email()
        if t == "phone":
            return fake.phone_number()
        if t == "company":
            return fake.company()
        if t == "city":
            return fake.city()
        if t == "country":
            return random.choice(COUNTRY_LIST)
        if t == "ip_address":
            return fake.ipv4()
        if t == "url":
            return fake.url()
        if t == "color":
            return random.choice(COLOR_PALETTE)
        if t == "text":
            return fake.sentence(nb_words=random.randint(6, 18))
        if t == "uuid":
            prefix = attr.get("prefix", "")
            raw = str(uuid_lib.uuid4())
            return f"{prefix}{raw[:8].upper()}" if prefix else raw

        # ── Date ───────────────────────────────────
        if t == "date":
            try:
                start = datetime.fromisoformat(attr.get("start", "2020-01-01"))
                end   = datetime.fromisoformat(attr.get("end",   "2024-12-31"))
            except ValueError:
                start = datetime(2020, 1, 1)
                end   = datetime(2024, 12, 31)
            delta_days = max((end - start).days, 1)
            return (start + timedelta(days=random.randint(0, delta_days))).strftime("%Y-%m-%d")

        # ── Boolean ────────────────────────────────
        if t == "boolean":
            return random.random() < float(attr.get("true_rate", 0.5))

        # ── Categorical ────────────────────────────
        if t == "categorical":
            values  = attr.get("values") or ["A", "B"]
            weights = attr.get("weights") or attr.get("probabilities")
            if weights and len(weights) == len(values):
                return random.choices(values, weights=[float(w) for w in weights], k=1)[0]
            return random.choice(values)

        # ── Numeric ────────────────────────────────
        dist = attr.get("distribution", "normal")
        mean = float(attr.get("mean", 50))
        std  = float(attr.get("std",  max(mean * 0.3, 5)))
        lo   = attr.get("min")
        hi   = attr.get("max")

        if lo is not None: lo = float(lo)
        if hi is not None: hi = float(hi)

        val: float
        if dist == "uniform":
            val = _rng.uniform(lo if lo is not None else 0.0,
                               hi if hi is not None else 100.0)
        elif dist == "lognormal":
            sigma = min(std / max(abs(mean), 1.0), 1.2)
            mu    = math.log(max(mean, 1.0)) - 0.5 * sigma ** 2
            val   = float(_rng.lognormal(mu, sigma))
        elif dist == "poisson":
            val = float(_rng.poisson(max(mean, 0.5)))
        elif dist == "exponential":
            val = float(_rng.exponential(max(mean, 1.0)))
        elif dist == "beta":
            a_param = float(attr.get("alpha", 2.0))
            b_param = float(attr.get("beta_param", 5.0))
            scale   = (hi - lo) if (lo is not None and hi is not None) else 100.0
            offset  = lo if lo is not None else 0.0
            val     = float(_rng.beta(a_param, b_param)) * scale + offset
        elif dist == "gamma":
            shape = (mean / max(std, 1.0)) ** 2
            scale = std ** 2 / max(mean, 1.0)
            val   = float(_rng.gamma(shape, scale))
        elif dist == "zipf":
            alpha_z = max(float(attr.get("alpha", 2.0)), 1.01)
            val     = float(_rng.zipf(alpha_z))
        else:  # normal (default)
            val = float(_rng.normal(mean, max(std, 0.01)))

        # Clamp to [min, max]
        if lo is not None: val = max(lo, val)
        if hi is not None: val = min(hi, val)

        decimals = int(attr.get("decimals", 0 if t == "integer" else 2))
        return int(round(val)) if t == "integer" else round(val, decimals)

    def _apply_relationships(self, data: list):
        strength_map = {"strong": 0.80, "moderate": 0.55, "weak": 0.30}

        for rel in self.relationships:
            frm = rel.get("from", "")
            to  = rel.get("to",   "")
            if not frm or not to:
                continue
            if frm not in self._attr_map or to not in self._attr_map:
                continue

            from_attr = self._attr_map[frm]
            to_attr   = self._attr_map[to]
            if from_attr["type"] not in ("integer", "float"):
                continue

            from_vals = [r[frm] for r in data if isinstance(r.get(frm), (int, float))]
            if not from_vals:
                continue

            min_f = float(min(from_vals))
            max_f = float(max(from_vals))
            rng_f = max_f - min_f or 1.0

            alpha   = strength_map.get(rel.get("strength", "moderate"), 0.55)
            forward = rel.get("direction", "positive") == "positive"

            to_vals = [r[to] for r in data if isinstance(r.get(to), (int, float))]

            if to_attr["type"] in ("integer", "float") and to_vals:
                min_t = float(min(to_vals))
                max_t = float(max(to_vals))
                rng_t = max_t - min_t or 1.0
                to_lo = to_attr.get("min")
                to_hi = to_attr.get("max")
                dec   = int(to_attr.get("decimals", 0 if to_attr["type"] == "integer" else 2))

                for row in data:
                    fv = row.get(frm)
                    if not isinstance(fv, (int, float)):
                        continue
                    norm  = (float(fv) - min_f) / rng_f
                    noise = float(_rng.random())
                    blend = alpha * norm + (1.0 - alpha) * noise
                    if not forward:
                        blend = 1.0 - blend
                    new_val = min_t + blend * rng_t

                    if to_lo is not None: new_val = max(float(to_lo), new_val)
                    if to_hi is not None: new_val = min(float(to_hi), new_val)

                    row[to] = int(round(new_val)) if to_attr["type"] == "integer" else round(new_val, dec)

            elif to_attr["type"] == "boolean":
                tr = float(to_attr.get("true_rate", 0.5))
                for row in data:
                    fv = row.get(frm)
                    if not isinstance(fv, (int, float)):
                        continue
                    norm  = (float(fv) - min_f) / rng_f
                    noise = float(_rng.random())
                    blend = alpha * norm + (1.0 - alpha) * noise
                    threshold = (1.0 - tr) if forward else tr
                    row[to] = blend > threshold

    def _apply_constraints(self, data: list):
        for constraint in self.constraints:
            if constraint.get("type") != "conditional":
                continue
            if_field  = constraint.get("if_field")
            if_val    = constraint.get("if_value")
            then_field = constraint.get("then_field")
            then_val  = constraint.get("then_value")
            if not all([if_field, if_val is not None, then_field, then_val is not None]):
                continue
            for row in data:
                if str(row.get(if_field, "")) == str(if_val):
                    row[then_field] = then_val

    def _enforce_unique(self, data: list):
        for attr in self.attributes:
            if not attr.get("unique"):
                continue
            name = attr["name"]
            seen: set = set()
            for row in data:
                orig = row.get(name)
                if orig is None:
                    continue
                val = orig
                attempts = 0
                while str(val) in seen and attempts < 30:
                    val = self._sample(attr)
                    attempts += 1
                row[name] = val
                seen.add(str(val))

    @staticmethod
    def _histogram(arr: np.ndarray, bins: int = 10) -> list:
        counts, edges = np.histogram(arr, bins=bins)
        return [
            {"label": f"{edges[i]:.1f}-{edges[i + 1]:.1f}", "count": int(counts[i])}
            for i in range(len(counts))
        ]
