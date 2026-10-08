"""Shared site code checked against this repository's own config and pipeline output."""
import json
import os
import re
import shutil
import subprocess

import pytest

import build_site
import config

# Fields build_site.build reads from every paper without a default.
REQUIRED = {
    "id", "title", "authors", "abstract", "pdf_link", "forum_link",
    "keywords", "tldr", "area", "decision", "track",
}

needs_data = pytest.mark.skipif(
    not (os.path.exists(config.PAPERS_PATH) and os.path.exists(config.LAYOUT_PATH)),
    reason="pipeline output not present",
)


@pytest.fixture(scope="module")
def data():
    with open(config.PAPERS_PATH) as f:
        papers = json.load(f)
    with open(config.LAYOUT_PATH) as f:
        layout = json.load(f)
    return papers, layout


@needs_data
def test_papers_have_every_field_build_site_reads(data):
    papers, _ = data
    missing = {k for p in papers for k in REQUIRED - p.keys()}
    assert not missing, f"papers lack {sorted(missing)}"
    assert len({p["id"] for p in papers}) == len(papers), "duplicate paper ids"
    assert all(p["title"] and p["abstract"] for p in papers)


@needs_data
def test_build_runs_on_this_repository_data(data):
    papers, layout = data
    core, details = build_site.build(papers, layout)
    assert core["meta"] == {"name": config.NAME, "n": len(papers)}
    assert len(details["abstract"]) == len(papers)
    assert all(core["nn"])


def test_rendered_page_script_parses(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    with open(build_site.TEMPLATE_PATH, encoding="utf-8") as f:
        page = build_site.render_index(f.read())
    scripts = re.findall(r"<script>(.*?)</script>", page, re.S)
    assert scripts, "no inline script in the page"
    js = tmp_path / "page.js"
    js.write_text("\n".join(scripts), encoding="utf-8")
    result = subprocess.run([node, "--check", str(js)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
