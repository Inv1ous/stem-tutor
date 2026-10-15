"""build/glyphs.py: Unicode sub/superscript letters in content (Eₖ, vᵢₙᵢₜᵢₐₗ) are found and written as LaTeX; the safe
glyphs (H₂O, m s⁻², 10⁻³, xⁿ) are left alone; files keep their formatting. Hermetic apart from the real-content check."""
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "build"))
import glyphs  # noqa: E402


@pytest.mark.parametrize("raw,want", [
    ("Eₖ", "$E_k$"), ("The energy Eₖ rises.", "The energy $E_k$ rises."), ("vᵢₙᵢₜᵢₐₗ", "$v_{initial}$"),
    ("the speed vᵢₙᵢₜᵢₐₗ, then", "the speed $v_{initial}$, then"), ("Kₚ = 2.96 × 10⁻⁹ Pa⁻¹", "$K_p$ = 2.96 × 10⁻⁹ Pa⁻¹"),
    ("CₙH₂ₙ₊₁OH", "$C_nH_{2n+1}OH$"), ("NOₓ,", "$NO_x$,"), ("ΔHₙₑuₜ?", "$ΔH_{neut}$?"), ("Eₐ₁ and Eₐ₂", "$E_{a1}$ and $E_{a2}$"),
    ("Viₙ and Vₒuₜ", "$V_{in}$ and $V_{out}$"), ("xᵃ", "$x^a$"), ("10ᵗʰ", "$10^{th}$"), ("neutrino ν ₑ", "neutrino $ν_e$"),
    ("a stray ₙ here", "a stray _n here"),  # nothing to hang on: plain linear text
    ("inside $Eₖ = ½mv²$ maths", "inside $E_k = ½mv²$ maths"),  # in a span the run is replaced in place, no new $
    ("$$Kₚ$$", "$$K_p$$"), (r"\(Wₛ\)", r"\(W_s\)"),
    ("Tₕₑ C–C–C bₒₙd ₐₙgₗₑₛ ₐrₑ ₐₗₗ ₁₂₀°", "The C–C–C bond angles are all 120°"),  # a font accident: back to letters
])
def test_unsafe_runs_become_latex(raw, want):
    assert glyphs.fix_text(raw) == want


@pytest.mark.parametrize("safe", ["H₂O", "m s⁻² and 10⁻³", "Cu²⁺", "xⁿ", "¹⁴₆C", "∫₀¹ x² dx", "E_k and $E_k$", "T½", "plain", ""])
def test_safe_glyphs_and_plain_text_come_back_unchanged(safe):
    assert glyphs.fix_text(safe) == safe and glyphs.problems(safe) == []


def test_fix_text_is_idempotent_and_leaves_nothing_unsafe():
    for raw in ("Eₖ and Kₚ, CₙH₂ₙ₊₁OH, xᵃ², $Wₛ$, ν ₑ, a ₙ"):
        once = glyphs.fix_text(raw)
        assert glyphs.fix_text(once) == once and glyphs.problems(once) == []


def test_problems_say_what_to_write_instead():
    found = glyphs.problems("The energy Eₖ and speed vᵢₙᵢₜᵢₐₗ")
    assert len(found) == 2 and "'Eₖ'" in found[0] and "'$E_k$'" in found[0] and "$v_{initial}$" in found[1]


def test_json_is_rewritten_string_by_string_keeping_the_file_as_it_was(tmp_path):
    text = ('{\n "id": "9702-3.2-Eₖ",\n "Eₖ": "a key stays",\n "items": [\n  {"stem": "Find Eₖ.\\nThen Eₖ\\u0003x", '
            '"n": 3, "ok": true}\n ],\n "safe": "H₂O"\n}\n')
    f = tmp_path / "pack.json"
    f.write_text(text, encoding="utf-8")
    new, n = glyphs.fix_file_text(f, text)
    assert n == 1 and new.endswith("}\n") and new.count("\n") == text.count("\n")
    data = json.loads(new)
    assert data["id"] == "9702-3.2-Eₖ" and "Eₖ" in data and data["items"][0]["stem"] == "Find $E_k$.\nThen $E_k$\x03x"
    assert data["safe"] == "H₂O"
    assert new.replace("$E_k$", "Eₖ") == text  # nothing else moved


def test_the_cli_lists_by_default_and_writes_only_with_write(tmp_path, capsys):
    pack = tmp_path / "packs" / "p.json"
    pack.parent.mkdir()
    pack.write_text(json.dumps({"stem": "Eₖ rises", "id": "x"}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    note = tmp_path / "n.md"
    note.write_text("# Note\n\nThe speed vᵢₙᵢₜᵢₐₗ.\n", encoding="utf-8")
    assert glyphs.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "p.json: 1 string" in out and "n.md: 1 string" in out and "dry run" in out and "'$E_k$'" in out
    assert "Eₖ" in pack.read_text(encoding="utf-8")
    glyphs.main(["--write", str(tmp_path)])
    assert json.loads(pack.read_text(encoding="utf-8")) == {"stem": "$E_k$ rises", "id": "x"}
    assert pack.read_text(encoding="utf-8").endswith("}\n") and note.read_text(encoding="utf-8") == "# Note\n\nThe speed $v_{initial}$.\n"
    assert glyphs.main([str(tmp_path)]) == 0 and "0 strings in 0 files" in capsys.readouterr().out


def test_python_string_literals_are_patched_and_the_script_still_compiles(tmp_path):
    f = tmp_path / "gen.py"
    f.write_text("x = 'Use Mᵣ=mRT/pV here'\ny = 'safe H₂O'\nz = f'{x} Eₖ'\n", encoding="utf-8")
    new, n = glyphs.fix_file_text(f, f.read_text(encoding="utf-8"))
    assert n == 1 and "$M_r$=mRT/pV" in new and "safe H₂O" in new and "z = f'{x} Eₖ'" in new  # an f-string is reported only
    compile(new, "gen.py", "exec")


def test_the_real_content_has_no_unsafe_glyphs_left():
    bad = []
    for root, pattern in (("build/out/packs", "*.json"), ("build/out/notes", "*.md"), ("build/work/teach", "*.json")):
        for f in sorted((REPO / root).rglob(pattern)):
            text = f.read_text(encoding="utf-8")
            if any(c in text for c in glyphs.UNSAFE_GLYPHS):
                bad.append(f.name)
    assert not bad, bad
