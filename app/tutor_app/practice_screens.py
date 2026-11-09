"""Practice: one entry that replaces Test prep, Topical past papers and Source-verified practice.

Step 1 is the picker (PickerScreen in mode "practice"): a whole course, a whole topic, or ticked chapters.
Step 2 is PracticeSetupScreen: question sources, how many, difficulty, whether to include chapters not yet started.
Then SessionScreen starts mode "practice" with the options below.

Session options (the contract with tutorlib.policy / Tutor.start):
    focus             list of subtopic ids that were chosen (after the "not yet started" choice is applied)
    course            the course (spec id, e.g. "9701", "P1") when everything chosen is in one course, else None
    scope             "course" | "module" | "chapters"
    sources           subset of ["topical", "source_verified"]; both by default
    count             number of questions (1 to topical_selection.COUNT_LIMIT)
    difficulty        "mixed" | "easier" | "harder"
    include_unstarted bool
    types             question types (topical_selection.TYPES)
    auto_mark         bool: automatic AI marking of written answers
Source-verified questions count towards mastery like the past-paper bank; the session screen tags each of them.
"""
from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, SelectionList, Static, Switch
from textual.widgets.selection_list import Selection

from tutorlib import topical_selection
from tutorlib.topicals import started_chapters

SOURCES = (("Past-paper bank (reviewed, counts towards mastery)", "topical"),
           ("Source-verified papers (counts towards mastery)", "source_verified"))
DIFFICULTIES = (("Mixed", "mixed"), ("Easier questions first", "easier"), ("Harder questions first", "harder"))


def classify(packs, focus: list[str], selectable: list[str] | None = None) -> tuple[str, str | None]:
    """(scope, course) for a chosen set of subtopics.

    "course": every selectable subtopic of one course is chosen; "module": every selectable subtopic of one topic of a
    course; otherwise "chapters". `course` is the one course everything belongs to, else None.
    """
    chosen = set(focus)
    specs = {packs.subtopics[s].get("spec") for s in chosen if s in packs.subtopics}
    course = next(iter(specs)) if len(specs) == 1 else None
    pool = set(selectable) if selectable is not None else set(packs.subtopics)
    if course:
        whole = {s for s in pool if packs.subtopics.get(s, {}).get("spec") == course}
        if whole and whole <= chosen:
            return "course", course
        topics = {packs.subtopics[s].get("topic") for s in chosen if s in packs.subtopics}
        if len(topics) == 1:
            topic = next(iter(topics))
            module = {s for s in pool if packs.subtopics.get(s, {}).get("topic") == topic}
            if module and module <= chosen:
                return "module", course
    return "chapters", course


def start_practice(app) -> None:
    """Menu entry: picker, then setup, then the session. Cancelling at either step comes back to the menu."""
    from .screens import PickerScreen, SessionScreen

    def configured(options):
        if options:
            app.push_screen(SessionScreen({"mode": "practice", "minutes": app.settings.minutes, **options}))

    def chosen(focus):
        if focus:
            picker = picked["picker"]
            scope, course = classify(app.tutor.packs, focus, getattr(picker, "built", None))
            app.push_screen(PracticeSetupScreen(focus, scope, course), configured)

    picked: dict = {}
    picker = PickerScreen("practice")
    picked["picker"] = picker
    app.push_screen(picker, chosen)


