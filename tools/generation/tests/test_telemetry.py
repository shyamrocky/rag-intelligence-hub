"""Independent owned arithmetic/usage fixtures, never real API measurements."""

import copy
from datetime import date
from decimal import Decimal

import pytest

from tools.generation.telemetry import capture_usage, estimate_max_cost, load_pricing, price_usage

DAY = date(2026, 10, 27)


def response(i=1000, c=200, w30=100, w12=0, o=100, reasoning=30, model="gpt-6-luna"):
    return {
        "model": model,
        "status": "completed",
        "service_tier": "default",
        "output": [],
        "usage": {
            "input_tokens": i,
            "output_tokens": o,
            "total_tokens": i + o,
            "input_tokens_details": {
                "cached_tokens": c,
                "cache_write_tokens": w30 + w12,
                "cache_write_tokens_details": {"ttl_30m_tokens": w30, "ttl_12h_tokens": w12},
            },
            "output_tokens_details": {"reasoning_tokens": reasoning},
        },
    }


def cost(raw, model="gpt-6-luna", registry=None, **kw):
    return price_usage(capture_usage(raw, model, 12.5), registry or load_pricing(), as_of=DAY, **kw)


@pytest.mark.parametrize("cached,w30,w12", [(0, 0, 0), (200, 0, 0), (200, 100, 0), (200, 100, 200)])
def test_exact_partitioned_input_cost_and_reasoning_not_charged_twice(cached, w30, w12):
    raw = response(c=cached, w30=w30, w12=w12)
    result = cost(raw)
    expected = (
        Decimal(1000 - cached - w30 - w12) * Decimal(".1")
        + Decimal(cached) * Decimal(".01")
        + Decimal(w30) * Decimal(".125")
        + Decimal(w12) * Decimal(".25")
        + Decimal(100) * Decimal(".5")
    ) / 1000000
    assert result["cost_status"] == "ESTIMATED_API_COST"
    assert Decimal(result["total_estimated_cost_usd"]) == expected
    assert Decimal(result["output_cost_usd"]) == Decimal("0.00005")
    assert result["total_tokens"] == 1100  # Reasoning is already inside output100.


@pytest.mark.parametrize("tokens,expected_factor", [(272000, 1), (272001, 2)])
def test_long_context_applies_to_full_request(tokens, expected_factor):
    result = cost(response(i=tokens, c=0, w30=0))
    assert (
        Decimal(result["input_cost_usd"])
        == Decimal(tokens) * Decimal(".1") * expected_factor / 1000000
    )
    expected_out = Decimal(".00005") * (Decimal("1.5") if expected_factor == 2 else 1)
    assert Decimal(result["output_cost_usd"]) == expected_out


@pytest.mark.parametrize(
    "tier,factor", [("default", "1"), ("flex", ".5"), ("fast", "2"), ("priority", "2")]
)
def test_response_processing_tier_and_regional_surcharge(tier, factor):
    raw = response()
    raw["service_tier"] = tier
    result = cost(raw, region="regional")
    base = Decimal(cost(response())["total_estimated_cost_usd"])
    assert Decimal(result["total_estimated_cost_usd"]) == base * Decimal(factor) * Decimal("1.10")


@pytest.mark.parametrize(
    "field", ["input_tokens", "output_tokens", "total_tokens", "input_tokens_details"]
)
def test_missing_usage_never_fabricates_cost(field):
    raw = response()
    del raw["usage"][field]
    assert cost(raw)["cost_status"] == "COST_UNAVAILABLE"
    assert cost(raw)["total_estimated_cost_usd"] is None


