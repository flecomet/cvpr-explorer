"""Scrape CVPR 2026 papers from the CVF open-access site.

Produces data/cvpr_2026_papers.json: a list of
{title, authors, abstract, pdf_link} in listing order.
"""
import json
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://openaccess.thecvf.com"
LISTING_URL = f"{BASE_URL}/CVPR2026?day=all"
OUTPUT_PATH = "data/cvpr_2026_papers.json"
MAX_WORKERS = 16
MAX_RETRIES = 3

_thread_local = threading.local()


def get_session():
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


def fetch_listing_hrefs():
    resp = requests.get(LISTING_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    hrefs = [a["href"] for a in soup.select(".ptitle a")]
    return hrefs


def parse_paper(url):
    session = get_session()
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.find("div", id="papertitle").text.strip()
    abstract = soup.find("div", id="abstract").text.strip()

    authors_div = soup.find("div", id="authors")
    authors_tag = authors_div.find("i") if authors_div else None
    authors = authors_tag.text.strip() if authors_tag else authors_div.text.strip()

    pdf_a = soup.find("a", string="pdf")
    if pdf_a is None:
        pdf_a = soup.find("a", href=lambda h: h and h.endswith(".pdf"))
    pdf_link = BASE_URL + pdf_a["href"]

    return {
        "title": title,
        "authors": authors,
        "abstract": abstract,
        "pdf_link": pdf_link,
    }


def fetch_with_retry(href):
    url = BASE_URL + href
    delay = 1.0
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return url, parse_paper(url)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
    return url, {"__error__": str(last_exc)}


def main():
    print(f"Fetching listing: {LISTING_URL}")
    hrefs = fetch_listing_hrefs()
    n_expected = len(hrefs)
    print(f"Found {n_expected} paper links in listing.")

    results_by_href = {}
    failures = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_href = {
            executor.submit(fetch_with_retry, href): href for href in hrefs
        }
        done = 0
        for future in as_completed(future_to_href):
            href = future_to_href[future]
            url, result = future.result()
            if "__error__" in result:
                failures.append((url, result["__error__"]))
            else:
                results_by_href[href] = result
            done += 1
            if done % 200 == 0 or done == n_expected:
                print(f"  fetched {done}/{n_expected}")

    if failures:
        print(f"\n{len(failures)} papers failed after {MAX_RETRIES} retries:")
        for url, err in failures:
            print(f"  {url}: {err}")
        sys.exit(1)

    # Preserve listing order.
    papers = [results_by_href[href] for href in hrefs]

    assert len(papers) == n_expected, (
        f"parsed paper count {len(papers)} != listing href count {n_expected}"
    )
    for p in papers:
        assert p["title"], f"empty title for paper: {p}"
        assert p["abstract"], f"empty abstract for paper: {p['title']!r}"

    import os
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(papers, f)

    print(f"Wrote {len(papers)} papers to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
