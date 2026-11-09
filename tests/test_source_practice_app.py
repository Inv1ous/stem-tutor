"""A real Home entry drives isolated attempts without the adaptive Tutor."""
import asyncio
from copy import deepcopy
import sys
from pathlib import Path

import pytest
from textual.widgets import Button, Input, Select, Static, TextArea

sys.path.insert(0, str(Path(__file__).parent / 'app'))
from test_tui import app_for
from test_source_practice import install, NATIVE, PMT, module


def staged_practice_app(tmp_path, monkeypatch):
    app, root = app_for(tmp_path, monkeypatch)
    # The ordinary tiny app fixture references unavailable dummy exam papers.
    (root / ".tutor/packs/v1/papers.json").write_text('{"papers": []}')
    # Import sources into the app's disposable Library using the shared real assets.
    staging, native = install(tmp_path, NATIVE / '9701_s19_11')
    _, written = install(tmp_path, PMT)
    import json
    from tutorlib.asset_library import AssetLibrary, write_asset
    library = AssetLibrary(staging)
    for key, record in library.records().items():
        write_asset(root, record['path'], library.read('asset:' + key), metadata={k:v for k,v in record.items() if k not in {'path','sha256','aliases'}})
    catalog = root / 'Library/catalog.json'; data = json.loads(catalog.read_bytes())
    for key, record in library.records().items():
        found = next(k for k,v in data['assets'].items() if v['path'] == record['path'])
        data['assets'][key] = data['assets'].pop(found)
    catalog.write_text(json.dumps(data))
    module().publish(root, [native, written], expected_current=None)
    return app, root


def test_home_practice_written_flow_preserves_mastery_and_work_on_ai_failure(tmp_path, monkeypatch):
    from tutor_app.source_practice_screen import SourcePracticeScreen
    app, root = staged_practice_app(tmp_path, monkeypatch)
    called = []
    async def failed(*args, **kwargs):
        called.append((args, kwargs)); raise RuntimeError('provider unavailable')

    async def go():
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause()
            monkeypatch.setattr(app.ai, 'one_shot', failed)
            # Source practice is the merged Practice entry now; the old id stays a working alias (see home_menu).
            from tutor_app import home_menu
            assert home_menu.ALIASES['source-practice'] == 'practice'
            assert any(key == 'practice' for key, _ in app.screen._menu_items)
            before = deepcopy(app.tutor.state), list(app.tutor.vault.events())
            app.screen._start('source-practice'); await pilot.pause()
            screen = app.screen; assert isinstance(screen, SourcePracticeScreen)
            assert not called
            screen.query_one('#practice-course', Select).value = 'D1'; await pilot.pause()
            assert screen.current['kind'] == 'structured'
            answer = screen.query_one('#practice-answer', TextArea); answer.text = 'My original working'
            screen.query_one('#practice-submit', Button).press(); await pilot.pause()
            assert screen.attempt_id and screen.feedback['scheme_media']
            assert screen.query('#practice-scheme Static')
            screen.query_one('#practice-explain', Button).press(); await pilot.pause()
            assert called and answer.text == 'My original working'
            assert 'self-mark' in str(screen.query_one('#practice-status', Static).content).lower()
            screen.query_one('#practice-award', Input).value = '4'
            screen.query_one('#practice-save-mark', Button).press(); await pilot.pause()
            assert screen.collection.feedback(screen.attempt_id)['awarded'] == 4
            assert (app.tutor.state, list(app.tutor.vault.events())) == before
            screen.query_one('#practice-course', Select).value = '9701'; await pilot.pause()
            screen.query_one('#practice-answer', TextArea).text = 'B'
            screen.query_one('#practice-submit', Button).press(); await pilot.pause()
            assert screen.collection.feedback(screen.attempt_id)['awarded'] == 1
            assert (app.tutor.state, list(app.tutor.vault.events())) == before
            assert app.tutor.session is None
            await app.ai.close()
    asyncio.run(go())


