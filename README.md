# CVPR 2026 Explorer

A 2D semantic map of all 4068 CVPR 2026 papers, built from
[SPECTER2](https://huggingface.co/allenai/specter2) embeddings of their abstracts.
Nearby points are semantically similar papers, so a cluster is a topic.

**Live site: https://flecomet.github.io/cvpr-explorer/**

> This is a fork of [dataplayer12/cvpr-explorer](https://github.com/dataplayer12/cvpr-explorer)
> ([cvprexplorer.com](http://cvprexplorer.com)), rewritten for CVPR 2026: OpenAI embeddings
> replaced with the open SPECTER2 scientific-document model, automatic cluster labels, and a
> static front-end that needs no server. Original idea and design credit to
> [@dataplayer12](https://github.com/dataplayer12). Same license as upstream — see [LICENSE](LICENSE).

## Why

Conference sites list 4000+ papers as one flat list. Finding the ones you care about means
scrolling past thousands you don't. Here you zoom into the region of the map you're interested
in — diffusion, 3D reconstruction, medical imaging — and read only those.

## How it works

The pipeline is offline; the site is static.

| Step | Script | Output |
|------|--------|--------|
| Scrape titles, authors, abstracts, PDF links | `scrape.py` | `data/cvpr_2026_papers.json` |
| Embed abstracts with SPECTER2 | `embed.py` | `data/cvpr_2026_specter2.npy` |
| UMAP to 2D + HDBSCAN clusters + c-TF-IDF labels | `layout.py` | `data/cvpr_2026_layout.json` |
| Merge into the site payload | `build_site.py` | `site/data.json` |

`site/index.html` renders that payload client-side with plotly.js. No backend, no API keys at
serve time.

## Run the pipeline

```shell
pip install -r requirements-pipeline.txt
python scrape.py     # writes data/cvpr_2026_papers.json
python embed.py      # writes data/cvpr_2026_specter2.npy (GPU recommended)
python layout.py     # writes data/cvpr_2026_layout.json
```

## Serve locally

Static site (what the live URL serves):

```shell
python build_site.py
python -m http.server -d site 8000   # http://localhost:8000
```

Or the original Dash app:

```shell
pip install -r requirements.txt
python app.py                        # http://localhost:8050
```

Or with Docker:

```shell
docker compose build
docker compose up
```

## Deployment

Pushing to `main` runs `.github/workflows/pages.yml`, which rebuilds `site/data.json` and
publishes `site/` to GitHub Pages.

## Roadmap

- [x] SPECTER2 embeddings (open model, no API key)
- [x] 2D projection with clusters and automatic topic labels
- [x] Static site — no server, no cold start
- [x] Keyword search across titles and abstracts
- [ ] Mark papers with released code
- [ ] Add more conferences and years back
