import numpy as np

import layout


def test_nearest_neighbors_matches_brute_force():
    rng = np.random.default_rng(0)
    emb = layout.normalize(rng.normal(size=(60, 16)))
    nn = layout.nearest_neighbors(emb, k=5, chunk=7)  # chunk size not dividing n
    sims = emb @ emb.T
    np.fill_diagonal(sims, -np.inf)
    expected = np.argsort(-sims, axis=1)[:, :5]
    assert (nn == expected).all()


def test_nearest_neighbors_excludes_self_and_caps_k():
    emb = layout.normalize(np.eye(3, 4))
    nn = layout.nearest_neighbors(emb, k=10)
    assert nn.shape == (3, 2)
    assert all(i not in row for i, row in enumerate(nn))


def test_normalize_handles_zero_rows():
    out = layout.normalize(np.zeros((2, 3), dtype=np.float16))
    assert np.isfinite(out).all()


def test_pick_terms_skips_overlaps():
    ranked = ["diffusion", "diffusion language", "language", "protein folding", "protein"]
    assert layout.pick_terms(ranked, n=3) == ["diffusion", "language", "protein folding"]


def test_cluster_labels_name_distinct_topics():
    texts = (
        ["reinforcement policy reward agent environment"] * 5
        + ["protein molecule drug binding structure"] * 5
        + ["graph node edge message passing"] * 5
        + ["quantum circuit qubit noise gate"] * 5
        + ["stray paper"]
    )
    labels = np.array([0] * 5 + [1] * 5 + [2] * 5 + [3] * 5 + [-1])
    names = layout.cluster_labels(texts, labels)
    assert "reward" in names[0] or "policy" in names[0] or "agent" in names[0]
    assert "protein" in names[1] or "molecule" in names[1] or "drug" in names[1]
    assert names[-1] == "unclustered"
    assert len(set(names.values())) == len(names)


def test_cluster_labels_with_two_clusters():
    texts = ["alpha beta"] * 3 + ["gamma delta"] * 3
    names = layout.cluster_labels(texts, np.array([0, 0, 0, 1, 1, 1]))
    assert set(names) == {0, 1}
