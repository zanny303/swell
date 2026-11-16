from swell.similarity import eligible, sisters


def result(name, source, values, passed=True):
    return {
        "site": name, "source": source,
        "tests": [{"name": "independent check", "passed": passed}, {"name": "not applicable", "passed": None}],
        "signature": dict(zip(("gain_per_lep", "T", "tau", "beta", "artifact_share"), values)),
    }


def test_cross_site_similarity_ranks_only_real_validated_runs():
    rows = {
        "A": result("A", "NASA NISAR GUNW", [5, 20, 3, 8, .2]),
        "B": result("B", "NASA NISAR GUNW", [5.1, 20.2, 3.1, 8.2, .21]),
        "C": result("C", "NASA NISAR GUNW", [10, 60, 12, 25, .8]),
        "Synthetic": result("Synthetic", "SYNTHETIC", [5, 20, 3, 8, .2]),
        "Failed": result("Failed", "NASA NISAR GUNW", [5, 20, 3, 8, .2], passed=False),
    }
    assert eligible(rows["A"])[0] is True
    assert eligible(rows["Synthetic"])[0] is False
    ranked = sisters(rows)
    assert [x["site"] for x in ranked["A"]][0] == "B"
    assert "Synthetic" not in [x["site"] for x in ranked["A"]]
    assert "Failed" not in [x["site"] for x in ranked["A"]]


def test_similarity_rejects_missing_or_nonfinite_signature():
    bad = result("Bad", "NASA NISAR GUNW", [5, 20, 3, 8, .2])
    bad["signature"]["T"] = float("nan")
    ok, reason = eligible(bad)
    assert not ok
    assert "non-finite" in reason
