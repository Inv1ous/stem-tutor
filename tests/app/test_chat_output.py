"""The shared chat contract streams complete semantic blocks, never its transport."""
import json

import pytest

from tutor_app.chat_output import DocumentDecoder, DocumentError, document_instructions, document_schema


def wire(blocks, **extra):
    return json.dumps({"blocks": blocks, **extra}, ensure_ascii=False)


def block(kind, text):
    return {"kind": kind, "text": text}


def decode(source, speech=False):
    decoder = DocumentDecoder(speech=speech)
    streamed = decoder.feed(source)
    markdown, spoken = decoder.finish()
    assert streamed == markdown
    return decoder, markdown, spoken


BLOCKS = [block("paragraph", "Use \\(x_i^2\\) and 95%."), block("heading", "Method"),
          block("bullet", "First"), block("bullet", "Second"), block("step", "Substitute"),
          block("equation", r"F=ma"), block("step", "Calculate"),
          block("code", 'x_1 = {"key": "$5"}\n```\n• literal')]
EXPECTED = ('Use $x_i^2$ and 95%.\n\n**Method**\n\n- First\n\n- Second\n\n'
            '1. Substitute\n\n$$\nF=ma\n$$\n\n2. Calculate\n\n'
            '````\nx_1 = {"key": "$5"}\n```\n• literal\n````')


def test_every_json_split_has_identical_canonical_output_and_separate_speech():
    source = wire(BLOCKS, speech='Read this "separately". 🧪')
    for split in range(len(source) + 1):
        decoder = DocumentDecoder(speech=True)
        rendered = decoder.feed(source[:split]) + decoder.feed(source[split:])
        assert decoder.finish() == (EXPECTED, 'Read this "separately". 🧪')
        assert rendered == EXPECTED
        assert decoder.document == {"blocks": BLOCKS, "speech": 'Read this "separately". 🧪'}
        assert json.loads(decoder.wire) == decoder.document


def test_one_character_chunks_support_reordered_fields_escapes_and_unicode():
    source = '{"speech":"\\ud83e\\uddea","blocks":[{"text":"a \\\"quote\\\" \\\\ path / é","kind":"paragraph"}]}'
    decoder = DocumentDecoder(speech=True)
    rendered = ''.join(decoder.feed(c) for c in source)
    assert decoder.finish() == (rendered, '🧪')
    assert rendered == 'a "quote" \\ path / é'


def test_partial_blocks_never_leak_and_first_complete_block_streams_immediately():
    decoder = DocumentDecoder()
    assert decoder.feed('{"blocks":[{"kind":"paragraph","text":"Visible') == ''
    assert decoder.feed('"}') == 'Visible'
    assert decoder.feed(',{"text":"Next","kind":"bullet"}') == '\n\n- Next'
    assert decoder.feed(']}') == ''
    assert decoder.finish() == ('Visible\n\n- Next', '')


@pytest.mark.parametrize('source', [
    '', '{}', '{"blocks":[]}', '{"blocks":[{}]}', '{"blocks":[{"kind":"paragraph"}]}',
    '{"blocks":[{"kind":"other","text":"x"}]}',
    '{"blocks":[{"kind":"paragraph","text":"x","extra":"y"}]}',
    '{"blocks":[{"kind":"paragraph","kind":"heading","text":"x"}]}',
    '{"blocks":[{"kind":"paragraph","text":"x","text":"y"}]}',
    '{"blocks":[{"kind":"paragraph","text":"x"}],"blocks":[]}',
    '{"blocks":[{"kind":"paragraph","text":"x"}],"speech":"no"}',
    '{"blocks":[{"kind":"paragraph","text":"x"}],"extra":"no"}',
    '{"blocks":[{"kind":"paragraph","text":""}]}',
    '{"blocks":[{"kind":"paragraph","text":123}]}',
    '{"blocks":[{"kind":"paragraph","text":"x"},]}',
    '{"blocks":[{"kind":"paragraph","text":"x"}],}',
    '{"blocks":[{"kind":"paragraph","text":"x"}]} trailing',
    '{"blocks":[[[[[[[[[[[[[[[[[[[[',
])
def test_malformed_documents_fail_safely(source):
    with pytest.raises(DocumentError):
        decode(source)