def test_pending_ai_on_prior_question_does_not_block_new_submission(tmp_path):
    from textual.app import App
    from tutor_app.source_practice_screen import SourcePracticeScreen
    from types import SimpleNamespace

    class FakeCollection:
        def __init__(self): self.saved = []
        def question(self, qid):
            return {'id': qid, 'title': 'Source', 'label': qid, 'kind': 'structured', 'marks': 2,
                    'question_text': 'Original question', 'question_media': []}
        def submit(self, qid, answer):
            self.saved.append((qid, answer)); return {'attempt_id': qid + '-attempt'}
        def feedback(self, attempt_id):
            return {'marks': 2, 'scheme_text': 'Original scheme', 'scheme_media': []}
        def _attempt(self, attempt_id): return {'answer': 'Q1 original work'}

    class TestScreen(SourcePracticeScreen):
        def on_mount(self, event):
            event.prevent_default()
            self.collection = FakeCollection(); self.current = self.collection.question('q1')
            self.attempt_id = 'q1-attempt'; self.feedback = None; self.drafts = {}; self.busy = False

    async def go():
        app = App(); started = asyncio.Event(); release = asyncio.Event()
        async def pending(*args, **kwargs):
            started.set(); await release.wait()
            return {'text': 'stale Q1 response'}, SimpleNamespace(ok=True)
        app.ai = SimpleNamespace(one_shot=pending)
        app.settings = SimpleNamespace(ai_mark_model='', ai_explain_model='', model='test')
        app.vault = tmp_path
        async with app.run_test(size=(100, 36)) as pilot:
            screen = TestScreen(); await app.push_screen(screen); await pilot.pause()
            screen.ai_help(); await asyncio.wait_for(started.wait(), timeout=3)
            select = screen.query_one('#practice-question', Select)
            select.set_options([('Question 2', 'q2')]); select.value = 'q2'; await pilot.pause()
            screen.query_one('#practice-answer', TextArea).text = 'Q2 independent work'
            await screen.submit()
            release.set(); await pilot.pause()
            assert screen.collection.saved == [('q2', 'Q2 independent work')]
            assert screen.attempt_id == 'q2-attempt'
            release.set(); await pilot.pause()
            assert 'stale Q1 response' not in str(screen.query_one('#practice-ai-result', Static).content)
    asyncio.run(go())


