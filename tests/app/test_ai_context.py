"""The AI is told the whole question in front of the learner, with its diagram, and each kind of help uses the model and
thinking chosen in Settings. Asked by the learner: diagram past-paper questions had to be copied out by hand to get a
reasonable answer; and to choose the model and thinking for marking, explaining and asking, keeping usage low."""
import asyncio
import io
import json

from test_tui import app_for
from tutor_app import config, prompts
from tutor_app.screens import SessionScreen
from tutorlib.asset_library import write_asset

LONG = ("The diagram shows the shape at one instant in time of part of a stretched string as a wave travels along it "
        "from left to right. " * 6)
QUESTION_IMAGE = 'Library/Courses/9702/Questions/Media/q28.png'


def _install_image(vault, relative, colour='blue'):
    """Valid synthetic media and fixture paper paths in this test's Library."""
    from PIL import Image
    image = io.BytesIO()
    Image.new('RGB', (3, 2), colour).save(image, format='PNG')
    write_asset(vault, relative, image.getvalue())
    for kind in ('qp', 'ms'):
        filename = f'9702_s23_{kind}_22.pdf'
        write_asset(vault, f'Library/Courses/9702/Sources/Papers/{filename}', b'%PDF-1.4 synthetic fixture',
                    aliases=[f'Papers/9702/{filename}'])


def _open_with_diagram(app, v):
    s = app.tutor.session
    n, p = max(s["presented"].items(), key=lambda x: int(x[0]))
    _install_image(v, QUESTION_IMAGE)
    p["unassisted"] = False  # an ordinary question: help is allowed
    p["inst"].update(stem=LONG, image=QUESTION_IMAGE, source={"type": "past", "ref": "CAIE 9702 · Jun 2024 · P11 · Q28"})
    return int(n)


def run(app, steps, size=(120, 40)):
    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await steps(pilot)
            await app.ai.close()
    asyncio.run(go())


def test_the_whole_question_its_source_and_its_diagram_go_to_the_ai(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.push_screen(SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]}))
        await pilot.pause()
        n = _open_with_diagram(app, v)
        told = prompts.context(app.tutor)
        assert LONG.strip()[:1000] in told  # all of it, not the first 400 characters
        assert "past paper: CAIE 9702 · Jun 2024 · P11 · Q28" in told and "has a diagram" in told
        assert f"OPEN question {n}, on screen now" in told
        assert prompts.focus_image(app.tutor) == v / QUESTION_IMAGE
    run(app, steps)


