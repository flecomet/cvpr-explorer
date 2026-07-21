# CVPR 2026 Explorer — Design

Date: 2026-07-21
Status: Approved

## Goal

Fork `dataplayer12/cvpr-explorer` into a single-purpose tool: a 2D semantic map of the 4068 CVPR 2026 papers, built on SPECTER2 embeddings, with unsupervised cluster coloring. Ship fast.

## Why the fork diverges from upstream

Upstream is broken and over-general for this goal:

- `embed_openai.py` imports a private module `uc` (`uc.NOT_OAI_API` = API key). Pipeline cannot run.
- `data/*.json` and `data/*.npy` are gitignored. Only `cvpr_2023_*` exists at repo root. `embed.py` iterates every conference/year in `conf2year.py` and opens `data/{conf}_{year}_papers.json` at import time, so the app crashes on a fresh clone.
- `download.py` uses Selenium + headless Chrome with a hardcoded `time.sleep(2)` per paper. The CVF open-access site is static HTML; Selenium is unnecessary and drags Chrome + chromedriver into the Docker image.
- `embed.py` recomputes t-SNE for every conference/year at import. Startup cost scales with the dataset count.

Decision: reduce to CVPR 2026 only, precompute all derived artifacts offline, and let the served app be a thin reader.

## Scope

In scope:

- CVPR 2026 (4068 papers) from `https://openaccess.thecvf.com/CVPR2026?day=all`.
- SPECTER2 embeddings of title + abstract.
- UMAP 2D map view, Dash + Plotly `Scattergl`.
- HDBSCAN clusters, auto-named by TF-IDF.
- Slim Docker image.

Out of scope (explicitly deferred):

- kNN / node-link graph view.
- Other conferences and years; `conf2year.py` multi-conference machinery is removed.
- Keyword search box.
- "Papers with code" links.

## Architecture

Two halves with a file boundary between them.

**Offline pipeline** (run on a machine with a GPU, three scripts, run once):

```
scrape.py  → data/cvpr_2026_papers.json
embed.py   → data/cvpr_2026_specter2.npy
layout.py  → data/cvpr_2026_layout.json
```

**Served app** (`app.py`) reads `cvpr_2026_papers.json` and `cvpr_2026_layout.json` at boot and does no computation. `cvpr_2026_specter2.npy` is a pipeline intermediate and is not read by the app.

All three artifacts are committed to git. Rationale: the repo already set that precedent (`cvpr_2023_embeddings_openai.npy` is tracked), the Docker image becomes self-contained, and deployment needs no GPU. Total added weight ~19 MB.

## Components

### `scrape.py`

Purpose: turn the CVF listing into a papers JSON.

- Fetch `https://openaccess.thecvf.com/CVPR2026?day=all`, extract every `.ptitle a` href (4068 expected).
- Fetch each paper page concurrently with `ThreadPoolExecutor(max_workers=16)` using `requests.Session` per worker.
- Parse with BeautifulSoup: `div#papertitle`, `div#abstract`, and the `.pdf` href (prefix with `https://openaccess.thecvf.com`). Authors from `div#authors`.
- Retry each URL up to 3 times with exponential backoff. Collect permanent failures.
- Output: `data/cvpr_2026_papers.json`, a list of `{title, authors, abstract, pdf_link}` in listing order.

Error handling: if any paper fails after retries, print the failing URLs and exit non-zero. A partial dataset must not silently become the shipped artifact.

Verification: assert the parsed paper count matches the number of listing hrefs; assert no empty title or abstract.

### `embed.py`

Purpose: SPECTER2 embeddings.

- `allenai/specter2_base` + the `allenai/specter2` proximity adapter, via `adapters.AutoAdapterModel`.
- Input text per paper: `title + tokenizer.sep_token + abstract`.
- `truncation=True, max_length=512`, batch size 32, fp16 on CUDA, CPU fallback.
- Pool: CLS token, i.e. `last_hidden_state[:, 0, :]` → `[4068, 768]`.
- Output: `data/cvpr_2026_specter2.npy`, float32.

Verification: assert shape `[len(papers), 768]`; assert no NaN.

### `layout.py`

Purpose: 2D coordinates, clusters, and cluster names.

