"""Resource accounting cannot sum unrelated high-water measurements as simultaneous RSS."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from profile_local import combined_samples, process_tree_rss, statistics_for


def test_align_only_overlapping_samples():
    groups = [[{"t": 1.0, "rss": 100}, {"t": 2.0, "rss": 500}],
              [{"t": 1.1, "rss": 200}, {"t": 2.1, "rss": 20}]]
    assert [r["rss"] for r in combined_samples(groups)] == [300, 520]


def test_no_claim_of_concurrency_without_overlap():
    assert combined_samples([[{"t": 1, "rss": 100}], [{"t": 3, "rss": 900}]]) == []


def test_empty_statistics_are_unknown():
    assert statistics_for([]) == {"n": 0, "p50": None, "max": None}


def test_latency_sample_count_and_median():
    assert statistics_for([3, 1, 2]) == {"n": 3, "p50": 2, "max": 3}


def test_actual_live_child_included_in_rss():
    import subprocess
    import time

    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3)"])
    try:
        time.sleep(0.05)
        sample = process_tree_rss()
        assert str(child.pid) in sample["processes"]
        assert sample["tree_rss"] == sum(sample["processes"].values())
    finally:
        child.terminate()
        child.wait(timeout=5)