def test_asking_sends_the_diagram_with_the_chosen_model_and_thinking(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    calls = []

    async def fake_stream(prompt, **kw):
        calls.append(kw)
        yield "A nudge."

    async def steps(pilot):
        app.settings.ai_ask_model, app.settings.ai_ask_think = "sonnet", True
        app.settings.ai_explain_model, app.settings.ai_explain_think = "opus", False
        monkeypatch.setattr(app.ai, "stream", fake_stream)
        scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()
        _open_with_diagram(app, v)
        scr.stream("why?", mode="ask")
        await pilot.pause(0.3)
        scr.stream("again, differently", mode="explain")
        await pilot.pause(0.3)
        assert calls[0] == {"image": v / QUESTION_IMAGE, "model": "sonnet", "think": True}
        assert calls[1]["model"] == "opus" and calls[1]["think"] is False
    run(app, steps)


def test_marking_uses_the_marking_choice(tmp_path, monkeypatch):
    app, v = app_for(tmp_path, monkeypatch)
    seen = []

    async def fake_one_shot(prompt, schema=None, model=None, think=False, **kw):
        seen.append((model, think))
        return {"points": [{"point": "[1] has direction", "met": True, "why": "ok"}], "feedback": "Good."}, None

    async def steps(pilot):
        app.settings.ai_mark_model, app.settings.ai_mark_think = "sonnet", True
        monkeypatch.setattr(app.ai, "one_shot", fake_one_shot)
        scr = SessionScreen({"mode": "test", "minutes": 40, "focus": ["9702-2.1"]})
        app.push_screen(scr)
        await pilot.pause()
        scr.view = {"n": 1, "stem": "Explain why velocity is a vector."}
        scr.scheme, scr.long_text = [{"i": 1, "mark": "[1]", "point": "has direction"}], "it has a direction"
        scr.ai_check_long({"ticked": []})
        await pilot.pause(0.3)
        assert seen and seen[0] == ("sonnet", True)
    run(app, steps)


def test_settings_have_a_model_and_thinking_for_each_kind_of_help_and_save_them(tmp_path, monkeypatch):
    from textual.widgets import Select, Switch
    app, v = app_for(tmp_path, monkeypatch)

    async def steps(pilot):
        app.action_settings()
        await pilot.pause()
        scr = app.screen
        for mode in config.AI_MODES:
            assert scr.query_one(f"#ai_{mode}_model", Select).value == "haiku"  # everything starts cheapest
            assert scr.query_one(f"#ai_{mode}_think", Switch).value is False
        scr.query_one("#ai_explain_model", Select).value = "sonnet"
        scr.query_one("#ai_ask_think", Switch).value = True
        scr.query_one("#save").press()
        await pilot.pause()
        saved = config.Settings.load(v)
        assert saved.ai_for("explain") == ("sonnet", False) and saved.ai_for("ask") == ("haiku", True)
        assert saved.ai_for("mark") == ("haiku", False)
        assert (app.ai.model, app.ai.think) == ("haiku", True)  # the conversation started ahead is the asking one
    run(app, steps, size=(100, 40))


def test_a_settings_file_written_by_hand_falls_back_safely(tmp_path):
    (tmp_path / ".tutor").mkdir()
    (tmp_path / ".tutor/app_settings.json").write_text(json.dumps(
        {"model": "sonnet", "ai_mark_model": "gpt", "ai_ask_model": "opus", "ai_ask_think": "yes"}))
    s = config.Settings.load(tmp_path)
    assert s.ai_for("mark") == ("sonnet", False)  # an unknown model: the general one
    assert s.ai_for("ask") == ("opus", False)  # a think flag that is not true/false is ignored
    assert config.Settings().ai_for("explain") == ("haiku", False)


def test_prepared_multi_page_question_uses_snapshots_in_view_now_and_ai(tmp_path):
    from fixtures import make_vault
    from tutorlib import saved_figures, session, store
    root = make_vault(tmp_path)
    paths = ['Library/Courses/9702/Questions/Media/' + name for name in ('first.png', 'second.png')]
    for name, colour in [('first.png', 'red'), ('second.png', 'blue')]:
        _install_image(root, 'Library/Courses/9702/Questions/Media/' + name, colour)
    sources = [(root / path).read_bytes() for path in paths]
    original = {'id': 'prepared-image-question', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                'marks': 1, 'stem': 'Which?', 'options': {'A': 'One', 'B': 'Two'}, 'answer': 'A',
                'images': paths}
    prepared = saved_figures.prepare_question(root, original)
    tutor = session.Tutor(store.Vault(root))
    tutor.start('review')
    activity = tutor._questions({'kind': 'practice', 'kc': '9702-2.1.1'}, 0, [prepared])
    view = activity['items'][0]
    assert view['images'] == prepared['images']
    now = (root / 'Now.md').read_text()
    assert now.index(prepared['images'][0]) < now.index(prepared['images'][1])
    assert prompts.focus_image(tutor) == root / prepared['images'][0]
    (root / paths[0]).write_bytes(b'replaced')
    restored = session.Tutor(store.Vault(root))
    assert saved_figures.verify_question(root, next(iter(restored.session['presented'].values()))['inst']) == sources
    assert prompts.focus_image(restored).read_bytes() == sources[0]


def test_menu_chat_keeps_finished_question_choices_source_explanation_and_verified_image(tmp_path, monkeypatch):
    from tutorlib import session, store
    from tutor_app.screens import ChatScreen
    app, vault = app_for(tmp_path, monkeypatch)
    calls = []

    async def fake_stream(prompt, **kw):
        calls.append((prompt, kw))
        app.ai.last = type('Result', (), {'ok': True, 'text': 'Because the diagram shows direction.',
                                          'speech': '', 'message': ''})()
        yield 'Because the diagram shows direction.'

    async def steps(pilot):
        tutor = app.tutor
        app.settings.ai_ask_model = 'sonnet'
        app.ai.model = 'sonnet'
        tutor.start('test', focus=['9702-2.1'])
        item = {'id': 'finished-image-question', 'kcs': ['9702-2.1.1'], 'kind': 'mcq', 'difficulty': 2,
                'marks': 1, 'stem': 'Which vector?', 'options': {'A': 'Speed', 'B': 'Velocity'},
                'answer': 'B', 'source': {'type': 'past', 'ref': 'CAIE 9702 · Jun 2024 · P11 · Q28'},
                'image': QUESTION_IMAGE, 'explanation': 'The arrow points along displacement.'}
        _install_image(vault, QUESTION_IMAGE)
        view = tutor._present(item, block='practice', phase='practice')
        tutor.session['presented'][str(view['n'])]['unassisted'] = False
        tutor.answer(f"{view['n']}A3")
        event = next(e for e in tutor.vault.events() if e.get('type') == 'answer')
        assert 'key' not in event['question'] and event['question']['options'] == {'A': 'Speed', 'B': 'Velocity'}
        tutor.end()
        monkeypatch.setattr(app, 'ai_available', lambda mode: True)
        monkeypatch.setattr(app.ai, 'stream', fake_stream)
        screen = ChatScreen()
        await app.push_screen(screen)
        await pilot.pause()
        await screen.reply('Why was my choice wrong?').wait()
        prompt, kwargs = calls[0]
        assert 'A) Speed; B) Velocity' in prompt
        assert 'CAIE 9702 · Jun 2024 · P11 · Q28' in prompt
        assert 'The arrow points along displacement.' in prompt
        assert kwargs['image'] == vault / QUESTION_IMAGE
        await app.ai.close()
    run(app, steps)
