"""Scrape the CVPR 2026 papers from the CVF open-access site.

Writes config.PAPERS_PATH: a list of {id, title, authors, abstract, pdf_link, forum_link,
keywords, tldr, area, decision, track, site} in listing order. CVF publishes no keywords,
TL;DR, primary area or presentation type, so those fields stay empty and decision is "other".
"""
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import config

MAX_WORKERS = 16
MAX_RETRIES = 3

_thread_local = threading.local()


def get_session():
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        _thread_local.session = session
    return session


def paper_id(url):
    """'.../html/Xiao_Foo_CVPR_2026_paper.html' or '.../papers/Xiao_Foo_CVPR_2026_paper.pdf'
    -> 'Xiao_Foo_CVPR_2026'."""
    return re.sub(r"_paper\.(html|pdf)$", "", url.rsplit("/", 1)[-1])


def page_url(pdf_link):
    """PDF link -> the paper's abstract page on the same site."""
    return re.sub(r"/papers/(.*)\.pdf$", r"/html/\1.html", pdf_link)


def to_record(title, authors, abstract, pdf_link):
    return {
        "id": paper_id(pdf_link),
        "title": " ".join(title.split()),
        "authors": " ".join(authors.split()),
        "abstract": " ".join(abstract.split()),
        "pdf_link": pdf_link,
        "forum_link": page_url(pdf_link),
        "keywords": [],
        "tldr": "",
        "area": "",
        "decision": "other",
        "track": "",
        "site": "",
    }


def fetch_listing_hrefs():
    resp = requests.get(config.LISTING_URL, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return [a["href"] for a in soup.select(".ptitle a")]


def parse_paper_html(html, url):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("div", id="papertitle").text
    abstract = soup.find("div", id="abstract").text

    authors_div = soup.find("div", id="authors")
    authors_tag = authors_div.find("i") if authors_div else None
    authors = authors_tag.text if authors_tag else authors_div.text

    pdf_a = soup.find("a", string="pdf")
    if pdf_a is None:
        pdf_a = soup.find("a", href=lambda h: h and h.endswith(".pdf"))
    return to_record(title, authors, abstract, urljoin(url, pdf_a["href"]))


def fetch_with_retry(href):
    url = config.CVF_URL + href
    delay = 1.0
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = get_session().get(url, timeout=30)
            resp.raise_for_status()
            return url, parse_paper_html(resp.text, url)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
    return url, {"__error__": str(last_exc)}


def main():
    print(f"Fetching listing: {config.LISTING_URL}")
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

    # Listing order, not id order: the committed embeddings follow this order.
    papers = [results_by_href[href] for href in hrefs]

    assert len({p["id"] for p in papers}) == len(papers), "duplicate paper ids"
    for p in papers:
        assert p["title"], f"empty title for paper: {p}"
        assert p["abstract"], f"empty abstract for paper: {p['title']!r}"

    os.makedirs(os.path.dirname(config.PAPERS_PATH), exist_ok=True)
    with open(config.PAPERS_PATH, "w") as f:
        json.dump(papers, f, ensure_ascii=False)

    print(f"Wrote {len(papers)} papers to {config.PAPERS_PATH}")


if __name__ == "__main__":
    main()