@pytest.mark.parametrize('source', ['{', '{"blocks":[', '{"blocks":[{"text":"x',
                                    '{"blocks":[{"kind":"paragraph","text":"x"}'])
def test_incomplete_documents_never_finish_successfully(source):
    decoder = DocumentDecoder()
    decoder.feed(source)
    with pytest.raises(DocumentError, match='[Ii]ncomplete'):
        decoder.finish()


@pytest.mark.parametrize('text', ['\x00', '\x1b[31m', '\x85', '\ud800', '\u202e', '\r'])
@pytest.mark.parametrize('kind', ['paragraph', 'equation', 'code'])
def test_unsafe_decoded_controls_and_surrogates_are_rejected(kind, text):
    with pytest.raises(DocumentError):
        decode(json.dumps({'blocks': [block(kind, text)]}))


@pytest.mark.parametrize('text', [
    '• First • Second • Third • Fourth • Fifth', 'First\n\nSecond', '# Heading',
    '- First\n- Second', '1. First\n2. Second', 'Intro\n> quoted block',
    '```json\n{}\n```', '| A | B |\n|---|---|',
])
@pytest.mark.parametrize('kind', ['paragraph', 'heading', 'bullet', 'step'])
def test_prose_cannot_smuggle_markdown_blocks_or_inline_bullet_walls(kind, text):
    with pytest.raises(DocumentError):
        decode(wire([block(kind, text)]))


def test_math_and_literal_spans_preserve_dots_bullets_source_and_currency():
    text = r'Use $a • b$, $\ce{CuSO4.5H2O}$, `• literal • text`, [x](https://example.org/x_1) and $5.'
    _, shown, _ = decode(wire([block('paragraph', text)]))
    assert shown == text
    source = '\n\t{"a": "•"}\r\n\n'
    _, shown, _ = decode(wire([block('code', source)]))
    assert shown == '```\n' + source + '```'


def test_numbering_survives_equations_and_restarts_after_other_kinds():
    blocks = [block('step', 'A'), block('equation', 'x=1'), block('equation', 'y=2'),
              block('step', 'B'), block('paragraph', 'Pause'), block('step', 'C')]
    _, shown, _ = decode(wire(blocks))
    assert shown == '1. A\n\n$$\nx=1\n$$\n\n$$\ny=2\n$$\n\n2. B\n\nPause\n\n1. C'


def test_schema_and_instructions_describe_strict_contract_without_global_word_limit():
    plain, spoken = document_schema(), document_schema(speech=True)
    assert plain['additionalProperties'] is False
    assert plain['required'] == ['blocks']
    assert spoken['required'] == ['blocks', 'speech']
    assert 'speech' not in plain['properties']
    assert plain['properties']['blocks']['maxItems'] == 256
    assert set(plain['properties']['blocks']['items']['properties']['kind']['enum']) == {
        'paragraph', 'heading', 'bullet', 'step', 'equation', 'code'}
    for enabled in (False, True):
        instructions = document_instructions(speech=enabled)
        assert json.dumps(document_schema(speech=enabled), ensure_ascii=False) in instructions
        assert 'outer delimiters' in instructions
        assert '120' not in instructions


def test_speech_is_required_only_when_enabled_and_is_never_visual():
    with pytest.raises(DocumentError):
        decode(wire([block('paragraph', 'Hi')]), speech=True)
    with pytest.raises(DocumentError):
        decode(wire([block('paragraph', 'Hi')], speech='\x1b'), speech=True)
    _, shown, spoken = decode(wire([block('paragraph', 'Hi')], speech=''), speech=True)
    assert (shown, spoken) == ('Hi', '')


