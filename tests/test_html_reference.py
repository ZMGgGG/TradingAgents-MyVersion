import pytest

from tradingagents.evaluation.html_reference import extract_reference_text_from_html_file


@pytest.mark.unit
def test_extract_reference_text_from_html_file(tmp_path):
    html_file = tmp_path / "sample.html"
    html_file.write_text(
        """
        <html>
          <head>
            <title>Test Research</title>
            <meta name="description" content="A short summary.">
          </head>
          <body>
            <article>
              <h1>Headline</h1>
              <p>First paragraph.</p>
              <p>Second paragraph.</p>
              <script>console.log("ignore me")</script>
            </article>
          </body>
        </html>
        """,
        encoding="utf-8",
    )
    text = extract_reference_text_from_html_file(html_file)
    assert "# Test Research" in text
    assert "A short summary." in text
    assert "First paragraph." in text
    assert "ignore me" not in text
