import pytest

from cli.main import discover_reference_reports


@pytest.mark.unit
def test_discover_reference_reports_filters_supported_files(tmp_path):
    root = tmp_path / "研报"
    root.mkdir()
    html_file = root / "a.html"
    pdf_file = root / "b.pdf"
    md_file = root / "c.md"
    ignored_dir = root / "sample_files"
    ignored_dir.mkdir()
    ignored_asset = ignored_dir / "x.css"
    html_file.write_text("<html></html>", encoding="utf-8")
    pdf_file.write_bytes(b"%PDF-1.4 fake")
    md_file.write_text("# md", encoding="utf-8")
    ignored_asset.write_text("body{}", encoding="utf-8")

    results = discover_reference_reports(root)
    names = {path.name for path in results}
    assert names == {"a.html", "b.pdf", "c.md"}
