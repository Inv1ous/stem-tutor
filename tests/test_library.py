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


# ---------- figures: candidates, page images, crops, extraction, provenance ----------

def make_figure_pdf(path: Path, pages: list[dict], images: dict | None = None, page_extra: str = "") -> Path:
    """A real PDF with drawing ops per page. page = {"ops": content stream, "images": [names]}; images = {name: (w, h)}
    become shared RGB image objects, so one name on several pages is one repeated image (a logo)."""
    imgs = images or {}
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    ids = {}
    for nm, (w, h) in imgs.items():
        data = bytes((x * 7 + y * 3 + k * 50) % 256 for y in range(h) for x in range(w) for k in range(3))
        objs.append((w, h, data))
        ids[nm] = len(objs)
    kids = []
    for p in pages:
        n = len(objs) + 1
        kids.append(n)
        xo = "".join(f"/{k} {ids[k]} 0 R " for k in p.get("images", []))
        objs += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] {page_extra} /Contents {n + 1} 0 R "
                 f"/Resources << /Font << /F1 3 0 R >> /XObject << {xo}>> >> >>",
                 f"<< /Length {len(p['ops'])} >>\nstream\n{p['ops']}\nendstream"]
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>"
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        if isinstance(o, tuple):
            out += (f"{i} 0 obj\n<< /Type /XObject /Subtype /Image /Width {o[0]} /Height {o[1]} /ColorSpace /DeviceRGB "
                    f"/BitsPerComponent 8 /Length {len(o[2])} >>\nstream\n").encode() + o[2] + b"\nendstream\nendobj\n"
        else:
            out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out)
    return path


def txt(x, y, s, size=12):
    return f"BT /F1 {size} Tf {x} {y} Td ({s}) Tj ET\n"


def im(name, x, y, w, h):
    return f"q {w} 0 0 {h} {x} {y} cm /{name} Do Q\n"


BODY = txt(72, 740, "Chapter one intro text here and more words") + txt(72, 720, "Another line of the body text of the page")
VECTOR = BODY + "0.5 g 150 400 300 200 re f 0 G 2 w 150 400 300 200 re S\n" + txt(150, 380, "Figure 1.2 A test") \
    + txt(72, 340, "Text after the figure continues here for a while")


@pytest.fixture
def figs(lib, tmp_path, monkeypatch):
    monkeypatch.setenv("STEM_LIBRARY_ASSETS", str(tmp_path / "assets"))
    pages = [{"ops": VECTOR},
             {"ops": BODY + im("Pic", 150, 450, 300, 225) + txt(150, 430, "Fig. 4 Raster test") + im("Logo", 500, 740, 80, 40),
              "images": ["Pic", "Logo"]},
             {"ops": BODY + im("Logo", 500, 740, 80, 40), "images": ["Logo"]},
             {"ops": BODY + im("Logo", 500, 740, 80, 40), "images": ["Logo"]},
             {"ops": txt(72, 700, "Page of sparse words only") + "0 0 1 RG 100 100 300 300 re S\n"}]
    make_figure_pdf(lib / "Physics/Book.pdf", pages, {"Pic": (200, 150), "Logo": (160, 130)})
    return lib


def test_figures_lists_captions_with_boxes_rasters_and_skips_logos(figs, capsys):
    code, out = run(capsys, "figures", "physics/book")
    lines = out.splitlines()
    cap = next(x for x in lines if x.startswith("p1c1 · page 1 · caption · Figure 1.2 A test · box "))
    x0, y0, x1, y1 = map(float, cap.rsplit("box ", 1)[1].split(","))
    assert 0 <= x0 < x1 <= 1 and 0.09 < y0 < 0.25 and 0.4 < y1 <= 0.51  # the drawn rectangle sits in between
    assert any(x.startswith("p2i1 · page 2 · raster 200x150px") for x in lines)
    assert any("p2c1 · page 2 · caption · Fig. 4 Raster test" in x for x in lines)
    assert sum("skip: decorative" in x and "the same image on 3 pages" in x for x in lines) == 3
    assert any(x.startswith("p5v · page 5 · vector?") for x in lines)
    assert code == 0 and run(capsys, "figures", "physics/book", "--pages", "3")[1].startswith("skip: decorative")
    assert run(capsys, "figures", "physics/book", "--pages", "9")[0] == 1


def test_page_renders_a_png_or_a_part_of_it(figs, capsys):
    from PIL import Image
    path = Path(run(capsys, "page", "physics/book", "1", "--dpi", "72")[1].strip())
    assert path.is_file() and Image.open(path).size == (612, 792) and ".cache/pages" in str(path)
    part = Path(run(capsys, "page", "physics/book", "1", "--dpi", "72", "--box", "0,0,0.5,0.5")[1].strip())
    assert Image.open(part).size == (306, 396)
    assert run(capsys, "page", "physics/book", "1", "--box", "0.5,0,0.2,1")[0] == 1
    assert run(capsys, "page", "physics/book", "7")[0] == 1


