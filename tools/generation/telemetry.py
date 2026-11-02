"""Application-owned API usage and Decimal pricing; never part of model JSON."""

import json
import math
from datetime import date
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

HERE = Path(__file__).parent
MONEY_FIELDS = [
    "input_cost_usd",
    "cached_input_cost_usd",
    "cache_write_cost_usd",
    "output_cost_usd",
    "total_estimated_cost_usd",
]


def integer(value):
    return type(value) is int and value >= 0


def empty_usage(model, *, latency_ms=None, response_status="NOT_EXECUTED"):
    return {
        "input_tokens": None,
        "cached_input_tokens": None,
        "cache_write_tokens": None,
        "cache_write_30m_tokens": None,
        "cache_write_12h_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "total_tokens": None,
        "latency_ms": latency_ms,
        "model": model,
        "selected_model": model,
        "response_status": response_status,
        "service_tier": None,
        "usage_status": "USAGE_UNAVAILABLE",
        "usage_errors": [],
        "cost_status": "COST_UNAVAILABLE",
        "cost_reasons": ["NO_MEASURED_API_USAGE"],
        "pricing_version": None,
        **dict.fromkeys(MONEY_FIELDS),
    }


def capture_usage(response, selected_model, latency_ms):
    """Response is SDK model_dump() JSON or an owned test fixture, never LLM claims."""
    r = empty_usage(selected_model, latency_ms=latency_ms, response_status=response.get("status"))
    r["model"] = response.get("model")
    r["service_tier"] = response.get("service_tier")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        return r
    details = usage.get("input_tokens_details") or {}
    outputs = usage.get("output_tokens_details") or {}
    if not isinstance(details, dict) or not isinstance(outputs, dict):
        r.update(usage_status="USAGE_INVALID", usage_errors=["MALFORMED_USAGE_DETAILS"])
        return r
    writes = details.get("cache_write_tokens_details") or {}
    if not isinstance(writes, dict):
        r.update(usage_status="USAGE_INVALID", usage_errors=["MALFORMED_CACHE_WRITE_DETAILS"])
        return r
    r.update(
        input_tokens=usage.get("input_tokens"),
        cached_input_tokens=details.get("cached_tokens"),
        cache_write_tokens=details.get("cache_write_tokens"),
        cache_write_30m_tokens=writes.get("ttl_30m_tokens"),
        cache_write_12h_tokens=writes.get("ttl_12h_tokens"),
        output_tokens=usage.get("output_tokens"),
        reasoning_tokens=outputs.get("reasoning_tokens"),
        total_tokens=usage.get("total_tokens"),
    )
    errors = []
    if any(item.get("type") not in {"message", "reasoning"} for item in response.get("output", [])):
        errors.append("UNSUPPORTED_POTENTIALLY_BILLABLE_OUTPUT_TYPE")
    for key in [
        "input_tokens",
        "cached_input_tokens",
        "cache_write_tokens",
        "cache_write_30m_tokens",
        "cache_write_12h_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    ]:
        if r[key] is not None and not integer(r[key]):
            errors.append("INVALID_" + key.upper())
            r[key] = None
    i, c, w, o, total, reasoning = [
        r[k]
        for k in [
            "input_tokens",
            "cached_input_tokens",
            "cache_write_tokens",
            "output_tokens",
            "total_tokens",
            "reasoning_tokens",
        ]
    ]
    if all(integer(x) for x in [i, o, total]) and i + o != total:
        errors.append("TOTAL_TOKENS_DO_NOT_RECONCILE")
    if all(integer(x) for x in [i, c, w]) and c + w > i:
        errors.append("INPUT_SUBCATEGORIES_EXCEED_TOTAL")
    if integer(reasoning) and integer(o) and reasoning > o:
        errors.append("REASONING_EXCEEDS_OUTPUT_TOTAL")
    w30, w12 = r["cache_write_30m_tokens"], r["cache_write_12h_tokens"]
    if all(integer(x) for x in [w30, w12, w]) and w30 + w12 != w:
        errors.append("CACHE_WRITE_SUBCATEGORIES_DO_NOT_RECONCILE")
    known_usage = {
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "input_tokens_details",
        "output_tokens_details",
    }
    known_in = {"cached_tokens", "cache_write_tokens", "cache_write_tokens_details"}
    known_out = {"reasoning_tokens"}
    for values, allowed in [
        (usage, known_usage),
        (details, known_in),
        (outputs, known_out),
        (writes, {"ttl_30m_tokens", "ttl_12h_tokens"}),
    ]:
        if any(v not in (None, 0, {}, []) for k, v in values.items() if k not in allowed):
            errors.append("UNSUPPORTED_USAGE_CATEGORY")
    required = [i, c, w, o, total]
    r["usage_status"] = (
        "USAGE_INVALID"
        if errors
        else ("MEASURED_API_USAGE" if all(integer(x) for x in required) else "USAGE_PARTIAL")
    )
    if latency_ms is not None and (
        not isinstance(latency_ms, (int, float)) or not math.isfinite(latency_ms) or latency_ms < 0
    ):
        errors.append("INVALID_LATENCY")
        r["usage_status"] = "USAGE_INVALID"
    r["usage_errors"] = errors
    return r


def load_pricing(path=None):
    return json.loads(Path(path or HERE / "pricing-v1.json").read_bytes())


def policy_for(registry, model, as_of):
    if registry.get("schema") != "token-pricing-registry-1.0" or not registry.get("version"):
        raise ValueError("INVALID_PRICING_REGISTRY")
    matching = [
        p
        for p in registry["policies"]
        if p["model"] == model
        and date.fromisoformat(p["effective_from"])
        <= as_of
        <= date.fromisoformat(p["effective_through"])
    ]
    if len(matching) != 1:
        raise ValueError("MISSING_STALE_OR_AMBIGUOUS_PRICING")
    return matching[0]


def decimal(value):
    if type(value) is not str:
        raise ValueError("PRICING_MUST_USE_DECIMAL_STRINGS")
    d = Decimal(value)
    if not d.is_finite() or d < 0:
        raise ValueError("INVALID_PRICING_RATE")
    return d


def rates(policy, input_tokens, tier, region):
    if policy["currency"] != "USD" or policy["per_tokens"] != 1000000:
        raise ValueError("UNSUPPORTED_PRICING_UNITS")
    if type(policy["long_context_threshold"]) is not int or policy["long_context_threshold"] < 0:
        raise ValueError("INVALID_LONG_CONTEXT_CONDITION")
    long = input_tokens > policy["long_context_threshold"]
    tier_factor = decimal(policy["tier_multipliers"][tier])
    region_factor = decimal(policy["region_multipliers"][region])
    factor = tier_factor * region_factor
    fi = factor * (decimal(policy["long_context_input_multiplier"]) if long else 1)
    fo = factor * (decimal(policy["long_context_output_multiplier"]) if long else 1)
    return {
        k: decimal(policy[k]) * (fo if k == "output_rate" else fi)
        for k in [
            "input_rate",
            "cached_input_rate",
            "cache_write_30m_rate",
            "cache_write_12h_rate",
            "output_rate",
        ]
    }


def price_usage(usage, registry, *, region="global", as_of=None):
    r = dict(usage)
    r.update(dict.fromkeys(MONEY_FIELDS))
    r.update(cost_status="COST_UNAVAILABLE", pricing_version=registry.get("version"))
    try:
        if usage["usage_status"] != "MEASURED_API_USAGE":
            raise ValueError("USAGE_MISSING_OR_INVALID")
        if usage["model"] != usage["selected_model"]:
            raise ValueError("RESPONSE_MODEL_PRICING_BINDING_MISMATCH")
        p = policy_for(registry, usage["model"], as_of or date.today())
        with localcontext() as ctx:
            ctx.prec = 50
            rate = rates(p, usage["input_tokens"], usage["service_tier"], region)
            i, c, w, o = [
                usage[k]
                for k in [
                    "input_tokens",
                    "cached_input_tokens",
                    "cache_write_tokens",
                    "output_tokens",
                ]
            ]
            w30, w12 = usage["cache_write_30m_tokens"], usage["cache_write_12h_tokens"]
            if w == 0:
                w30 = w12 = 0
            if not all(integer(x) for x in [w30, w12]) or w30 + w12 != w:
                raise ValueError("CACHE_WRITE_LIFETIME_USAGE_MISSING")
            costs = [
                (i - c - w) * rate["input_rate"],
                c * rate["cached_input_rate"],
                w30 * rate["cache_write_30m_rate"] + w12 * rate["cache_write_12h_rate"],
                o * rate["output_rate"],
            ]
            for key, value in zip(MONEY_FIELDS[:-1], costs, strict=True):
                r[key] = str(value / 1000000)
            r["total_estimated_cost_usd"] = str(sum(costs) / 1000000)
        r.update(
            cost_status="ESTIMATED_API_COST",
            cost_reasons=[],
            pricing_effective_from=p["effective_from"],
            pricing_effective_through=p["effective_through"],
        )
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        # Only application-owned error codes; never raw provider exceptions.
        reason = str(error) if type(error) is ValueError else "MISSING_OR_INVALID_PRICING_CATEGORY"
        r["cost_reasons"] = [reason]
    return r


def estimate_max_cost(
    model, input_tokens, output_reserve, registry, *, tier, region="global", as_of=None
):
    result = {
        "status": "COST_UNAVAILABLE",
        "pricing_version": registry.get("version"),
        "verified_input_tokens": input_tokens,
        "reserved_output_tokens": output_reserve,
        "estimated_max_cost_usd": None,
        "actual_output_tokens": None,
        "assumption": "Worst-case input category (uncached/read/30m-write/12h-write), full output reserve; no invoice claim.",
    }
    try:
        if not integer(input_tokens) or not integer(output_reserve):
            raise ValueError("VERIFIED_GENERATOR_INPUT_COUNT_UNAVAILABLE")
        p = policy_for(registry, model, as_of or date.today())
        with localcontext() as ctx:
            ctx.prec = 50
            r = rates(p, input_tokens, tier, region)
            cost = (
                input_tokens * max(v for k, v in r.items() if k != "output_rate")
                + output_reserve * r["output_rate"]
            )
            result.update(
                status="ESTIMATED_MAX_API_COST", estimated_max_cost_usd=str(cost / 1000000)
            )
    except (ValueError, KeyError, TypeError, InvalidOperation) as error:
        result["reason"] = (
            str(error) if type(error) is ValueError else "MISSING_OR_INVALID_PRICING_CATEGORY"
        )
    return result
