"""Session summary and small modal dialogs, independent of the main screens."""
from __future__ import annotations

import time
from datetime import timedelta

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Markdown, OptionList, Static
from textual.widgets.option_list import Option

from tutorlib import clock, model, policy

from .panels import Composer
from .texmath import to_terminal


class SummaryScreen(ModalScreen):
    BINDINGS = [Binding("enter", "close", "Back to menu"), Binding("escape", "dismiss(None)", "Back")]

    def __init__(self, summary: dict) -> None:
        super().__init__()
        self.summary = summary
        self.opened = time.monotonic()

    def action_close(self) -> None:
        if time.monotonic() - self.opened >= 0.7:  # not the ⏎ still held down from "Next ⏎": read it first
            self.dismiss(None)
        else:  # ignored, but visibly
            self.query_one("#summary-hint", Static).update("Press ⏎ again for the menu · ↑↓ scroll")

    def compose(self) -> ComposeResult:
        s = self.summary
        t = self.app.tutor
        acc = f"{round(100 * s['accuracy'])}%" if s.get("accuracy") is not None else "–"
        learned = "\n".join(f"- ✓ {t.packs.kcs[k]['title']}" for k in s.get("kcs_learned", []) if k in t.packs.kcs)
        due = model.due_kcs(t.state, t.now() + timedelta(days=1))
        term_due = policy.review_terms(t.state, t.packs, t.now() + timedelta(days=1))
        a = self.app.ai
        today = t.study_clock.today(t.now().date().isoformat())
        earned, total = s.get("marks") or (0, 0)
        marks = f"  ·  **Marks:** {earned:g} of {total}" if total else ""  # what an examiner would give (Q-017)
        text = (f"# Session done ✓\n\n**Answered:** {s['answered']}  ·  **Fully right:** {s['correct']} ({acc}){marks}\n\n"
                + (f"**Session time:** {clock.fmt(s['active_seconds'], True)} on the screen  ·  **True time:** "
                   f"{clock.fmt(s['true_seconds'], True)} from start to finish  ·  **Studied today:** {clock.fmt(today)}\n\n"
                   if "active_seconds" in s else "")
                + (f"## Learned today\n{learned}\n\n" if learned else "")
                + f"**Due for review in the next 24 hours:** {len(due)} idea(s), {len(term_due)} term(s)\n\n"
                + f"**AI replies this session:** {a.session.replies}\n\n"
                + (f"**New Anki cards ({(s.get('week') or {})['anki']['cards']}):** double-click "
                   f"`{(s.get('week') or {})['anki']['path']}` in the tutor folder to import them.\n\n"
                   if ((s.get("week") or {}).get("anki") or {}).get("path") else "")
                + "Your notes and the full lesson are in Obsidian (Home → Recent lessons).")
        with VerticalScroll(id="summary"):  # a short window scrolls it; the way out stays in sight
            yield Static("⏎ menu · ↑↓ scroll", id="summary-hint", classes="hint")
            yield Markdown(to_terminal(text))


class ConfirmScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(self, question: str, choices: list[tuple[str, str]]) -> None:
        super().__init__()
        self.question, self.choices = question, choices

    def compose(self) -> ComposeResult:
        with Vertical(id="ask"):
            yield Static(self.question, classes="hint")
            yield OptionList(*[Option(label, id=cid) for cid, label in self.choices], id="confirm")

    def on_mount(self) -> None:
        self.query_one("#confirm", OptionList).focus()

    @on(OptionList.OptionSelected, "#confirm")
    def chose(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option.id)


class AskScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel")]

    def __init__(self, mode: str = "ask", *, notice: str | None = None) -> None:
        super().__init__()
        self.mode = mode
        self.notice = notice

    def compose(self) -> ComposeResult:
        with Vertical(id="ask"):
            yield Static("Ask the tutor anything: it knows what is on screen and the questions just marked. "
                         "⏎ sends, ctrl+j starts a new line, Esc cancels.", classes="hint")
            if self.notice:
                yield Static(self.notice, id="ask-image-notice", classes="hint")
            yield Composer(placeholder="e.g. what would the full answer be here?", id="q")

    def on_mount(self) -> None:
        self.query_one("#q", Composer).focus()
        self.app.prepare_local_ai(self.mode)

    def on_unmount(self) -> None:
        self.app.stop_local_preload(self)

    @on(Composer.Submitted, "#q")
    def sent(self, event: Composer.Submitted) -> None:
        question = event.value.strip()
        if question and getattr(self.app, "_preload_owner", None) is self:
            self.app._preload_owner = self.app.screen_stack[-2]  # the session now owns its requested preparation
        self.dismiss(question or None)