def test_full_size_scheme_is_attempt_owned_complete_and_resets_on_navigation(tmp_path, monkeypatch):
    from tutor_app import mac
    app, root = staged_practice_app(tmp_path, monkeypatch)
    opened = []
    def open_ok(vault, note, background=True):
        opened.append((vault, note, background)); return True
    monkeypatch.setattr(mac, 'open_in_obsidian', open_ok)

    async def go():
        async with app.run_test(size=(100, 36)) as pilot:
            await pilot.pause(); app.screen._start('source-practice'); await pilot.pause()
            screen = app.screen
            screen.query_one('#practice-course', Select).value = 'D1'; await pilot.pause()
            scheme_button = screen.query_one('#practice-open-scheme', Button)
            assert scheme_button.disabled
            screen.open_scheme(); assert not opened
            await pilot.press('ctrl+o'); await pilot.pause()
            assert opened and all(note in screen.current.get('context_media', []) + screen.current['question_media'] for _, note, _ in opened), (str(screen.query_one('#practice-status', Static).content), screen._bindings.key_to_bindings.get('ctrl+o'))
            opened.clear()
            questions = screen.collection.questions('D1')
            q2 = next(q for q in questions if q['label'] == '2')
            screen.query_one('#practice-question', Select).value = q2['id']; await pilot.pause()
            assert scheme_button.disabled
            screen.query_one('#practice-answer', TextArea).text = 'My Q2 working'
            await screen.submit()
            expected = screen.collection.feedback(screen.attempt_id)['scheme_media']
            assert len(expected) == 2 and not scheme_button.disabled
            checked = []
            original_path = screen.collection.media_path
            def owned(qid, reference, **kwargs):
                checked.append((qid, reference, kwargs.get('attempt_id')))
                return original_path(qid, reference, **kwargs)
            monkeypatch.setattr(screen.collection, 'media_path', owned)
            await pilot.press('ctrl+o'); await pilot.pause()
            assert [ref for _, ref, _ in opened] == expected
            assert checked == [(q2['id'], ref, screen.attempt_id) for ref in expected]
            assert all(background is False for _, _, background in opened)
            opened.clear()
            q6 = next(q for q in questions if q['label'] == '6')
            screen.query_one('#practice-question', Select).value = q6['id']; await pilot.pause()
            assert scheme_button.disabled
            screen.open_scheme(); assert not opened
            screen.query_one('#practice-answer', TextArea).text = 'My Q6 sorting passes'
            await screen.submit()
            refs = screen.collection.feedback(screen.attempt_id)['scheme_media']
            screen.open_scheme()
            assert [ref for _, ref, _ in opened] == refs
            # Retain the exact full-size accessible real Q6 source scheme for visual QA.
            import os
            if destination := os.environ.get('SOURCE_PRACTICE_SCHEME_QA'):
                Path(destination).write_bytes(original_path(q6['id'], refs[0], attempt_id=screen.attempt_id).read_bytes())
            monkeypatch.setattr(mac, 'open_in_obsidian', lambda *a, **kw: False)
            screen.open_scheme()
            assert 'could not open' in str(screen.query_one('#practice-status', Static).content).lower()
            def opening_error(*args, **kwargs): raise OSError('Launch Services refused')
            monkeypatch.setattr(mac, 'open_in_obsidian', opening_error)
            screen.open_scheme()
            assert 'could not open' in str(screen.query_one('#practice-status', Static).content).lower()
            # A forged feedback list cannot open another question's scheme.
            opened.clear(); monkeypatch.setattr(mac, 'open_in_obsidian', open_ok)
            original_feedback = screen.collection.feedback
            monkeypatch.setattr(screen.collection, 'feedback', lambda attempt: {**original_feedback(attempt), 'scheme_media': [expected[0]]})
            screen.open_scheme()
            assert not opened
            assert 'could not open' in str(screen.query_one('#practice-status', Static).content).lower()
            await app.ai.close()
    asyncio.run(go())


@pytest.mark.parametrize('registered', [None, 'exact'])
@pytest.mark.parametrize('filename,target', [('scheme.png','scheme.png'), ('scheme.pdf','scheme.pdf'), ('lesson.md','lesson.md'), ('lesson','lesson.md'), ('9701-1.1','9701-1.1.md')])
def test_mac_open_preserves_existing_image_suffix_for_unregistered_vault(tmp_path, monkeypatch, registered, filename, target):
    from tutor_app import mac
    from types import SimpleNamespace
    from urllib.parse import unquote
    image = tmp_path / 'Library' / filename; image.parent.mkdir(); image.write_bytes(b'disposable input')
    opened = []
    monkeypatch.setattr(mac.sys, 'platform', 'darwin')
    monkeypatch.setattr(mac.shutil, 'which', lambda name: '/usr/bin/open')
    monkeypatch.setattr(mac, 'obsidian_vault_registered', lambda vault: registered)
    monkeypatch.setattr(mac.subprocess, 'run', lambda args, **kw: (opened.append(args) or SimpleNamespace(returncode=0)))
    assert mac.open_in_obsidian(tmp_path, 'Library/' + filename, background=False)
    expected = ('obsidian://open?vault=' + tmp_path.name + '&file=Library/' + filename if registered == 'exact'
                else 'obsidian://open?path=' + str(image.parent / target))
    assert unquote(opened[0][-1]) == expected


