"""Settings shared by every pipeline script."""

NAME = "CVPR 2026"
SLUG = "cvpr_2026"
YEAR = 2026

PAPERS_PATH = f"data/{SLUG}_papers.json"
EMBEDDINGS_PATH = f"data/{SLUG}_specter2.npy"
LAYOUT_PATH = f"data/{SLUG}_layout.json"
SITE_DIR = "site"

# Values substituted into templates/index.html by build_site.py.
REPO_URL = "https://github.com/flecomet/cvpr-explorer"
SOURCE_NAME = "CVF Open Access"
SOURCE_URL = "https://openaccess.thecvf.com/CVPR2026?day=all"
STORAGE_PREFIX = "cvpr-explorer"
CSV_NAME = "cvpr2026-saved.csv"

# CVF open-access site, read by scrape.py.
CVF_URL = "https://openaccess.thecvf.com"
LISTING_URL = f"{CVF_URL}/CVPR2026?day=all"