class PracticeSetupScreen(ModalScreen):
    """Choose sources, count, difficulty and whether to include chapters not started yet; then start."""
    BINDINGS = [Binding("escape", "dismiss(None)", "Cancel"), Binding("ctrl+s", "start_set", "Start")]
    DEFAULT_CSS = """
    PracticeSetupScreen { align: center middle; }
    #practice-setup { width: 90; max-width: 95%; height: 90%; max-height: 90%;
        border: round $modal-border; background: $modal-background; padding: 1 2; }
    #practice-setup .title { color: $accent; text-style: bold; }
    #practice-fields { height: 1fr; }
    #practice-summary { height: auto; max-height: 3; }
    #practice-change { margin: 0 0 1 0; }
    #practice-setup .row { height: auto; }
    #practice-setup .row > Static { width: 1fr; }
    #practice-count { width: 8; }
    #practice-unstarted { height: 1; border: none; padding: 0; width: auto; }
    #practice-difficulty, #practice-marking { width: 28; }
    #practice-sources { height: 4; max-height: 4; }
    #practice-types { height: 5; max-height: 5; }
    #practice-availability { height: auto; }
    #practice-footer { height: auto; background: $modal-background; }
    #practice-actions { height: auto; }
    #practice-actions Button { margin-right: 2; }
    """

    def __init__(self, focus: list[str], scope: str = "chapters", course: str | None = None) -> None:
        super().__init__()
        self.selected = list(focus)
        self.scope, self.course = scope, course
        self._counts: dict | None = None
        self._generation = 0
        self._remembered = False

    # ---------- layout ----------
    def compose(self) -> ComposeResult:
        with Vertical(id="practice-setup"):
            yield Static("Practice", classes="title")
            with VerticalScroll(id="practice-fields"):
                yield Static("", id="practice-summary")
                yield Button("Change what to practise", id="practice-change", compact=True)
                yield Static("Question sources (Space toggles): at least one.", classes="hint")
                yield SelectionList(*(Selection(label, value, True, id=f"src-{value}") for label, value in SOURCES),
                                    id="practice-sources")
                with Horizontal(classes="row"):
                    yield Static(f"Number of questions (1–{topical_selection.COUNT_LIMIT})")
                    yield Input("10", id="practice-count", type="integer", compact=True, select_on_focus=False)
                with Horizontal(classes="row"):
                    yield Static("Difficulty")
                    yield Select(list(DIFFICULTIES), value="mixed", id="practice-difficulty", allow_blank=False, compact=True)
                with Horizontal(classes="row"):
                    yield Static("Include chapters I have not started yet")
                    yield Switch(True, id="practice-unstarted")
                with Horizontal(classes="row"):
                    yield Static("Written-answer marking")
                    yield Select([("Self-mark", "manual"), ("Automatic AI", "ai")], value="manual",
                                 id="practice-marking", allow_blank=False, compact=True)
                yield Static("Question types: Space toggles a type.", classes="hint")
                yield SelectionList(*(Selection(label, value, True, id=value) for label, value in topical_selection.TYPE_CHOICES),
                                    id="practice-types")
            with Vertical(id="practice-footer"):
                yield Static("", id="practice-availability", classes="hint")
                with Horizontal(id="practice-actions"):
                    yield Button("Start practice", id="practice-start", variant="primary", compact=True)
                    yield Button("Cancel", id="practice-cancel", compact=True)

    def on_mount(self) -> None:
        self.apply_remembered()
        self.refresh_summary()
        self.query_one("#practice-count", Input).focus()

    def apply_remembered(self) -> None:
        """Start from what was chosen last time: marking, count, difficulty, sources, types and not-started chapters."""
        s = self.app.settings
        self.query_one("#practice-marking", Select).value = "ai" if s.practice_auto_mark else "manual"
        self.query_one("#practice-count", Input).value = str(min(max(1, s.practice_count), topical_selection.COUNT_LIMIT))
        if s.practice_difficulty in dict((v, k) for k, v in DIFFICULTIES):
            self.query_one("#practice-difficulty", Select).value = s.practice_difficulty
        self.query_one("#practice-unstarted", Switch).value = bool(s.practice_unstarted)
        sources = [x for x in s.practice_sources.split(",") if x in dict((v, k) for k, v in SOURCES)]
        sel = self.query_one("#practice-sources", SelectionList)
        if sources:
            for _, value in SOURCES:
                (sel.select if value in sources else sel.deselect)(value)
        kinds = [x for x in s.practice_types.split(",") if x in dict((v, k) for k, v in topical_selection.TYPE_CHOICES)]
        types = self.query_one("#practice-types", SelectionList)
        if kinds:
            for _, value in topical_selection.TYPE_CHOICES:
                (types.select if value in kinds else types.deselect)(value)

    def remember(self, options: dict) -> None:
        """Keep this choice for the next set (written beside the other settings; a failed write is only not remembered)."""
        s = self.app.settings
        s.practice_auto_mark, s.practice_count = bool(options["auto_mark"]), options["count"]
        s.practice_difficulty, s.practice_unstarted = options["difficulty"], bool(options["include_unstarted"])
        s.practice_sources, s.practice_types = ",".join(options["sources"]), ",".join(options["types"])
        try:
            s.save(self.app.vault)
        except OSError:
            pass

    # ---------- what is chosen ----------
    def _focus(self) -> list[str]:
        """The chosen subtopics, less those not started when that is switched off."""
        if self.query_one("#practice-unstarted", Switch).value:
            return list(self.selected)
        t = self.app.tutor
        begun = started_chapters(t.state, t.packs)
        return [s for s in self.selected if s in begun]

    def refresh_summary(self) -> None:
        packs = self.app.tutor.packs
        where = {"course": f"Entire course {self.course}", "module": f"Entire topic in {self.course}"}.get(
            self.scope, "Chosen chapters" + (f" in {self.course}" if self.course else ""))
        titles = "; ".join(f"{s} {packs.subtopics.get(s, {}).get('title', '')}" for s in self.selected[:6])
        more = f"; and {len(self.selected) - 6} more" if len(self.selected) > 6 else ""
        self.query_one("#practice-summary", Static).update(f"{where}: {len(self.selected)} subtopics. {titles}{more}")
        self.refresh_availability()

    def refresh_availability(self) -> None:
        self._generation += 1
        self._counts = None
        self._load_counts(self._generation, self._focus())

    @work(thread=True, exclusive=True, group="practice-availability", exit_on_error=False)
    def _load_counts(self, generation: int, focus: list[str]) -> None:
        """What the question bank holds for this choice, read off the UI thread (it plans a set to count it)."""
        error = ""
        try:
            counts = self.app.tutor.topical_choices(focus) if focus else None
        except Exception as exc:  # noqa: BLE001 - say so; Start stays off
            counts, error = None, str(exc)
        try:
            self.app.call_from_thread(self._availability_ready, generation, counts, error)
        except Exception:  # noqa: BLE001 - the screen is gone
            pass

    def _availability_ready(self, generation: int, counts, error: str) -> None:
        if generation != self._generation or not self.is_attached:
            return
        self._counts, self._error = counts, error
        if counts is None and error:
            self.query_one("#practice-availability", Static).update(error)
            self.query_one("#practice-start", Button).disabled = True
            return
        types = self.query_one("#practice-types", SelectionList)
        if counts:
            for label, value in topical_selection.TYPE_CHOICES:
                types.replace_option_prompt(value, f"{label} · {counts['counts'][value]} available")
        self.update_availability()

    def _options(self) -> dict:
        text = self.query_one("#practice-count", Input).value.strip()
        if not text.isascii() or not text.isdecimal():
            raise ValueError(f"Choose a whole number of questions from 1 to {topical_selection.COUNT_LIMIT}.")
        count = int(text)
        topical_selection.validate_count(count)
        sources = [v for _, v in SOURCES if v in self.query_one("#practice-sources", SelectionList).selected]
        if not sources:
            raise ValueError("Choose at least one question source.")
        types = topical_selection.validate_types(self.query_one("#practice-types", SelectionList).selected)
        focus = self._focus()
        if not focus:
            raise ValueError("None of these chapters has been started. Switch on “Include chapters I have not started yet”.")
        return {"focus": focus, "course": self.course, "scope": self.scope, "sources": sources, "count": count,
                "difficulty": self.query_one("#practice-difficulty", Select).value,
                "include_unstarted": bool(self.query_one("#practice-unstarted", Switch).value),
                "types": types, "auto_mark": self.query_one("#practice-marking", Select).value == "ai"}

    def update_availability(self) -> None:
        start = self.query_one("#practice-start", Button)
        try:
            options = self._options()
            lines = []
            bank = None
            if "topical" in options["sources"]:
                bank = (self._counts or {}).get("counts") and sum(self._counts["counts"][k] for k in options["types"])
                if self._counts is None:
                    lines.append("Checking the question bank…")
                else:
                    lines.append(f"Past-paper bank: {bank} matching question{'s' if bank != 1 else ''}.")
            if "source_verified" in options["sources"]:
                lines.append("Source-verified: from the original papers; counts towards mastery.")
            if bank == 0 and options["sources"] == ["topical"]:
                raise ValueError("No eligible reviewed questions match these topics and types. Change topics or types.")
        except ValueError as exc:
            start.disabled = True
            message = str(exc)
        else:
            start.disabled = False
            message = " ".join(lines) + f" Up to {options['count']} questions, no repeats."
        self.query_one("#practice-availability", Static).update(message)

    @on(Input.Changed, "#practice-count")
    @on(SelectionList.SelectedChanged, "#practice-sources")
    @on(SelectionList.SelectedChanged, "#practice-types")
    @on(Select.Changed, "#practice-difficulty")
    def options_changed(self) -> None:
        self.update_availability()

    @on(Switch.Changed, "#practice-unstarted")
    def unstarted_changed(self) -> None:
        self.refresh_availability()
        self.update_availability()

    @on(Button.Pressed, "#practice-change")
    def change_topics(self) -> None:
        from .screens import PickerScreen

        picker = PickerScreen("practice", selected=self.selected)

        def chosen(focus):
            if focus:
                self.selected = list(focus)
                self.scope, self.course = classify(self.app.tutor.packs, self.selected, getattr(picker, "built", None))
                self.refresh_summary()
        self.app.push_screen(picker, chosen)

    @on(Button.Pressed, "#practice-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#practice-start")
    def action_start_set(self) -> None:
        if self.query_one("#practice-start", Button).disabled:
            return
        try:
            options = self._options()
        except ValueError as exc:
            self.app.notify(str(exc), severity="warning", timeout=6)
            return
        self.remember(options)
        self.dismiss(options)