@pytest.mark.parametrize('correct', [True, False])
def test_explicit_ai_explanation_distinguishes_correct_confirmation_and_focused_repair(tmp_path, correct):
    from textual.app import App
    from tutor_app.source_practice_screen import SourcePracticeScreen
    from types import SimpleNamespace

    calls = []
    class Practice:
        def _attempt(self, attempt_id): return {'answer': 'B' if correct else 'A'}
        def feedback(self, attempt_id):
            return {'answer': 'B', 'marks': 1, 'awarded': int(correct)}
        def media_path(self, qid, ref, **kwargs): return tmp_path / ref

    class TestScreen(SourcePracticeScreen):
        def on_mount(self, event):
            event.prevent_default()
            self.collection = Practice()
            self.current = {'id': 'q2', 'kind': 'mcq', 'marks': 1,
                            'question_text': 'Original source', 'question_media': ['question.png']}
            self.attempt_id = 'saved-attempt'; self.busy = False

    async def go():
        app = App(); app.vault = tmp_path
        async def provider(prompt, **kwargs):
            calls.append((prompt, kwargs))
            return {'text': 'Brief source-grounded feedback', 'suggested_award': 0}, SimpleNamespace(ok=True)
        app.ai = SimpleNamespace(one_shot=provider)
        app.settings = SimpleNamespace(ai_mark_model='', ai_explain_model='', model='test')
        async with app.run_test(size=(100, 36)) as pilot:
            screen = TestScreen(); await app.push_screen(screen); await pilot.pause()
            assert calls == []
            screen.ai_help(); await pilot.pause()
            assert len(calls) == 1
            prompt, options = calls[0]
            assert 'correct' in prompt.lower() and 'concise' in prompt.lower()
            assert 'focused correction' in prompt.lower()
            assert ('Result: correct' if correct else 'Result: incorrect') in prompt
            assert 'full detail only when requested' in prompt.lower()
            assert options['images'] == [tmp_path / 'question.png']
            assert screen.query_one('#practice-award', Input).value == ''
            assert screen.collection.feedback(screen.attempt_id)['awarded'] == int(correct)
    asyncio.run(go())


@pytest.mark.parametrize('award,label', [(3, 'full marks (self-marked)'),
                                        (1, 'partial marks (self-marked)'),
                                        (None, 'unmarked')])
def test_written_ai_explanation_uses_saved_award_without_changing_it(tmp_path, award, label):
    from textual.app import App
    from tutor_app.source_practice_screen import SourcePracticeScreen
    from types import SimpleNamespace
    calls = []
    class Practice:
        def _attempt(self, attempt_id): return {'answer': 'Saved written work'}
        def feedback(self, attempt_id):
            result = {'marks': 3, 'scheme_text': 'Original scheme', 'scheme_media': []}
            if award is not None: result['awarded'] = award
            return result
        def media_path(self, qid, ref, **kwargs): return tmp_path / ref
    class TestScreen(SourcePracticeScreen):
        def on_mount(self, event):
            event.prevent_default(); self.collection = Practice()
            self.current = {'id': 'q2', 'kind': 'structured', 'marks': 3,
                            'question_text': 'Original source', 'question_media': []}
            self.attempt_id = 'saved'; self.busy = False
    async def go():
        app = App(); app.vault = tmp_path
        async def provider(prompt, **kwargs):
            calls.append(prompt)
            return {'text': 'Feedback', 'suggested_award': 0}, SimpleNamespace(ok=True)
        app.ai = SimpleNamespace(one_shot=provider)
        app.settings = SimpleNamespace(ai_mark_model='', ai_explain_model='', model='test')
        async with app.run_test(size=(100, 36)) as pilot:
            screen = TestScreen(); await app.push_screen(screen); await pilot.pause()
            assert not calls
            before = screen.collection.feedback('saved')
            screen.ai_help(); await pilot.pause()
            assert f'Result: {label}' in calls[0]
            assert 'full marks' in calls[0].lower() and 'concise' in calls[0].lower()
            assert 'partial marks' in calls[0].lower() and 'focused correction' in calls[0].lower()
            assert screen.collection.feedback('saved') == before
            assert screen.query_one('#practice-award', Input).value == ''
    asyncio.run(go())
