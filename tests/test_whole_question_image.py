"""A question whose choices live in the picture: Obsidian shows the whole-question image, the Terminal offers A to D.

Options are null in the pack for these items, so the image is the only place the choices are printed. The Obsidian
question block must embed the picture, must not show an answer, and the Terminal's choice panel must still list
A to D so the learner can answer."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "plugin/stem-tutor/skills/tutor/scripts"))
sys.path.insert(0, str(ROOT / "app"))

from tutorlib import views  # noqa: E402

IMAGE = "Assets/9702/9702-6-1-fig-p05-whole.png"


def _view(**extra):
    base = {"n": 1, "stem": "Three identical springs, each with the same spring constant, are connected together in four "
                            "different arrangements, as shown. Which arrangement has the largest combined spring constant?",
            "images": [IMAGE], "options": None, "kind": "mcq", "marks": 1}
    base.update(extra)
    return base


def test_obsidian_block_embeds_the_whole_question_picture():
    block = views.question_block(_view())
    assert f"![[{IMAGE}]]" in block
    assert "Which arrangement has the largest combined spring constant" in block


def test_obsidian_block_shows_no_answer_or_option_text_it_does_not_have():
    block = views.question_block(_view())
    assert "**A.**" not in block and "**B.**" not in block  # no invented option text
    assert "key" not in block.lower() and "answer:" not in block.lower()


def test_terminal_choice_panel_still_offers_A_to_D_when_options_are_null():
    from tutor_app.panels import ChoicePanel
    panel = ChoicePanel(1, None, confidence=False)
    assert list(panel.options) == ["A", "B", "C", "D"]
