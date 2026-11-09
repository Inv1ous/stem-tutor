"""Original-source practice, deliberately separate from adaptive Tutor sessions."""
from __future__ import annotations

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Input, Select, Static, TextArea

from tutorlib.source_practice import Collection
from .lesson_media import figure_previews
from . import mac


class SourcePracticeScreen(Screen):
    BINDINGS = [Binding('escape', 'back', 'Back'),
                Binding('ctrl+o', 'open_full_size', 'Open full size', priority=True)]
    DEFAULT_CSS = '''
    SourcePracticeScreen > VerticalScroll { padding: 1 2; }
    SourcePracticeScreen Select { height: 3; }
    SourcePracticeScreen TextArea { height: 8; margin: 1 0; }
    SourcePracticeScreen Horizontal { height: auto; }
    SourcePracticeScreen #practice-award { width: 12; }
    SourcePracticeScreen #practice-status { margin: 1 0; }
    '''

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static('Source-verified practice · No mastery credit', classes='title')
            yield Static('Original questions and official answers. Detailed skill mapping has not been certified; this practice does not change mastery.')
            yield Select([], id='practice-course', prompt='Course')
            yield Select([], id='practice-source', prompt='Source')
            yield Select([], id='practice-question', prompt='Question')
            yield Static('', id='practice-question-text', markup=False)
            with VerticalScroll(id='practice-images'): pass
            yield Button('Open original question images', id='practice-open')
            yield TextArea(id='practice-answer')
            yield Button('Submit answer', id='practice-submit', variant='primary')
            yield Static('', id='practice-status', markup=False)
            yield Button('Open original mark scheme in full size', id='practice-open-scheme', disabled=True)
            with VerticalScroll(id='practice-scheme'): pass
            with Horizontal():
                yield Input(placeholder='Award', id='practice-award', type='integer')
                yield Button('Save self-mark', id='practice-save-mark', disabled=True)
            with Horizontal():
                yield Button('Explain with AI', id='practice-explain', disabled=True)
                yield Button('Ask AI for a suggested mark', id='practice-ai-mark', disabled=True)
            yield Static('', id='practice-ai-result', markup=False)
        yield Footer()

    def on_mount(self):
        self.current = None; self.attempt_id = None; self.feedback = None; self.drafts = {}; self.busy = False
        try: self.collection = Collection(self.app.vault)
        except (OSError, ValueError) as exc:
            self.query_one('#practice-status', Static).update(f'No source practice collection is available: {exc}')
            self.query_one('#practice-submit', Button).disabled = True
            return
        courses = self.collection.courses()
        self.query_one('#practice-course', Select).set_options([(c, c) for c in courses])
        if courses: self.query_one('#practice-course', Select).value = courses[0]

    @on(Select.Changed, '#practice-course')
    def course_changed(self, event):
        if event.value is Select.NULL or event.value != event.select.value: return
        source = self.query_one('#practice-source', Select)
        values = self.collection.sources(event.value)
        source.set_options([(s, s) for s in values]); source.value = values[0] if values else Select.NULL

    @on(Select.Changed, '#practice-source')
    def source_changed(self, event):
        if event.value is Select.NULL or event.value != event.select.value: return
        course = self.query_one('#practice-course', Select).value
        values = self.collection.questions(course, event.value)
        question = self.query_one('#practice-question', Select)
        question.set_options([(f"Question {q['label']} · {q['kind']}", q['id']) for q in values])
        question.value = values[0]['id'] if values else Select.NULL

    @on(Select.Changed, '#practice-question')
    async def question_changed(self, event):
        if event.value is Select.NULL or event.value != event.select.value: return
        if self.current: self.drafts[self.current['id']] = self.query_one('#practice-answer', TextArea).text
        self.current = self.collection.question(event.value); self.attempt_id = None; self.feedback = None
        row = self.current
        self.query_one('#practice-answer', TextArea).text = self.drafts.get(row['id'], '')
        # a question with images is shown by its images: the text pulled from the PDF is not shown beside them
        text = '' if row.get('context_media') or row['question_media'] else row.get('question_text', '')
        self.query_one('#practice-question-text', Static).update(f"{row['title']} · Question {row['label']} · {row['marks']} marks\n{text}")
        self.query_one('#practice-status', Static).update('Choose A–D and submit.' if row['kind'] == 'mcq' else 'Write your working and submit to unlock the original mark scheme. Maximum: printed question total.')
        self.query_one('#practice-ai-result', Static).update('')
        self.query_one('#practice-award', Input).value = ''
        for selector in ('#practice-save-mark', '#practice-explain', '#practice-ai-mark', '#practice-open-scheme'):
            self.query_one(selector, Button).disabled = True
        self.query_one('#practice-submit', Button).disabled = False
        for selector in ('#practice-images', '#practice-scheme'):
            await self.query_one(selector).remove_children()
        for preview in figure_previews(self.app.vault, row.get('context_media', []) + row['question_media']):
            if preview: await self.query_one('#practice-images').mount(Static(preview))

    def _open_images(self, references, *, attempt_id=None, label='question'):
        try:
            if not references: raise ValueError('No original images are available.')
            # Authenticate the entire ordered scope before opening any image.
            for reference in references:
                self.collection.media_path(self.current['id'], reference, attempt_id=attempt_id)
            for index, reference in enumerate(references, 1):
                if not mac.open_in_obsidian(self.app.vault, reference, background=False):
                    raise OSError(f'Image {index} of {len(references)} was not opened.')
        except (OSError, ValueError) as exc:
            self.query_one('#practice-status', Static).update(f'Could not open original {label} images: {exc}')
            return
        self.query_one('#practice-status', Static).update(f'Opened {len(references)} original {label} image(s) in full size. No mastery credit.')

    @on(Button.Pressed, '#practice-open')
    def open_original(self):
        if not self.current: return
        self._open_images(self.current.get('context_media', []) + self.current['question_media'])

    @on(Button.Pressed, '#practice-open-scheme')
    def open_scheme(self):
        if not self.current or self.current['kind'] == 'mcq' or not self.attempt_id: return
        try:
            # Re-read owned attempt feedback; never trust a stale visible scheme.
            feedback = self.collection.feedback(self.attempt_id)
            self._open_images(feedback['scheme_media'], attempt_id=self.attempt_id, label='mark scheme')
        except (OSError, ValueError) as exc:
            self.query_one('#practice-status', Static).update(f'Could not open original mark scheme images: {exc}')

    def action_open_full_size(self):
        if self.current and self.current['kind'] != 'mcq' and self.attempt_id:
            self.open_scheme()
        else:
            self.open_original()

    @on(Button.Pressed, '#practice-submit')
    async def submit(self):
        if not self.current: return
        try:
            record = self.collection.submit(self.current['id'], self.query_one('#practice-answer', TextArea).text)
            self.attempt_id = record['attempt_id']; self.feedback = self.collection.feedback(self.attempt_id)
        except (ValueError, OSError) as exc:
            self.query_one('#practice-status', Static).update(str(exc)); return
        feedback = self.feedback
        self.query_one('#practice-submit', Button).disabled = True
        self.query_one('#practice-explain', Button).disabled = False
        if self.current['kind'] == 'mcq':
            self.query_one('#practice-status', Static).update(f"{'Correct.' if feedback['awarded'] else 'Not quite.'} Official answer: {feedback['answer']}. No mastery credit.")
        else:
            self.query_one('#practice-status', Static).update(f"Attempt saved. Compare with the complete original scheme and self-mark 0–{feedback['marks']}. No mastery credit.")
            await self.query_one('#practice-scheme').mount(Static(feedback['scheme_text'], markup=False))
            for reference in feedback['scheme_media']:
                self.collection.media_path(self.current['id'], reference, attempt_id=self.attempt_id)
            for preview in figure_previews(self.app.vault, feedback['scheme_media']):
                if preview: await self.query_one('#practice-scheme').mount(Static(preview))
            self.query_one('#practice-save-mark', Button).disabled = False
            self.query_one('#practice-ai-mark', Button).disabled = False
            self.query_one('#practice-open-scheme', Button).disabled = False

    @on(Button.Pressed, '#practice-save-mark')
    def save_mark(self):
        try:
            value = self.query_one('#practice-award', Input).value
            if not value.isdigit(): raise ValueError('Enter an integer award.')
            self.collection.award(self.attempt_id, int(value))
        except (ValueError, OSError) as exc:
            self.query_one('#practice-status', Static).update(str(exc)); return
        self.query_one('#practice-save-mark', Button).disabled = True
        self.query_one('#practice-status', Static).update(f'Self-mark saved: {value}/{self.current["marks"]}. No mastery credit.')

    @on(Button.Pressed, '#practice-explain')
    @on(Button.Pressed, '#practice-ai-mark')
    def request_ai(self, event):
        self.ai_help(event.button.id == 'practice-ai-mark')

    @work(exclusive=True)
    async def ai_help(self, marking=False):
        if self.busy or not self.attempt_id: return
        self.busy = True
        qid, attempt_id = self.current['id'], self.attempt_id
        try:
            attempt = self.collection._attempt(attempt_id)
            row = self.current; feedback = self.collection.feedback(attempt_id)
            refs = row.get('context_media', []) + row['question_media'] + feedback.get('scheme_media', [])
            images = [self.collection.media_path(qid, ref, attempt_id=attempt_id) for ref in refs]
            awarded = feedback.get('awarded')
            if row['kind'] == 'mcq':
                result_label = 'correct' if awarded == row['marks'] else 'incorrect'
            elif awarded is None:
                result_label = 'unmarked'
            else:
                result_label = 'full marks (self-marked)' if awarded == row['marks'] else 'partial marks (self-marked)'
            prompt = ('Suggest a mark and explain it against the original scheme. The learner will confirm the award.' if marking else
                      'Explain using the original question and official answer/scheme. For correct work or self-marked full marks, give concise confirmation and the key reason. '
                      'For incorrect work or self-marked partial marks, give focused correction of the learner’s error and the next useful step. '
                      'For unmarked written work, compare with the scheme without assuming correctness. Respect saved self-marks as learner-confirmed, not AI or official grading. Give full detail only when requested.')
            prompt += f'\nResult: {result_label}. AI suggestions do not change saved marks or mastery.'
            prompt += f"\nQuestion: {row.get('question_text', '')}\nLearner work: {attempt['answer']}\nMaximum: {row['marks']}\nOfficial feedback: {feedback}"
            schema = {'type': 'object', 'properties': {'text': {'type': 'string'}, 'suggested_award': {'type': 'integer'}}, 'required': ['text']}
            settings = self.app.settings
            chosen = (settings.ai_mark_model if marking else settings.ai_explain_model) or settings.model
            result, status = await self.app.ai.one_shot(prompt, schema=schema, model=chosen, images=images)
            if not status.ok or not isinstance(result, dict) or not isinstance(result.get('text'), str):
                raise ValueError(getattr(status, 'message', '') or 'AI did not return usable feedback')
            if self.attempt_id != attempt_id: return
            self.query_one('#practice-ai-result', Static).update(result['text'])
            suggestion = result.get('suggested_award')
            if marking and type(suggestion) is int and 0 <= suggestion <= row['marks']:
                self.query_one('#practice-award', Input).value = str(suggestion)
                self.query_one('#practice-status', Static).update('AI suggestion only. Check the original scheme, then Save self-mark to confirm.')
        except Exception as exc:
            if self.attempt_id == attempt_id:
                self.query_one('#practice-status', Static).update(f'AI unavailable: {exc}. Your work is saved; self-mark using the original scheme.')
        finally: self.busy = False

    def action_back(self):
        self.app.pop_screen()
