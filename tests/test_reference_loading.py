import pytest

from cli.main import load_reference_text


@pytest.mark.unit
def test_load_reference_text_supports_html(tmp_path):
    html_file = tmp_path / "reference.html"
    html_file.write_text(
        """
        <html>
          <head><title>Reference Title</title></head>
          <body><article><p>Reference body.</p></article></body>
        </html>
        """,
        encoding="utf-8",
    )
    text = load_reference_text(html_file)
    assert "Reference Title" in text
    assert "Reference body." in text


@pytest.mark.unit
def test_load_reference_text_supports_markdown(tmp_path):
    md_file = tmp_path / "reference.md"
    md_file.write_text("# Reference\n\nBody text.", encoding="utf-8")
    text = load_reference_text(md_file)
    assert text == "# Reference\n\nBody text."


@pytest.mark.unit
def test_load_reference_text_supports_pdf_dispatch(tmp_path, monkeypatch):
    pdf_file = tmp_path / "reference.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake")

    monkeypatch.setattr(
        "cli.main.extract_reference_text_from_pdf_file",
        lambda path: "# PDF Reference\n\nExtracted body.\n",
    )
    text = load_reference_text(pdf_file)
    assert "PDF Reference" in text