- `umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.05, metric="cosine", random_state=42)` on the L2-normalized embeddings → `xy`.
- `sklearn.cluster.HDBSCAN(min_cluster_size=25)` fit on that same 2D `xy`. Clustering in the projected space (rather than in high dimensions) guarantees that clusters are spatially contiguous on the map, which is what makes the legend legible. This is a deliberate UX trade against clustering fidelity.
- `sklearn.cluster.HDBSCAN` ships with scikit-learn ≥ 1.3, so the separate `hdbscan` package (which needs a compiler) is not a dependency.
- Cluster naming: build one pseudo-document per cluster by concatenating its abstracts, run `TfidfVectorizer(ngram_range=(1,2), stop_words=...)` across those documents, take the top 3 terms, join with `·`. Stopwords: English plus a domain stoplist — `propose, proposed, method, methods, paper, results, novel, approach, task, tasks, model, models, performance, state art`.
- HDBSCAN noise (label `-1`) becomes cluster name `unclustered`.
- Output: `data/cvpr_2026_layout.json` with `{"clusters": {id: name}, "points": [{x, y, cluster}]}`, `points` in the same order as `cvpr_2026_papers.json`.

Verification: assert `len(points) == len(papers)`; print the cluster count, each cluster's size, and its name for eyeball review.

### `app.py`

Purpose: the served Dash app. Replaces upstream `embed.py`.

- Load the two JSON artifacts at module import. No t-SNE, no UMAP, no model at runtime.
- One `go.Scattergl` trace per cluster; trace name is the cluster name; `unclustered` is added first so it renders underneath, in grey.
- `customdata` carries `[pdf_link, title, abstract]`; hover shows the title only.
- Click callback fills title, abstract, and an "Open PDF" link, as upstream did.
- Dark theme (`#111111`) retained. Figure fills `80vh`.
- `app.run(debug=False, host="0.0.0.0", port=8050)` — port matches the Dockerfile's `EXPOSE 8050`. Upstream used port 80 with `debug=True`, which is wrong for a served app.

Error handling: if a data artifact is missing, fail at import with a message naming the pipeline script that produces it.

## Dependencies

Split in two, because the pipeline deps are heavy and the image should not carry them.

`requirements.txt` (runtime / Docker): `dash`, `plotly`, `pandas`, `numpy`, `gunicorn`.

`requirements-pipeline.txt` (local only): `requests`, `beautifulsoup4`, `torch`, `transformers`, `adapters`, `umap-learn`, `scikit-learn>=1.3`, `numpy`.

Local pipeline env created with `uv venv`.

Dropped entirely: `selenium`, `webdriver_manager`, `spacy`, `werkzeug`, `flask`.

## Docker

Single-stage `python:3.11-slim`, install `requirements.txt`, copy the app and `data/`, `CMD ["python", "app.py"]`.

Removed: both Chrome install blocks, the chromedriver download, `spacy download en_core_web_md`, and the `x86` / `arm` / `x86-final` / `arm-final` multi-stage split — that split existed only to handle Chrome. With Chrome gone the image is architecture-neutral, which closes the upstream roadmap item "Docker image that builds on both arm and x86".

Expected image size: ~250 MB, down from ~2 GB.

## Deletions

Removed from the fork, recoverable from git history:

`download.py`, `embed.py` (upstream app; the name is reused by the new embedding script), `embed_openai.py`, `conf2year.py`, `cvpr-2023-embeddings.npy`, `cvpr_2023_embeddings_openai.npy`, `cvpr_2023_papers.json`.

`.gitignore` loses the `data/*.json` and `data/*.npy` entries, since the CVPR 2026 artifacts are now tracked.

## Git

No remote operations. `origin` still points at `dataplayer12/cvpr-explorer` and nothing is pushed. Creating a new GitHub repo is a separate, explicit decision.

## Success criteria

1. `python scrape.py` produces a 4068-entry JSON with no empty abstracts.
2. `python embed.py` produces a `[4068, 768]` float32 array with no NaN.
3. `python layout.py` produces a layout whose point count matches the paper count, and prints a cluster list where recognizable CVPR 2026 topics are identifiable by name.
4. `python app.py` boots in under 5 seconds and serves an interactive map on :8050; clicking a point shows its title, abstract, and a working PDF link.
5. `docker build` succeeds and `docker run` serves the same app.
