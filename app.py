"""CVPR 2026 Explorer: served Dash app.

Reads the precomputed data/cvpr_2026_papers.json and
data/cvpr_2026_layout.json artifacts at import time and does no
further computation. Run the offline pipeline (scrape.py, embed.py,
layout.py) first if these files are missing.
"""
import json
import os

import plotly.graph_objects as go
import dash
from dash import dcc, html
from dash.dependencies import Input, Output

PAPERS_PATH = "data/cvpr_2026_papers.json"
LAYOUT_PATH = "data/cvpr_2026_layout.json"


def _load(path, producing_script):
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Missing data artifact {path!r}. Run `python {producing_script}` "
            "to produce it before starting the app."
        )
    with open(path, "r") as f:
        return json.load(f)


papers = _load(PAPERS_PATH, "scrape.py")
layout_data = _load(LAYOUT_PATH, "layout.py")

clusters = layout_data["clusters"]
points = layout_data["points"]

assert len(points) == len(papers), (
    f"point count {len(points)} != paper count {len(papers)}"
)


def create_scatter_plot():
    fig = go.Figure()

    # Group point indices by cluster id.
    by_cluster = {}
    for idx, point in enumerate(points):
        by_cluster.setdefault(point["cluster"], []).append(idx)

    # "unclustered" (-1) first, so it renders underneath everything else.
    cluster_ids = sorted(by_cluster.keys(), key=lambda c: (c != -1,))

    for cluster_id in cluster_ids:
        idxs = by_cluster[cluster_id]
        name = clusters[str(cluster_id)]
        xs = [points[i]["x"] for i in idxs]
        ys = [points[i]["y"] for i in idxs]
        titles = [papers[i]["title"] for i in idxs]
        customdata = [
            [papers[i]["pdf_link"], papers[i]["title"], papers[i]["abstract"]]
            for i in idxs
        ]

        marker = dict(size=6)
        if cluster_id == -1:
            marker["color"] = "grey"

        fig.add_trace(
            go.Scattergl(
                x=xs,
                y=ys,
                mode="markers",
                name=name,
                marker=marker,
                text=titles,
                customdata=customdata,
                hovertemplate="<b>%{text}</b><extra></extra>",
            )
        )

    fig.update_layout(
        autosize=True,
        margin=dict(l=50, r=50, b=50, t=50, pad=4),
        paper_bgcolor="#111111",
        plot_bgcolor="#111111",
        font=dict(color="white"),
        title="CVPR 2026 — SPECTER2 Semantic Map",
        title_font=dict(size=24),
        title_x=0.5,
        legend=dict(font=dict(color="white")),
    )
    return fig


app = dash.Dash(__name__)
app.title = "CVPR 2026 Explorer"

app.layout = html.Div(
    children=[
        dcc.Graph(
            id="scatter-plot",
            figure=create_scatter_plot(),
            style={"height": "80vh"},
        ),
        html.Div(
            children=[
                html.Div(id="pdf-link"),
                html.Div(id="title"),
                html.Div(id="abstract"),
                html.Div(
                    children=[
                        html.P(
                            "A 2D semantic map of all 4068 CVPR 2026 papers, "
                            "built from SPECTER2 embeddings."
                        ),
                        html.P(
                            "Find similar papers from nearby points on the map."
                        ),
                        html.P(
                            "Click on a data point to view the title, "
                            "abstract, and open the PDF link."
                        ),
                    ],
                    style={
                        "color": "white",
                        "textAlign": "center",
                        "marginTop": "20px",
                    },
                ),
                dcc.Link(
                    "GitHub",
                    href="https://github.com/dataplayer12/cvpr-explorer",
                    target="_blank",
                    style={
                        "display": "inline-block",
                        "backgroundColor": "#6c757d",
                        "color": "white",
                        "padding": "10px",
                        "textDecoration": "none",
                    },
                ),
            ],
            style={"marginTop": "20px", "marginBottom": "0"},
        ),
    ],
    style={
        "backgroundColor": "#111111",
        "color": "white",
        "display": "flex",
        "flexDirection": "column",
    },
)


@app.callback(
    [
        Output("pdf-link", "children"),
        Output("title", "children"),
        Output("abstract", "children"),
    ],
    Input("scatter-plot", "clickData"),
)
def update_link_and_abstract(click_data):
    if click_data is not None:
        href, title, abstract = click_data["points"][0]["customdata"]
        return (
            html.A(
                "Open PDF", href=href, target="_blank", style={"color": "white"}
            ),
            html.P(f"Title: {title}", style={"color": "white"}),
            html.P(f"Abstract: {abstract}", style={"color": "white"}),
        )
    return "", "", ""


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
