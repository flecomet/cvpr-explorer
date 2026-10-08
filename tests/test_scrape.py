import scrape

URL = "https://openaccess.thecvf.com/content/CVPR2026/html/Lee_A_Paper_Title_CVPR_2026_paper.html"
PDF = "https://openaccess.thecvf.com/content/CVPR2026/papers/Lee_A_Paper_Title_CVPR_2026_paper.pdf"
PAGE = """<html><body>
<div id="papertitle">
  A  Paper Title</div>
<div id="authors"><b><i>Ann Lee, Bo Chen</i></b></div>
<div id="abstract"> First line.
 Second line. </div>
[<a href="/content/CVPR2026/papers/Lee_A_Paper_Title_CVPR_2026_paper.pdf">pdf</a>]
</body></html>"""


def test_page_and_pdf_share_an_id():
    assert scrape.paper_id(URL) == scrape.paper_id(PDF) == "Lee_A_Paper_Title_CVPR_2026"
    assert scrape.page_url(PDF) == URL


def test_parse_paper_html_fills_the_schema():
    p = scrape.parse_paper_html(PAGE, URL)
    assert p == {
        "id": "Lee_A_Paper_Title_CVPR_2026",
        "title": "A Paper Title",
        "authors": "Ann Lee, Bo Chen",
        "abstract": "First line. Second line.",
        "pdf_link": PDF,
        "forum_link": URL,
        "keywords": [],
        "tldr": "",
        "area": "",
        "decision": "other",
        "track": "",
        "site": "",
    }
