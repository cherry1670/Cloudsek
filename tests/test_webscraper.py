from app.fetcher.webscraper import extract_metadata


def test_extract_metadata_reads_common_html_tags() -> None:
    html = """
    <html>
      <head>
        <title>Example Domain</title>
        <meta name="description" content="A sample page">
        <meta property="og:title" content="OG Example">
        <link rel="canonical" href="/canonical">
        <link rel="icon" href="/favicon.ico">
      </head>
    </html>
    """

    metadata = extract_metadata(html, "https://example.com/path")

    assert metadata["title"] == "Example Domain"
    assert metadata["description"] == "A sample page"
    assert metadata["open_graph"]["title"] == "OG Example"
    assert metadata["canonical_url"] == "https://example.com/canonical"
    assert metadata["favicon_url"] == "https://example.com/favicon.ico"
