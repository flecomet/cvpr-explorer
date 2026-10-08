import pytest

import build_site


def paper(i, decision="poster", area="rl", track="Main track"):
    return {
        "id": f"id{i}", "title": f"T{i}", "authors": "A", "abstract": "abs",
        "pdf_link": "p", "forum_link": "f", "keywords": ["k"], "tldr": "",
        "area": area, "decision": decision, "track": track,
    }


def make(n=4):
    papers = [paper(i, decision=["oral", "poster", "weird", "poster"][i % 4]) for i in range(n)]
    layout = {
        "clusters": {"0": "a · b", "1": "c · d", "-1": "unclustered"},
        "points": [{"x": float(i), "y": float(2 * i), "cluster": [0, 0, 1, -1][i % 4]} for i in range(n)],
        "neighbors": [[(i + 1) % n] for i in range(n)],
    }
    return papers, layout


def test_columns_are_aligned():
    papers, layout = make()
    core, details = build_site.build(papers, layout)
    n = len(papers)
    for key in ("id", "x", "y", "c", "dec", "area", "track", "site", "title", "nn"):
        assert len(core[key]) == n, key
    for key in ("authors", "abstract", "tldr", "kw", "pdf", "forum"):
        assert len(details[key]) == n, key


def test_unknown_decision_maps_to_other_and_order_is_fixed():
    papers, layout = make()
    core, _ = build_site.build(papers, layout)
    assert core["decisions"] == ["oral", "poster", "other"]
    assert core["decisions"][core["dec"][2]] == "other"


def test_cluster_centroid_is_median_and_empty_clusters_dropped():
    papers, layout = make(4)
    layout["clusters"]["7"] = "empty · cluster"
    core, _ = build_site.build(papers, layout)
    assert "7" not in core["clusters"]
    assert core["clusters"]["0"] == {"name": "a · b", "n": 2, "cx": 0.5, "cy": 1.0}
    assert core["clusters"]["-1"]["n"] == 1


def test_mismatched_inputs_fail():
    papers, layout = make()
    layout["points"].pop()
    try:
        build_site.build(papers, layout)
    except AssertionError:
        return
    raise AssertionError("expected a length mismatch to be rejected")


def test_render_index_fills_every_placeholder(monkeypatch):
    for key in build_site.PLACEHOLDERS:
        monkeypatch.setattr(build_site.config, key, f"<{key}>", raising=False)
    page = build_site.render_index(" ".join(f"@@{k}@@" for k in build_site.PLACEHOLDERS))
    assert page == " ".join(f"<{k}>" for k in build_site.PLACEHOLDERS)


def test_render_index_rejects_unknown_placeholder():
    with pytest.raises(AssertionError, match="@@NOPE@@"):
        build_site.render_index("@@NOPE@@")


def test_template_uses_only_known_placeholders():
    with open(build_site.TEMPLATE_PATH, encoding="utf-8") as f:
        build_site.render_index(f.read())
