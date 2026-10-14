"""build/library.py on a temporary library with awkward folder names. The PDFs are written by a tiny helper."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "build"))
import library  # noqa: E402

pytestmark = pytest.mark.skipif(not (library._poppler("pdftotext") and library._poppler("pdfinfo")),
                                reason="poppler not installed")


def make_pdf(path: Path, pages: list[str]) -> Path:
    """A minimal real PDF, text per page, \\n starts a new line (empty string = a page with no text, like a scan)."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for t in pages:
        n = len(objs) + 1
        kids.append(f"{n} 0 R")
        esc = t.encode("latin-1", "replace").decode("latin-1").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        lines = "".join(f"({ln}) '\n" for ln in esc.split("\n"))
        stream = f"BT /F1 6 Tf 7 TL 20 780 Td\n{lines}ET" if t else ""
        objs += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {n + 1} 0 R "
                 f"/Resources << /Font << /F1 3 0 R >> >> >>", f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"]
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(pages)} >>"
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    return path


@pytest.fixture
def lib(tmp_path, monkeypatch):
    root = tmp_path / "sources/library"
    monkeypatch.setenv("STEM_LIBRARY_ROOT", str(root))
    make_pdf(root / "My Notes/Chemistry/Électrolyse.pdf", ["Electrolysis moves ions to the cathode", "Faraday constant and charge"])
    make_pdf(root / "Maths Textbook Ch3/Quadratics.pdf", ["The discriminant decides the number of roots", "Completing the square example"])
    make_pdf(root / "日本語 ノート/deep/er/Waves.pdf", ["Standing waves have nodes and antinodes"])
    (root / "Empty Shelf").mkdir()
    return root


def run(capsys, *args):
    code = library.main(list(args))
    return code, capsys.readouterr().out


def test_tree_lists_every_depth_and_empty_folders(lib, capsys):
    code, out = run(capsys, "tree")
    assert code == 0
    for s in ("My Notes/", "Chemistry/", "Électrolyse.pdf", "2 pages", "日本語 ノート/", "Waves.pdf", "1 pages"):
        assert s in out
    assert "Empty Shelf/  (empty)" in out
    assert "Quadratics.pdf" not in run(capsys, "tree", "chemistry")[1]


def test_search_ranks_and_ignores_case_and_accents(lib, capsys):
    out = run(capsys, "search", "ELECTROLYSE ions")[1]
    assert out.splitlines()[0].count(" · ") == 2 and "Électrolyse.pdf · page 1 · " in out
    assert "cathode" in out
    assert "page 2" in run(capsys, "search", "faraday")[1]


def test_and_first_then_or_fallback(lib, capsys):
    out = run(capsys, "search", "discriminant roots")[1]
    assert "Quadratics.pdf · page 1" in out
    out = run(capsys, "search", "discriminant nodes")[1]  # no page has both: any-word fallback
    assert "Quadratics.pdf" in out and "Waves.pdf" in out
    assert "no match" in run(capsys, "search", "zzzz")[1]


def test_folder_filter_and_roots(lib, capsys):
    assert "Waves.pdf" not in run(capsys, "search", "waves OR discriminant", "--folder", "maths")[1]
    assert "Waves.pdf" in run(capsys, "search", "nodes", "--folder", "ノート")[1]
    make_pdf(lib.parent / "papers/9702/qp.pdf", ["Standing waves question"])
    assert "qp.pdf" not in run(capsys, "search", "standing")[1]
    assert "qp.pdf" in run(capsys, "search", "standing", "--root", "papers")[1]
    both = run(capsys, "search", "standing", "--root", "all")[1]
    assert "qp.pdf" in both and "Waves.pdf" in both
    assert run(capsys, "search", "x", "--root", "nope")[0] == 1