def test_wire_is_deterministic_and_decoder_has_terminal_lifecycle():
    left, _, _ = decode('{ "blocks" : [{"text":"é", "kind":"paragraph"}] }')
    right, _, _ = decode(wire([block('paragraph', 'é')]))
    assert left.wire == right.wire == '{"blocks":[{"kind":"paragraph","text":"é"}]}'
    assert left.finish() == ('é', '')
    with pytest.raises(DocumentError):
        left.feed(' ')
    broken = DocumentDecoder()
    with pytest.raises(DocumentError):
        broken.feed('[]')
    with pytest.raises(DocumentError):
        broken.feed('{}')


def test_document_and_block_bounds_apply_while_accumulating():
    with pytest.raises(DocumentError, match='[Dd]ocument.*limit'):
        DocumentDecoder().feed(' ' * (4 * 1024 * 1024 + 1))
    decoder = DocumentDecoder()
    decoder.feed('{"blocks":[{"text":"')
    with pytest.raises(DocumentError, match='[Bb]lock.*limit'):
        decoder.feed('x' * (256 * 1024))
    with pytest.raises(DocumentError, match='[Bb]lock.*limit'):
        DocumentDecoder().feed('{"blocks":[{' + ' ' * (256 * 1024))
    with pytest.raises(DocumentError, match='256'):
        decode(wire([block('paragraph', 'x')] * 257))


@pytest.mark.parametrize('source', [
    'x\n$$\n\n# Smuggled heading\n\n$$\ny',
    r'x\] prose \[ y', '$x$', r'\[x\]', r'\(x\)',
])
def test_equation_source_cannot_escape_its_renderer_owned_delimiters(source):
    with pytest.raises(DocumentError):
        decode(wire([block('equation', source)]))


@pytest.mark.parametrize('text', ['\\', '"', '\t', '\n', '\r\n', '\\"', 'é🧪', 'a/b'])
def test_every_escape_split_preserves_literal_code_exactly(text):
    source = json.dumps({'blocks': [block('code', 'start' + text + 'end')]}, ensure_ascii=True)
    expected = '```\nstart' + text + 'end\n```'
    for split in range(len(source) + 1):
        decoder = DocumentDecoder()
        streamed = decoder.feed(source[:split]) + decoder.feed(source[split:])
        assert decoder.finish() == (expected, '')
        assert streamed == expected


def test_document_limit_counts_unicode_bytes_and_speech_before_blocks():
    decoder = DocumentDecoder(speech=True)
    decoder.feed('{"speech":"')
    with pytest.raises(DocumentError, match='[Dd]ocument.*limit'):
        decoder.feed('🧪' * (1024 * 1024))


def test_block_limit_counts_wire_bytes_even_with_only_unicode_or_whitespace():
    decoder = DocumentDecoder()
    decoder.feed('{"blocks":[{"text":"')
    with pytest.raises(DocumentError, match='[Bb]lock.*limit'):
        decoder.feed('🧪' * (64 * 1024))


def test_full_block_count_is_allowed_and_streamed_storage_is_bounded():
    blocks = [block('bullet', str(i)) for i in range(256)]
    decoder, shown, _ = decode(wire(blocks))
    assert len(decoder.document['blocks']) == 256
    assert shown.count('\n\n') == 255


def test_document_access_before_finish_and_after_failed_finish_is_rejected():
    decoder = DocumentDecoder()
    decoder.feed(wire([block('paragraph', 'Hello')]))
    with pytest.raises(DocumentError):
        _ = decoder.document
    with pytest.raises(DocumentError):
        _ = decoder.wire
    decoder.finish()
    changed = decoder.document
    changed['blocks'][0]['text'] = 'mutated'
    assert decoder.document['blocks'][0]['text'] == 'Hello'


def test_instructions_demonstrate_double_escaped_json_mathematics():
    assert r'"text":"\\frac{1}{2}"' in document_instructions()