@pytest.mark.parametrize(
    "kind", ["cached", "writes", "lifetime", "pricing", "stale", "tier", "region", "model"]
)
def test_missing_billable_categories_and_policy_fail_closed(kind):
    raw = response()
    registry = load_pricing()
    kwargs = {}
    if kind == "cached":
        del raw["usage"]["input_tokens_details"]["cached_tokens"]
    elif kind == "writes":
        del raw["usage"]["input_tokens_details"]["cache_write_tokens"]
    elif kind == "lifetime":
        del raw["usage"]["input_tokens_details"]["cache_write_tokens_details"]
    elif kind == "pricing":
        del registry["policies"][0]["cached_input_rate"]
    elif kind == "stale":
        registry["policies"][0]["effective_through"] = "2026-10-26"
    elif kind == "tier":
        raw["service_tier"] = "auto"
    elif kind == "region":
        kwargs["region"] = "unknown"
    else:
        raw["model"] = "unreviewed-model"
    result = cost(raw, registry=registry, **kwargs)
    assert result["cost_status"] == "COST_UNAVAILABLE"
    assert result["total_estimated_cost_usd"] is None


@pytest.mark.parametrize(
    "kind", ["total", "reasoning", "overlap", "negative", "bool", "fraction", "writes", "unknown"]
)
def test_usage_reconciliation_and_invalid_values(kind):
    raw = response()
    u = raw["usage"]
    if kind == "total":
        u["total_tokens"] += 1
    elif kind == "reasoning":
        u["output_tokens_details"]["reasoning_tokens"] = 101
    elif kind == "overlap":
        u["input_tokens_details"]["cached_tokens"] = 1000
    elif kind == "negative":
        u["input_tokens"] = -1
    elif kind == "bool":
        u["input_tokens"] = True
    elif kind == "fraction":
        u["output_tokens"] = 1.5
    elif kind == "writes":
        u["input_tokens_details"]["cache_write_tokens"] = 99
    else:
        u["input_tokens_details"]["audio_tokens"] = 10
    result = cost(raw)
    assert result["usage_status"] == "USAGE_INVALID"
    assert result["total_estimated_cost_usd"] is None


def test_missing_usage_and_optional_reasoning_breakdown():
    raw = response()
    raw["usage"] = None
    assert cost(raw)["usage_status"] == "USAGE_UNAVAILABLE"
    raw = response()
    del raw["usage"]["output_tokens_details"]["reasoning_tokens"]
    result = cost(raw)
    assert result["reasoning_tokens"] is None
    assert result["cost_status"] == "ESTIMATED_API_COST"  # Output total is still complete.


def test_zero_writes_does_not_require_nonexistent_lifetime_details():
    raw = response(w30=0)
    del raw["usage"]["input_tokens_details"]["cache_write_tokens_details"]
    assert cost(raw)["cost_status"] == "ESTIMATED_API_COST"


def test_model_switching_selects_different_rates_without_luna_assumptions():
    luna = cost(response())
    terra = cost(response(model="gpt-6.1-terra"), model="gpt-6.1-terra")
    assert Decimal(terra["output_cost_usd"]) == Decimal(luna["output_cost_usd"]) * 10
    assert Decimal(terra["cached_input_cost_usd"]) == Decimal(luna["cached_input_cost_usd"]) * 5


def test_dry_run_has_no_actual_output_and_maximum_is_conservative():
    registry = load_pricing()
    estimate = estimate_max_cost("gpt-6-luna", 1000, 4096, registry, tier="default", as_of=DAY)
    assert estimate["actual_output_tokens"] is None
    assert estimate["status"] == "ESTIMATED_MAX_API_COST"
    assert (
        Decimal(estimate["estimated_max_cost_usd"])
        == (Decimal(1000) * Decimal(".25") + Decimal(4096) * Decimal(".5")) / 1000000
    )
    blocked = estimate_max_cost("gpt-6-luna", None, 4096, registry, tier="default", as_of=DAY)
    assert blocked["status"] == "COST_UNAVAILABLE"


@pytest.mark.parametrize("rate", [None, -1, "NaN", "-1", "Infinity", 0.1])
def test_invalid_rates_are_not_totals(rate):
    registry = copy.deepcopy(load_pricing())
    registry["policies"][0]["input_rate"] = rate
    assert cost(response(), registry=registry)["total_estimated_cost_usd"] is None
