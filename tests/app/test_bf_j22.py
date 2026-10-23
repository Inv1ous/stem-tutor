"""Regression checks for shortcut marking and preserving work."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from textual.widgets import Input

from test_tui import app_for
from test_shortcuts_screen import card, events, open_from_menu, publish, run
from tutor_app.shortcuts_screen import numeric_ok
from tutorlib import shortcuts as sc


@pytest.mark.parametrize(('given', 'answer', 'right'), [
    ('1/3', '0.3333333333333333', True), ('-1 / 3', '-0.3333333333333333', True),
    ('1/3', '1', False), ('not 3, but 4', '3', False), ('25 kg', '25', False),
    ('minus 3', '3', False), ('1/0', '1', False), ('1e2', '100', True),
])
def test_numeric_practice_marks_the_whole_answer(given, answer, right):
    """B-040: exact fractions count, but their numerator and stray numbers do not."""
    assert numeric_ok(given, answer) is right


@pytest.mark.parametrize(('given', 'right'), [
    ('25 N', True), ('25 kg', False), ('25', True),
    ('0.025 kN', True), ('25 kN', False), ('25 N or 30 N', False),
])
def test_force_practice_accepts_the_requested_unit_only(tmp_path, monkeypatch, given, right):
    """B-040: the published force question accepts newtons, not kilograms."""
    app, v = app_for(tmp_path, monkeypatch)
    path = Path(__file__).resolve().parents[2] / 'build/out/shortcuts/lessons/M1.json'
    lesson = json.loads(path.read_text())['SEM-M1-resolve-into-components']
    publish(v, lessons={'SEM-9702-a': lesson})

    async def steps(pilot):
        scr = await open_from_menu(pilot, app, 'shortcuts', 'ShortcutsScreen')
        scr.act('start')
        await pilot.pause()
        scr.start_practice()
        await pilot.pause()
        scr.query_one(Input).value = given
        await pilot.press('enter')
        await pilot.pause()
        assert ('Correct.' if right else 'Not quite.') in card(scr)
        assert events(v)[-1]['rating'] == (3 if right else 1)
    run(app, steps)


@pytest.mark.parametrize(('stem', 'given', 'answer', 'right'), [
    ('Find the acceleration in m s$^{-2}$, to 2 significant figures.', '3 m/s^2', '3', True),
    ('Find the acceleration in m s$^{-2}$, to 2 significant figures.', '3 m/s', '3', False),
    ('A block is in equilibrium. Find the tension in N to 2 decimal places.', '25 N', '25', True),
    ('Find the displacement in m. Give a bare number.', '1/3 m', '0.3333333333333333', True),
    ('A 25 N force acts on a 25 kg block. Find the coefficient of friction.', '1 N', '1', False),
    ('A particle moves in vacuum. Find its speed in m s$^{-1}$.', '3 vacuum', '3', False),
])
def test_practice_units_follow_the_requested_quantity(stem, given, answer, right):
    """B-040: validate compound units without treating data units or prose as the answer unit."""
    assert numeric_ok(given, answer, stem) is right


@pytest.mark.parametrize('key', ['escape', 'ctrl+b'])
@pytest.mark.parametrize('kind', ['numeric', 'short'])
def test_leaving_practice_asks_before_losing_an_answer(tmp_path, monkeypatch, key, kind):
    """B-087: both Back keys ask, and Keep writing preserves the draft."""
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)

    async def steps(pilot):
        scr = await open_from_menu(pilot, app, 'shortcuts', 'ShortcutsScreen')
        scr.act('start')
        await pilot.pause()
        scr.start_practice()
        if kind == 'short':
            scr.pi = 2
            scr.next_practice()
        await pilot.pause()
        scr.query_one(Input).value = 'work in progress'
        await pilot.press(key)
        await pilot.pause()
        assert type(app.screen).__name__ == 'ConfirmScreen'
        await pilot.press('down', 'enter')
        await pilot.pause()
        assert app.screen is scr
        assert scr.query_one(Input).value == 'work in progress'
        await pilot.press(key)
        await pilot.pause()
        await pilot.press('enter')
        await pilot.pause()
        assert type(app.screen).__name__ == 'HomeScreen'
    run(app, steps)


@pytest.mark.parametrize('change', [False, True])
def test_settings_preserves_the_lesson_and_typed_practice(tmp_path, monkeypatch, change):
    """B-119: closing settings keeps the revealed parts and practice draft."""
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)

    async def steps(pilot):
        scr = await open_from_menu(pilot, app, 'shortcuts', 'ShortcutsScreen')
        await pilot.press('enter')
        await pilot.pause()
        await pilot.press('enter')
        await pilot.pause()
        before = card(scr)
        await pilot.press('s')
        await pilot.pause()
        if change:
            app.screen.change(min_score=10)
        await pilot.press('escape')
        await pilot.pause()
        assert scr.phase == 'reveal' and card(scr) == before
        scr.start_practice()
        await pilot.pause()
        scr.query_one(Input).value = '1/3'
        scr.action_settings()
        await pilot.pause()
        await pilot.press('escape')
        await pilot.pause()
        assert scr.phase == 'practice' and scr.query_one(Input).value == '1/3'
    run(app, steps)


@pytest.mark.parametrize('change', [False, True])
def test_settings_preserves_recall_question_and_visit_total(tmp_path, monkeypatch, change):
    """B-119: checking settings does not lose completed recall counts."""
    app, v = app_for(tmp_path, monkeypatch)
    publish(v)
    for ident in ['SEM-9702-a', 'SEM-9702-b']:
        sc.Course(v).record('learn', ident, 3, now=datetime.now(timezone.utc) - timedelta(days=40))

    async def steps(pilot):
        scr = await open_from_menu(pilot, app, 'shortcut_recall', 'ShortcutRecallScreen')
        await pilot.press('enter')
        await pilot.pause()
        await pilot.press('3')
        await pilot.pause()
        before = card(scr)
        await pilot.press('s')
        await pilot.pause()
        if change:
            app.screen.change(min_score=10)
        await pilot.press('escape')
        await pilot.pause()
        assert scr.phase == 'question' and card(scr) == before
        await pilot.press('enter')
        await pilot.pause()
        await pilot.press('3')
        await pilot.pause()
        assert 'You recalled 2 shortcuts' in card(scr)
    run(app, steps)
