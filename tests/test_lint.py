from tutorlib import lint


def rules(md, **kw):
    return [f["rule"] for f in lint.lint(md, **kw)]


def test_clean_note_passes():
    md = "# Kinematics\n\nInline $v = u + at$ and display:\n\n$$\ns = ut + \\tfrac{1}{2}at^2\n$$\n\n$\\ce{H2O}$\n"
    assert lint.lint(md) == []


def test_paren_bracket_delimiters_rejected():
    assert "delimiter" in rules("Energy \\(E = mc^2\\) and \\[F = ma\\]")


def test_unbalanced_inline_dollar():
    assert "unbalanced-dollar" in rules("Speed is $v = d/t and time")


def test_space_inside_inline_math():
    assert "inline-space" in rules("Speed $ v = d/t$ here")


def test_dollar_in_code_ignored():
    assert lint.lint("Use `$PATH` and\n```bash\necho $HOME\n```\n") == []


def test_currency_dollar_escaped_ok():
    assert lint.lint("It costs \\$5 and \\$6.") == []


def test_display_math_in_callout_needs_prefix():
    bad = "> [!example] Worked\n> Step 1\n$$\nx = 2\n$$\n> Step 2\n"
    good = "> [!example] Worked\n> Step 1\n> $$\n> x = 2\n> $$\n> Step 2\n"
    assert "callout-math" in rules(bad)
    assert lint.lint(good) == []


def test_pipe_in_math_inside_table():
    md = "| a | b |\n|---|---|\n| $|x|$ | 2 |\n"
    assert "table-pipe" in rules(md)
    assert lint.lint("| a | b |\n|---|---|\n| $\\lvert x \\rvert$ | 2 |\n") == []


def test_unbalanced_braces_in_math():
    assert "braces" in rules("$\\frac{1}{2$")


def test_unsupported_macros():
    assert "unsupported-macro" in rules("$\\SI{3}{m}$")
    assert "unsupported-macro" in rules("$$\n\\chemfig{H-O-H}\n$$")


def test_mermaid_unknown_type_and_unquoted_parens():
    assert "mermaid-type" in rules("```mermaid\nflowhcart TD\nA-->B\n```")
    assert "mermaid-label" in rules("```mermaid\nflowchart TD\nA[Force (N)] --> B\n```")
    assert lint.lint('```mermaid\nflowchart TD\nA["Force (N)"] --> B\n```') == []


def test_mermaid_reserved_end_node():
    assert "mermaid-reserved" in rules("```mermaid\nflowchart LR\nstart --> end\n```")


def test_unclosed_code_fence():
    assert "fence" in rules("```mermaid\nflowchart TD\nA-->B\n")


def test_missing_embed_detected(tmp_path):
    (tmp_path / "Assets").mkdir()
    (tmp_path / "Assets" / "ok.svg").write_text("<svg viewBox='0 0 1 1'></svg>")
    md = "![[Assets/ok.svg]]\n![[Assets/missing.svg]]\n"
    assert rules(md, vault_root=tmp_path) == ["missing-embed"]


def test_inline_svg_without_viewbox():
    assert "svg-viewbox" in rules('<svg width="300" height="200"><line/></svg>')