def test_text_pages_cap_and_ambiguity(lib, capsys):
    out = run(capsys, "text", "quadratics", "--pages", "2")[1]
    assert out.startswith("--- page 2 ---") and "Completing the square" in out and "discriminant" not in out
    assert out.count("--- page") == 1
    code, out = run(capsys, "text", "chemistry/electrolyse")
    assert code == 0 and "--- page 1 ---" in out and "--- page 2 ---" in out
    make_pdf(lib / "Maths Textbook Ch3/Quadratics 2.pdf", ["more"])
    code, out = run(capsys, "text", "quadratics")
    assert code == 1 and "matches 2 PDFs" in out and "Quadratics 2.pdf" in out
    assert run(capsys, "text", "nothing-here")[0] == 1
    make_pdf(lib / "Big/big.pdf", ["\n".join(["word " * 12] * 120)] * 2)
    assert "cut at 12000" in run(capsys, "text", "big.pdf")[1]
    assert "cut at" not in run(capsys, "text", "big.pdf", "--all")[1]


def test_cache_is_used_and_refreshed_on_change(lib, capsys, monkeypatch):
    run(capsys, "search", "discriminant")
    assert len(list((lib / ".cache").glob("*.json"))) == 3
    monkeypatch.setattr(library, "extract", lambda p: pytest.fail("re-extracted an unchanged file"))
    assert "Quadratics.pdf" in run(capsys, "search", "discriminant")[1]
    monkeypatch.undo()
    monkeypatch.setenv("STEM_LIBRARY_ROOT", str(lib))
    make_pdf(lib / "Maths Textbook Ch3/Quadratics.pdf", ["Vieta formulas link roots", "and more text here too"])
    assert "Vieta" in run(capsys, "search", "vieta")[1]
    assert "no match" in run(capsys, "search", "discriminant")[1]


def test_scanned_pdf_is_reported_not_fatal(lib, capsys):
    make_pdf(lib / "Scans/old.pdf", ["", ""])
    code, out = run(capsys, "search", "discriminant")
    assert code == 0 and "no text layer: needs OCR" in out and "Quadratics.pdf" in out
    assert run(capsys, "text", "old.pdf")[0] == 1


def test_corrupt_pdf_is_skipped(lib, capsys):
    (lib / "Bad").mkdir()
    (lib / "Bad/broken.pdf").write_text("not a pdf")
    code, out = run(capsys, "search", "discriminant")
    assert code == 0 and "broken.pdf" in out and "Quadratics.pdf" in out


def test_empty_library_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STEM_LIBRARY_ROOT", str(tmp_path / "nothing/library"))
    for args in (("tree",), ("search", "x"), ("for", "9702-5.1")):
        assert "library is empty: drop PDFs in sources/library/<any folder>" in run(capsys, *args)[1]


def test_for_builds_queries_from_the_chapters_kcs(lib, tmp_path, monkeypatch, capsys):
    import json
    g = tmp_path / "specs/9702"
    g.mkdir(parents=True)
    (g / "graph.json").write_text(json.dumps({
        "subtopics": [{"id": "9702-9.9", "title": "Waves and roots", "topic": "9702-9"}],
        "kcs": [{"id": "9702-9.9.1", "subtopic": "9702-9.9", "title": "Standing waves", "statement": "s",
                 "glossary": ["node", "antinode"]},
                {"id": "9702-9.9.2", "subtopic": "9702-9.9", "title": "Quantum chromodynamics", "statement": "s",
                 "glossary": []}]}))
    monkeypatch.setenv("STEM_LIBRARY_SPECS", str(tmp_path / "specs"))
    code, out = run(capsys, "for", "9702-9.9")
    assert code == 0 and "9702-9.9.1 Standing waves" in out and "Waves.pdf · page 1 · may add:" in out
    assert "nothing in the library" in out
    assert run(capsys, "for", "9702-0.0")[0] == 1


def test_no_reader_gives_one_plain_line(lib, monkeypatch, capsys):
    monkeypatch.setattr(library, "_poppler", lambda n: None)
    monkeypatch.setitem(sys.modules, "pypdf", None)
    code, out = run(capsys, "search", "x")
    assert code == 1 and out.count("\n") == 1 and "no PDF reader" in out


def test_cli_runs_as_a_script(lib):
    r = subprocess.run([sys.executable, str(REPO / "build/library.py"), "search", "faraday"],
                       capture_output=True, text=True, env={"STEM_LIBRARY_ROOT": str(lib), "PATH": "/usr/bin:/opt/homebrew/bin"})
    assert r.returncode == 0 and "page 2" in r.stdout