@pytest.mark.parametrize('kind,text,want', [
    ('equation', '\frac{1}{2} + \text{ kg}', r'\frac{1}{2} + \text{ kg}'),
    ('paragraph', 'Use $\frac{1}{2}$ and $\text{kg}$.', r'Use $\frac{1}{2}$ and $\text{kg}$.'),
])
def test_known_tex_json_controls_are_repaired_only_in_math_before_validation(kind, text, want):
    # Python and JSON decode the same FF/TAB escapes seen in actual local-model responses.
    assert '\x0c' in text
    decoder, shown, _ = decode(wire([block(kind, text)]))
    assert '\x0c' not in shown
    assert decoder.document['blocks'][0]['text'] == want
    assert want in shown


@pytest.mark.parametrize('kind,text', [
    ('code', '\frac{1}{2}'), ('paragraph', '\frac{1}{2}'),
    ('equation', '\funknown{x}'), ('paragraph', '$\funknown{x}$'),
    ('equation', '\x00x'), ('equation', '\x1bx'),
])
def test_math_repair_never_rewrites_literal_code_prose_or_unknown_controls(kind, text):
    with pytest.raises(DocumentError):
        decode(wire([block(kind, text)]))


@pytest.mark.parametrize('quote', ['“•”', '‘•’', '"•"', "'•'"])
def test_an_unambiguous_quoted_bullet_symbol_is_not_a_list(quote):
    text = 'The glyph ' + quote + ' denotes a bullet.'
    _, shown, _ = decode(wire([block('paragraph', text)]))
    assert shown == text


def test_equation_preserves_escaped_currency_and_tex_row_spacing():
    text = r'\begin{aligned}x&=1\\[2pt]y&=\$5\end{aligned}'
    _, shown, _ = decode(wire([block('equation', text)]))
    assert text in shown


@pytest.mark.parametrize('source', [
    r'\frac{a}{b}', r'\sqrt{x^2+1}', r'\frac{dy}{dx}=2x',
    r'\int_0^1 x^2\,dx=\frac{1}{3}', r'\sum_{i=1}^{n}i=\frac{n(n+1)}{2}',
    r'\lim_{x\to0}\frac{\sin x}{x}=1', r'F=3\,\mathrm{kg}\times 2\,\mathrm{m\,s^{-2}}',
    r'\ce{SO4^{2-}}', r'\ce{CuSO4.5H2O}', r'95\%', r'\unknown{x}',
])
def test_semantic_equations_keep_canonical_source_for_existing_math_converter(source):
    _, shown, _ = decode(wire([block('equation', source)]))
    assert shown == '$$\n' + source + '\n$$'


def test_actual_single_escaped_local_wire_repairs_with_text_before_kind_at_every_split():
    source = r'{"blocks":[{"text":"Use $\frac{1}{2}$ and $\text{kg}$.","kind":"paragraph"}]}'
    for split in range(len(source) + 1):
        decoder = DocumentDecoder()
        streamed = decoder.feed(source[:split]) + decoder.feed(source[split:])
        assert decoder.finish() == (r'Use $\frac{1}{2}$ and $\text{kg}$.', '')
        assert streamed == decoder.finish()[0]


@pytest.mark.parametrize('source', ['```', '<h1>Heading</h1>', '    indented code'])
def test_single_line_markdown_literal_blocks_cannot_bypass_prose_validation(source):
    with pytest.raises(DocumentError):
        decode(wire([block('paragraph', source)]))


@pytest.mark.parametrize('text', [
    'Intro ` • First • Second • Third',
    'Intro `` • First • Second • Third `',
    'Intro &bull; First &bull; Second &bull; Third',
    'Intro &#8226; First &#x2022; Second &bullet; Third',
])
def test_visible_bullet_walls_cannot_hide_behind_unmatched_code_or_html_entities(text):
    with pytest.raises(DocumentError):
        decode(wire([block('paragraph', text)]))


