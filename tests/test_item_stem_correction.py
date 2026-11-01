"""The approved item-selector set (2026-10-29): exact paths for source-verified corrections, nothing wider."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "build"))
import correction_review as cr  # noqa: E402


def _proposal(selector):
    return {"corrections": [{"selector": selector, "old": "a\x01b", "new": "a b", "reason": "PDF copy fault"}],
            "evidence": [{"source": "sources/papers/9701/2023/s/9701_s23_qp_11.pdf", "pdf_page": 10}]}


def test_each_approved_item_selector_is_accepted():
    for selector in cr.APPROVED_ITEM_SELECTORS:
        assert cr.validate_manifest(_proposal(selector)) == [], selector


def test_other_item_paths_are_refused():
    for selector in (["items", {"id": "9701-2.3-x011"}, "stem"],
                     ["items", {"id": "9701-2.3-x010"}, "explanation"],
                     ["items", {"id": "9701-2.3-x010"}, "options", "A"],
                     ["items", {"id": "9701-3.5-x011"}, "options", "E"],
                     ["items", {"id": "9701-3.5-x011"}, "answer"],
                     ["items", {"id": "9701-3.4-i18"}, "stem"]):
        assert "unsafe correction selector" in cr.validate_manifest(_proposal(selector)), selector
