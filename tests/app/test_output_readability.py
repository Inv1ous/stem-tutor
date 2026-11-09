"""Readability is enforced by the shared formatter, not a model's preferred prose style."""
import asyncio
from copy import deepcopy
import json
import re

import pytest
from markdown_it import MarkdownIt

from library_assets import read_json
from tutor_app.chat_output import DocumentDecoder
from tutor_app.config import AI_MODELS
from tutor_app.output_format import normalise_visual

PACK = 'Library/Releases/v274/specs/9701/packs/9701-4.2.json'


def bonding_form():
    card = read_json(PACK)['teach']['9701-4.2.3']
    return next(f for f in card['forms'] if f['name'].startswith('Deduce structure and bonding from a pattern'))


def test_registered_bonding_example_keeps_each_labelled_step_in_its_own_paragraph():
    source = bonding_form()['example']
    shown = normalise_visual(source)
    for n in range(1, 5):
        assert f'\n\nStep {n}:' in shown
    assert re.sub(r'\s+', '', shown) == re.sub(r'\s+', '', source)
    assert normalise_visual(shown) == shown


@pytest.mark.parametrize('source', ['First line.\nSecond line.', 'Given:\n$x=3$\n$v=2$',
                                   '**Method:**\nUse the definition.', 'First line.\\\nSecond line.',
                                   'First line.\\\\\nSecond line.'])
def test_explicit_prose_lines_remain_breaks_in_commonmark(source):
    shown = normalise_visual(source)
    assert '<br />' in MarkdownIt('commonmark').render(shown)
    assert normalise_visual(shown) == shown


@pytest.mark.parametrize('source', [
    'Compare Step 1: setup with Step 2: evaluation.',
    'Step 1: compare your answer with Step 2: the worked solution.',
    'The labels “Step 1: setup. Step 2: evaluation.” are quoted.',
    'The labels "Step 1: setup. Step 2: evaluation." are quoted.',
    '`Step 1: setup. Step 2: evaluation.`',
    '```text\nStep 1: literal. Step 2: literal.\nx_1^2\n```',
    '$\\text{Step 1: literal. Step 2: literal.}$',
    '[Step 1: literal. Step 2: literal.](https://example.test/Step-1)',
    '> Step 1: a quotation. Step 2: still quoted.',
    '- Step 1: inside one list item. Step 2: still that item.',
])
def test_step_references_and_protected_regions_are_not_reinterpreted(source):
    assert normalise_visual(source) == source


def test_semantic_document_spacing_is_independent_of_chunk_boundaries_and_keeps_code_exact():
    doc = {'blocks': [{'kind': 'paragraph', 'text': 'First line.\nSecond line.'},
                      {'kind': 'paragraph', 'text': 'Step 1: use the definition. Step 2: check the conditions.'},
                      {'kind': 'code', 'text': 'Step 1: literal. Step 2: literal.\nx_1^2'}],
           'speech': 'Speak Step 1: and Step 2: exactly.'}
    source = json.dumps(doc)
    for split in range(len(source) + 1):
        decoder = DocumentDecoder(speech=True)
        streamed = decoder.feed(source[:split]) + decoder.feed(source[split:])
        markdown, spoken = decoder.finish()
        assert streamed == markdown
        assert '<br />' in MarkdownIt('commonmark').render(markdown)
        assert 'Step 1: use the definition.\n\nStep 2:' in markdown
        assert '```\nStep 1: literal. Step 2: literal.\nx_1^2\n```' in markdown
        assert decoder.document == doc and spoken == doc['speech']


def test_form_wordings_are_distinct_bullets_before_the_worked_example():
    from test_guided_lesson import StubLesson
    tutor = StubLesson()
    form = {'name': 'Synthetic form', 'wordings': ['Explain the first claim.', 'Explain the second claim.'],
            'example': 'Step 1: inspect. Step 2: conclude.'}
    block = {'kc': 'P2-1.1', 'card': {'source': 'pack', 'forms': [form]},
             'i': 0, 'phases': ['form_example:0']}
    activity = tutor._step_node(block, 0)
    assert '\n\n- Explain the first claim.\n\n- Explain the second claim.\n\n' in activity['text']
    assert '**Worked example:**\n\n' in activity['text']
    assert form['example'] in activity['text']


@pytest.mark.parametrize('model', AI_MODELS)
def test_every_selectable_model_formats_only_visual_feedback(tmp_path, monkeypatch, model):
    from tutor_app import ai, local_models, prompts, tutor_ai
    monkeypatch.setattr(local_models, 'available_models', lambda: tuple(local_models.LOCAL_MODELS))
    raw = 'First idea.\nSecond idea. Step 1: inspect the condition. Step 2: state the result.'
    source = {'feedback': raw, 'points': [{'point': raw, 'met': True, 'why': raw}], 'speech': raw}
    before = deepcopy(source)
    result = ai.Result(text='Transport metadata', speech=raw, usage={'output_tokens': 7})
    think = local_models.supports_thinking(model) if local_models.is_local(model) else True

    async def go():
        client = tutor_ai.TutorAI(tmp_path, binary='/missing/claude', speech=True)
        seen = []
        async def answer(prompt, **kwargs):
            seen.append(kwargs)
            return source, result
        if model in ('haiku', 'sonnet', 'opus'):
            async def claude_answer(self, prompt, **kwargs):
                return await answer(prompt, **kwargs)
            monkeypatch.setattr(ai.Claude, 'one_shot', claude_answer)
        elif model.startswith('codex:'):
            monkeypatch.setattr(client.codex, 'one_shot', answer)
        elif model.startswith('abacus:'):
            monkeypatch.setattr(client.abacus, 'one_shot', answer)
        else:
            monkeypatch.setattr(client.local, 'one_shot', answer)
        data, returned = await client.one_shot('Check wording', schema=prompts.JUDGE, model=model,
                                               speech=True, think=think)
        assert '<br />' in MarkdownIt('commonmark').render(data['feedback'])
        assert '\n\nStep 1:' in data['feedback'] and '\n\nStep 2:' in data['feedback']
        assert data['points'][0]['point'] == raw and data['points'][0]['met'] is True
        assert data['speech'] == raw and source == before
        assert returned is result and returned.speech == raw and returned.usage == {'output_tokens': 7}
        assert seen[0]['model'] == model and seen[0]['think'] is think
        await client.close()
    asyncio.run(go())