@pytest.mark.parametrize('text', [
    'Use `• First • Second • Third` literally.',
    'Use ``• First ` • Second • Third`` literally.',
    'Use `&bull; First &bull; Second` literally.',
    'The glyph “&bull;” denotes a bullet.',
    'Use $a • b$ for a product.',
])
def test_bullet_validation_preserves_matched_code_quoted_symbols_and_math(text):
    _, shown, _ = decode(wire([block('paragraph', text)]))
    assert shown == text


@pytest.mark.parametrize('text,visible_fragment', [
    ('[• First • Second • Third](https://example.com)', '• First • Second • Third'),
    ('[&bull; First &bull; Second](https://example.com)', '• First • Second'),
    ('&#x202e;abc', '\u202eabc'),
    ('[&#x202e;abc](https://example.com)', '\u202eabc'),
])
def test_rendered_link_labels_and_entity_controls_are_validated(text, visible_fragment):
    from io import StringIO
    from rich.console import Console
    from rich.markdown import Markdown

    console = Console(file=StringIO(), force_terminal=False, record=True)
    console.print(Markdown(text))
    assert visible_fragment in console.export_text()
    with pytest.raises(DocumentError):
        decode(wire([block('paragraph', text)]))


@pytest.mark.parametrize('text', [
    '[source](https://example.com/?q=&bull;&bidi=&#x202e;)',
    '[Use `• First • Second` literally](https://example.com)',
    '[Use $a • b$](https://example.com)',
    '[The glyph “&bull;”](https://example.com)',
    'Use `&#x202e;abc` literally.',
    r'Use $\text{&#x202e;abc}$ as source.',
])
def test_link_destinations_and_protected_inline_literals_are_unchanged(text):
    _, shown, _ = decode(wire([block('paragraph', text)]))
    assert shown == text


def test_actual_native_numbered_heading_preserves_meaning_inside_owned_bold_wrapper():
    text = '1. Differentiate y = x e^(−x)'
    _, shown, _ = decode(wire([block('heading', text)]))
    canonical = '1. Differentiate y = x $e^{−x}$'
    assert shown == '**' + canonical + '**'
    from markdown_it import MarkdownIt
    tokens = MarkdownIt('commonmark').parse(shown)
    assert [token.type for token in tokens] == ['paragraph_open', 'inline', 'paragraph_close']
    assert ''.join(child.content for child in tokens[1].children if child.type == 'text') == canonical


@pytest.mark.parametrize('kind', ['paragraph', 'bullet'])
def test_numeric_heading_exception_does_not_relax_other_prose_layout(kind):
    with pytest.raises(DocumentError):
        decode(wire([block(kind, '1. Differentiate y = x e^(−x)')]))


def test_numeric_heading_exception_does_not_accept_multiple_numbered_lines():
    with pytest.raises(DocumentError):
        decode(wire([block('heading', '1. First\n2. Second')]))


def test_instructions_request_descriptive_headings_and_delimited_inline_latex():
    instructions = document_instructions()
    assert 'short descriptive labels without mathematics' in instructions
    assert 'inline mathematics as $...$' in instructions
    assert '$x e^{-x}$' in instructions


@pytest.mark.parametrize('text,content', [
    ('1. The bond is electrostatic in nature, meaning strong forces of attraction exist '
     'between oppositely charged ions.',
     'The bond is electrostatic in nature, meaning strong forces of attraction exist '
     'between oppositely charged ions.'),
    ('1. Alkanes (Saturated):', 'Alkanes (Saturated):'),
    ('Step 1: Substitute the values.', 'Substitute the values.'),
    ('Step1: Substitute the values.', 'Substitute the values.'),
    ('2) The result is $-2$.', 'The result is $-2$.'),
])
def test_redundant_step_wrapper_is_canonical_in_stream_document_and_history(text, content):
    # The first two blocks are the exact failures in candidate-local-matrix-1.json.
    source = wire([block('step', text), block('equation', 'x=1'), block('step', text)])
    expected = '1. ' + content + '\n\n$$\nx=1\n$$\n\n2. ' + content
    for split in range(len(source) + 1):
        decoder = DocumentDecoder()
        streamed = decoder.feed(source[:split]) + decoder.feed(source[split:])
        assert decoder.finish() == (expected, '')
        assert streamed == expected
        assert decoder.document['blocks'] == [block('step', content),
                                               block('equation', 'x=1'), block('step', content)]
        assert json.loads(decoder.wire) == decoder.document
        assert decode(decoder.wire)[1] == expected


