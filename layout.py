"""Compute a 2D UMAP layout and HDBSCAN clusters for CVPR 2026 papers.

Reads data/cvpr_2026_papers.json and data/cvpr_2026_specter2.npy,
writes data/cvpr_2026_layout.json:
    {"clusters": {id: name}, "points": [{x, y, cluster}]}
`points` is in the same order as cvpr_2026_papers.json.
"""
import json

import numpy as np
import umap
from sklearn.cluster import HDBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS

PAPERS_PATH = "data/cvpr_2026_papers.json"
EMBEDDINGS_PATH = "data/cvpr_2026_specter2.npy"
OUTPUT_PATH = "data/cvpr_2026_layout.json"

DOMAIN_STOPWORDS = [
    "propose",
    "proposed",
    "method",
    "methods",
    "paper",
    "results",
    "novel",
    "approach",
    "task",
    "tasks",
    "model",
    "models",
    "performance",
    "state",
    "art",
]


def main():
    with open(PAPERS_PATH, "r") as f:
        papers = json.load(f)
    n_papers = len(papers)
    print(f"Loaded {n_papers} papers from {PAPERS_PATH}")

    embeddings = np.load(EMBEDDINGS_PATH)
    assert embeddings.shape[0] == n_papers, (
        f"embeddings rows {embeddings.shape[0]} != paper count {n_papers}"
    )

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = embeddings / norms

    print("Running UMAP...")
    reducer = umap.UMAP(
        n_components=2,
        n_neighbors=15,
        min_dist=0.05,
        metric="cosine",
        random_state=42,
    )
    xy = reducer.fit_transform(normalized)

    print("Running HDBSCAN...")
    clusterer = HDBSCAN(min_cluster_size=25)
    labels = clusterer.fit_predict(xy)

    unique_labels = sorted(set(labels.tolist()))
    print(f"Found {len(unique_labels)} clusters (including noise if present).")

    stop_words = list(ENGLISH_STOP_WORDS) + DOMAIN_STOPWORDS

    abstracts = [p["abstract"] for p in papers]
    cluster_docs = {}
    cluster_sizes = {}
    for label in unique_labels:
        idxs = np.where(labels == label)[0]
        cluster_sizes[label] = len(idxs)
        cluster_docs[label] = " ".join(abstracts[i] for i in idxs)

    real_labels = [l for l in unique_labels if l != -1]
    cluster_names = {}
    if real_labels:
        docs = [cluster_docs[l] for l in real_labels]
        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words=stop_words)
        tfidf = vectorizer.fit_transform(docs)
        terms = np.array(vectorizer.get_feature_names_out())
        for row_idx, label in enumerate(real_labels):
            row = tfidf[row_idx].toarray().ravel()
            top_idx = row.argsort()[::-1][:3]
            top_terms = [terms[i] for i in top_idx]
            cluster_names[label] = " · ".join(top_terms)

    if -1 in unique_labels:
        cluster_names[-1] = "unclustered"

    points = [
        {"x": float(xy[i, 0]), "y": float(xy[i, 1]), "cluster": int(labels[i])}
        for i in range(n_papers)
    ]

    clusters_out = {str(label): cluster_names[label] for label in unique_labels}

    assert len(points) == n_papers, (
        f"point count {len(points)} != paper count {n_papers}"
    )

    with open(OUTPUT_PATH, "w") as f:
        json.dump({"clusters": clusters_out, "points": points}, f)

    print(f"\nCluster list ({len(unique_labels)} clusters):")
    for label in sorted(unique_labels, key=lambda l: (l == -1, -cluster_sizes[l])):
        print(f"  [{label}] size={cluster_sizes[label]:4d}  {cluster_names[label]}")

    print(f"\nWrote layout for {len(points)} points to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
