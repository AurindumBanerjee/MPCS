import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import tempfile
import json
from hkg.ingest.parse_html import extract_html_with_markup, parse_html_source
from bs4 import BeautifulSoup


def test_html_markup_preservation():
    html_sample = "<p><b>Fear of death</b>, with <i>extreme restlessness</i> and ANGUISH.</p>"
    soup = BeautifulSoup(html_sample, "html.parser")
    marked = extract_html_with_markup(soup)
    assert "**Fear of death**" in marked
    assert "_extreme restlessness_" in marked
    assert "ANGUISH" in marked


def test_parse_html_source_sections():
    sample_doc = """
    <html>
      <body>
        <h1>Arsenicum album</h1>
        <p>White Oxide of Arsenic. A valuable remedy.</p>
        <h3>Mind</h3>
        <p><b>Great anguish and restlessness.</b> Fear of death; thinks it useless to take medicine.</p>
        <h3>Stomach</h3>
        <p>Burning pain. Cannot bear the sight or smell of food. <i>Great thirst</i>; drinks much, but little at a time.</p>
        <h3>Modalities</h3>
        <p>Worse, wet weather, after midnight. Better, from heat, warm drinks.</p>
        <h3>Relationship</h3>
        <p>Compare: Acon., Bell., Phosphorus.</p>
      </body>
    </html>
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_path = Path(tmpdir) / "test_boericke.html"
        doc_path.write_text(sample_doc, encoding="utf-8")

        out_jsonl = parse_html_source(doc_path, source_key="test_source", output_dir=Path(tmpdir))
        assert out_jsonl.exists()

        records = [json.loads(line) for line in out_jsonl.read_text(encoding="utf-8").splitlines() if line]
        assert len(records) >= 4

        sections = [r["section"] for r in records]
        assert "Mind" in sections
        assert "Stomach" in sections
        assert "Modalities" in sections
        assert all(r["remedy_name"] == "Arsenicum album" for r in records)