@pytest.mark.parametrize('text', [
    '1. First\n2. Second', 'Step 1: First\n\nSecond', '1. # Heading',
    '1. - First\n- Second', 'Step 1: • First • Second', '1. ```\nsource\n```',
    '1. [• First • Second](https://example.com)', '1. &#x202e;abc',
])
def test_step_wrapper_recovery_does_not_relax_nested_structure_or_control_guards(text):
    with pytest.raises(DocumentError):
        decode(wire([block('step', text)]))


@pytest.mark.parametrize('text', [
    '-2 is negative.', '$-2$ is negative.', r'$- x + y$',
    '1.5 is the value.', 'Step 1 is explained in the question.',
    '`1. literal`', '[source](https://example.com/1.thing?q=$5)',
])
def test_step_recovery_preserves_numbers_signs_math_literals_and_urls(text):
    decoder, shown, _ = decode(wire([block('step', text)]))
    assert decoder.document['blocks'][0]['text'] == text
    assert shown == '1. ' + text


def test_recovered_step_preserves_math_controls_and_literal_code_bytes():
    literal = 'Step 1: 1. -2\nrecord = {"reply": "x_1^2", "cost": "$5"}\r\n'
    decoder, shown, _ = decode(wire([block('step', '1. Use $\frac{1}{2}$.'),
                                    block('code', literal)]))
    assert decoder.document['blocks'] == [block('step', r'Use $\frac{1}{2}$.'),
                                          block('code', literal)]
    assert shown == '1. Use $\\frac{1}{2}$.\n\n```\n' + literal + '```'


@pytest.mark.parametrize('speech', [False, True])
def test_document_example_obeys_contract_and_demonstrates_owned_step_math_layout(speech):
    instructions = document_instructions(speech=speech)
    example = instructions.split('\nExample document:\n', 1)[1].split('\n', 1)[0]
    decoder, shown, spoken = decode(example, speech=speech)
    literal = 'def square(x):\n    return x * x\nrecord = {"reply": "x_1^2"}'
    assert decoder.document['blocks'][-1] == block('code', literal)
    assert shown == ('1. Substitute the mass and acceleration.\n\n$$\nF=2\\times3=6\\,\\mathrm{N}\n$$'
                     + '\n\n```\n' + literal + '\n```')
    assert bool(spoken) == speech


@pytest.mark.parametrize('literal', [
    'def square(x): # comment record = {&quot;reply&quot;: &quot;x_1^2&quot;} return x * x',
    '1. dy/dx = e^(-x) - xe^(-x',
])
def test_model_authored_bad_literal_source_is_preserved_without_inventing_repairs(literal):
    decoder, shown, _ = decode(wire([block('code', literal)]))
    assert shown == '```\n' + literal + '\n```'
    assert decoder.document['blocks'] == [block('code', literal)]
    assert json.loads(decoder.wire)['blocks'][0]['text'] == literal


@pytest.mark.parametrize('text', [
    'Step 1: Step 2: Substitute.', '1. Step 1: Substitute.',
    pytest.param('Step 1: ' * 1000 + 'Substitute.', id='long-prefix-chain'),
])
def test_chained_step_wrappers_cannot_enter_history_that_changes_on_replay(text):
    # Previously accepted .wire removed another wrapper each time it was replayed.
    decoder = DocumentDecoder()
    with pytest.raises(DocumentError, match='[Ss]tep wrapper'):
        decoder.feed(wire([block('step', text)]))
    with pytest.raises(DocumentError):
        decoder.finish()
    with pytest.raises(DocumentError):
        _ = decoder.wire