def test_crop_writes_trimmed_png_sidecar_and_embed_lines(figs, capsys, tmp_path):
    import hashlib
    import json

    from PIL import Image
    args = ("crop", "physics/book", "--page", "1", "--box", "0,0.1,1,0.5", "--dpi", "100", "--to", "9702/9702-1.2 Rect!",
            "--caption", "A test", "--for", "9702-1.2", "--kc", "9702-1.2.1", "--why", "shows it")
    code, out = run(capsys, *args)
    png = tmp_path / "assets/9702/9702-1-2-rect.png"
    assert code == 0 and png.is_file()
    assert "![[Assets/9702/9702-1-2-rect.png]]" in out.splitlines()
    assert "*Figure: A test (source: Book, p.1)*" in out.splitlines()
    w, h = Image.open(png).size
    assert w < 100 * 612 / 72 * 0.6 and h < 100 * 792 / 72 * 0.4  # the empty margins are trimmed (rectangle is 300x200 pt)
    d = json.loads((tmp_path / "assets/9702/9702-1-2-rect.png.json").read_text())
    assert d["page"] == 1 and d["box"] == [0, 0.1, 1, 0.5] and d["dpi"] == 100 and d["caption"] == "A test"
    assert d["subtopic"] == "9702-1.2" and d["kc"] == "9702-1.2.1" and d["why"] == "shows it" and d["pdf"].endswith("Book.pdf")
    assert d["sha256"] == hashlib.sha256(png.read_bytes()).hexdigest() and d["created"]
    before = png.read_bytes()
    code, out = run(capsys, *args)
    assert code == 1 and "already exists" in out and png.read_bytes() == before  # never overwritten


def test_crop_refuses_small_blank_bad_input_and_big(figs, capsys, monkeypatch):
    base = ("crop", "physics/book", "--page", "1")
    code, out = run(capsys, *base, "--box", "0.30,0.25,0.45,0.30", "--to", "9702/tiny", "--dpi", "72")
    assert code == 1 and "under 150x100" in out and out.count("\n") == 1
    assert "blank" in run(capsys, *base, "--box", "0.0,0.9,1,1", "--to", "9702/blank")[1]
    assert run(capsys, *base, "--box", "nope", "--to", "9702/x")[0] == 1
    assert run(capsys, *base, "--box", "0,0,1,1", "--to", "nofolder")[0] == 1
    assert run(capsys, *base, "--box", "0,0,1,1", "--to", "9702/x", "--dpi", "900")[0] == 1
    monkeypatch.setattr(library, "MAX_BYTES", 1000)
    code, out = run(capsys, *base, "--box", "0,0.1,1,0.5", "--to", "9702/big")
    assert code == 1 and "over 6 MB: lower --dpi" in out and not list(Path(library.assets_dir()).glob("9702/big*"))


def test_extract_writes_the_embedded_image_unscaled(figs, capsys, tmp_path):
    import json

    from PIL import Image
    code, out = run(capsys, "extract", "physics/book", "--page", "2", "--index", "1", "--to", "9702/pic", "--caption", "Pic")
    png = tmp_path / "assets/9702/pic.png"
    assert code == 0 and Image.open(png).size == (200, 150) and "![[Assets/9702/pic.png]]" in out
    assert json.loads((tmp_path / "assets/9702/pic.png.json").read_text())["index"] == 1
    assert run(capsys, "extract", "physics/book", "--page", "2", "--index", "1", "--to", "9702/pic")[0] == 1
    assert "has no image 5" in run(capsys, "extract", "physics/book", "--page", "2", "--index", "5", "--to", "9702/p2")[1]


def test_cropped_and_rotated_pages_still_give_sane_boxes(lib, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("STEM_LIBRARY_ASSETS", str(tmp_path / "assets"))
    make_figure_pdf(lib / "Cropped.pdf", [{"ops": VECTOR}], page_extra="/CropBox [0 0 612 600]")
    line = run(capsys, "figures", "cropped")[1].splitlines()[0]
    y0, y1 = map(float, line.rsplit("box ", 1)[1].split(",")[1::2])
    assert 0.0 <= y0 < y1 and 0.3 < y1 < 0.4  # the cut page lost its top 192 pt: the caption (media y 403) is at 35%
    make_figure_pdf(lib / "Turned.pdf", [{"ops": VECTOR}], page_extra="/Rotate 90")
    assert "rotated: caption boxes unknown" in run(capsys, "figures", "turned")[1]


def test_figure_problems_check_file_sha_sidecar_and_source_caption(figs, capsys, tmp_path):
    run(capsys, "crop", "physics/book", "--page", "1", "--box", "0,0.1,1,0.5", "--to", "9702/f1", "--caption", "A test")
    emb = "![[Assets/9702/f1.png]]"
    good = f"{emb}\n*Figure: A test (source: Book, p.1)*\n"
    assert library.figure_problems(good, "9702-1.2") == []
    assert library.figure_problems("![[Assets/9702/hand-made.png]]\n", "9702-1.2") == []  # no sidecar: not ours to check
    assert "source caption" in library.figure_problems(f"{emb}\n\n\n*Figure: A test (source: Book, p.1)*\n")[0]
    assert "source caption" in library.figure_problems(f"{emb}\n*Figure: A test (source: Other, p.1)*\n")[0]
    assert "source caption" in library.figure_problems(f"{emb}\n*Figure: A test (source: Book, p.9)*\n")[0]
    png = tmp_path / "assets/9702/f1.png"
    side = png.with_name("f1.png.json")
    side_text = side.read_text()
    side.write_text(side_text.replace('"page": 1', '"page": 3'))
    assert "source caption" in library.figure_problems(good)[0]
    side.write_text("{not json")
    assert "sidecar" in library.figure_problems(good)[0]
    side.write_text(side_text)
    png.write_bytes(png.read_bytes() + b"x")
    assert "sha does not match" in library.figure_problems(good)[0]
    png.unlink()
    assert "does not exist" in library.figure_problems(good)[0]
    assert library.sidecars_for("9702-1.2") == [] and library.sidecars_for("nope") == []
    side.write_text(side_text.replace('"subtopic": ""', '"subtopic": "9702-1.2"'))
    assert [d["file"] for d in library.sidecars_for("9702-1.2")] == [str(png)]
