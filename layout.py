"""2D UMAP layout, HDBSCAN clusters, topic labels and nearest neighbours.

Reads config.PAPERS_PATH and config.EMBEDDINGS_PATH, writes config.LAYOUT_PATH:
    {"clusters": {id: name}, "points": [{x, y, cluster}], "neighbors": [[idx, ...]]}
`points` and `neighbors` follow the order of the papers file. Cluster -1 holds
papers HDBSCAN left unassigned.
"""
import argparse
import json

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

import config

N_NEIGHBORS = 6
LABEL_TERMS = 3

DOMAIN_STOPWORDS = [
    "propose", "proposed", "method", "methods", "paper", "results", "novel",
    "approach", "task", "tasks", "model", "models", "performance", "state",
    "art", "show", "demonstrate", "experiments", "existing", "based", "using",
    "data", "learning", "framework", "outperforms", "extensive",
]


def normalize(embeddings):
    emb = embeddings.astype(np.float32)
    norms = np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return emb / norms


def nearest_neighbors(normalized, k=N_NEIGHBORS, chunk=1024):
    """Top-k cosine neighbours of every row (self excluded), most similar first."""
    n = len(normalized)
    k = min(k, n - 1)
    out = np.empty((n, k), dtype=np.int32)
    for start in range(0, n, chunk):
        sims = normalized[start : start + chunk] @ normalized.T
        sims[np.arange(len(sims)), np.arange(start, start + len(sims))] = -np.inf
        top = np.argpartition(-sims, k - 1, axis=1)[:, :k]
        order = np.argsort(-np.take_along_axis(sims, top, axis=1), axis=1)
        out[start : start + chunk] = np.take_along_axis(top, order, axis=1)
    return out


def pick_terms(ranked_terms, n=LABEL_TERMS):
    """Take the top terms, skipping any that contain or are contained in a chosen one
    ("diffusion" vs "diffusion language"), so a label does not repeat itself."""
    chosen = []
    for term in ranked_terms:
        if any(term in c or c in term for c in chosen):
            continue
        chosen.append(term)
        if len(chosen) == n:
            break
    return chosen


def cluster_labels(texts, labels):
    """Name each real cluster by its highest TF-IDF terms, with all of a cluster's
    texts treated as one document so terms are scored against the other clusters."""
    real = sorted(set(labels.tolist()) - {-1})
    names = {}
    if real:
        docs = [" ".join(texts[i] for i in np.where(labels == c)[0]) for c in real]
        vec = TfidfVectorizer(
            ngram_range=(1, 2),
            stop_words=list(ENGLISH_STOP_WORDS) + DOMAIN_STOPWORDS,
            # Drop terms found in most clusters, but only when there are enough
            # clusters for that to be meaningful (max_df needs >= 1 document).
            max_df=0.5 if len(real) >= 4 else 1.0,
        )
        tfidf = vec.fit_transform(docs)
        terms = np.array(vec.get_feature_names_out())
        for row, c in enumerate(real):
            scores = tfidf[row].toarray().ravel()
            ranked = terms[scores.argsort()[::-1][:20]]
            names[c] = " · ".join(pick_terms(list(ranked)))
    if -1 in labels:
        names[-1] = "unclustered"
    return names


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--min-cluster-size", type=int, default=25)
    ap.add_argument("--n-neighbors", type=int, default=15, help="UMAP neighbourhood size")
    args = ap.parse_args()

    import umap  # imported here so the helpers above can be tested without numba
    from sklearn.cluster import HDBSCAN

    with open(config.PAPERS_PATH) as f:
        papers = json.load(f)
    embeddings = np.load(config.EMBEDDINGS_PATH)
    assert len(embeddings) == len(papers), (
        f"{len(embeddings)} embeddings != {len(papers)} papers"
    )
    normalized = normalize(embeddings)

    print("Running UMAP...")
    xy = umap.UMAP(
        n_components=2, n_neighbors=args.n_neighbors, min_dist=0.05,
        metric="cosine", random_state=42,
    ).fit_transform(normalized)

    print("Running HDBSCAN...")
    labels = HDBSCAN(min_cluster_size=args.min_cluster_size).fit_predict(xy)

    texts = [
        " ".join([p["title"], p["abstract"], " ".join(p.get("keywords", []))])
        for p in papers
    ]
    names = cluster_labels(texts, labels)
    neighbors = nearest_neighbors(normalized)

    out = {
        "clusters": {str(c): names[c] for c in sorted(names)},
        "points": [
            {"x": float(xy[i, 0]), "y": float(xy[i, 1]), "cluster": int(labels[i])}
            for i in range(len(papers))
        ],
        "neighbors": neighbors.tolist(),
    }
    with open(config.LAYOUT_PATH, "w") as f:
        json.dump(out, f)

    sizes = {c: int((labels == c).sum()) for c in names}
    print(f"\n{len(names)} clusters (including unclustered, if any):")
    for c in sorted(names, key=lambda c: (c == -1, -sizes[c])):
        print(f"  [{c:3d}] n={sizes[c]:4d}  {names[c]}")
    print(f"\nWrote layout for {len(papers)} papers to {config.LAYOUT_PATH}")


if __name__ == "__main__":
    main()
