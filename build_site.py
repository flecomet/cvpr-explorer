"""Build the static site payload served by GitHub Pages.

Merges data/cvpr_2026_papers.json and data/cvpr_2026_layout.json into a single
column-oriented site/data.json, which site/index.html renders client-side with
plotly.js. Run after the offline pipeline (scrape.py, embed.py, layout.py).
"""
import json
import os

PAPERS_PATH = "data/cvpr_2026_papers.json"
LAYOUT_PATH = "data/cvpr_2026_layout.json"
OUT_PATH = "site/data.json"


def main():
    with open(PAPERS_PATH) as f:
        papers = json.load(f)
    with open(LAYOUT_PATH) as f:
        layout_data = json.load(f)

    points = layout_data["points"]
    assert len(points) == len(papers), (
        f"point count {len(points)} != paper count {len(papers)}"
    )

    payload = {
        "clusters": layout_data["clusters"],
        # Column-oriented: ~15% smaller than a list of per-paper objects.
        "x": [round(p["x"], 3) for p in points],
        "y": [round(p["y"], 3) for p in points],
        "c": [p["cluster"] for p in points],
        "title": [p["title"] for p in papers],
        "authors": [p["authors"] for p in papers],
        "abstract": [p["abstract"] for p in papers],
        "pdf": [p["pdf_link"] for p in papers],
    }

    os.makedirs("site", exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(payload, f, separators=(",", ":"), ensure_ascii=False)

    mb = os.path.getsize(OUT_PATH) / 1e6
    print(f"wrote {OUT_PATH}: {len(papers)} papers, {mb:.1f} MB")


if __name__ == "__main__":
    main()
