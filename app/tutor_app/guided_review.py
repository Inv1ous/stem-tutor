"""Narrow, optional checks to help review a written guided answer."""
from __future__ import annotations

import re

_TRIPLE = re.compile(r"\bprimes?\s+(\d{1,7})\s*,\s*(\d{1,7})\s*(?:,?\s+and\s+|,\s*)(\d{1,7})\b", re.I)
_NEGATION = re.compile(r"\b(?:not|never|isn't|aren't|cannot|can't)\s+(?:the\s+)?(?:three\s+)?"
                       r"(?:consecutive|primes?)\b", re.I)


def positive_pair_warning(answer: str) -> str | None:
    """Check only one explicit integer assignment for each of x and y."""
    if not isinstance(answer, str) or len(answer) > 2000:
        return None
    text = answer.replace('−', '-')
    match = re.fullmatch(r'\s*(?:(?:choose|take|let)\s+)?x\s*=\s*([+-]?\d{1,6})'
                         r'\s*(?:[,;]\s*(?:and\s+)?|\s+and\s+)y\s*=\s*([+-]?\d{1,6})\s*\.?\s*',
                         text, re.I)
    if not match:
        return None
    values = [int(value) for value in match.groups()]
    try:
        from sympy import Integer
        if any(Integer(value) <= 0 for value in values):
            return 'At least one chosen value is not positive. Check the stated domain before accepting marks.'
    except ImportError:
        return None
    return None


def geometric_subtraction_note(answer: str) -> str | None:
    """Recognise only the explicit unfactorised lines in this specific proof."""
    if not isinstance(answer, str) or len(answer) > 2000:
        return None
    # A formula mentioned in a negation is not necessarily the student's step.
    # Decline to interpret the whole answer rather than guess its scope.
    if re.search(r"\b(?:not|never|no|isn't|aren't|wasn't|weren't|cannot|can't|don't|didn't)\b", answer, re.I):
        return None
    compact = answer.replace('$', '').replace('−', '-').replace('^{n}', '^n')
    compact = re.sub(r'\s*([=+\-^])\s*', r'\1', compact)
    start = r'(?<![A-Za-z0-9+*/^\-])'
    end = r'(?![A-Za-z0-9+*/^\-(\[])'
    wrong = (start + r'S-rS=ar\^n-a' + end, start + r'rS-S=a-ar\^n' + end)
    valid = (start + r'S-rS=a-ar\^n' + end, start + r'rS-S=ar\^n-a' + end)
    if any(re.search(pattern, compact) for pattern in wrong):
        return 'Check the sign in the displayed subtraction line and whether it was corrected before accepting marks.'
    if any(re.search(pattern, compact) for pattern in valid):
        return 'This subtraction order is valid. Check the remaining steps before accepting marks.'
    return None


def consecutive_prime_warning(answer: str) -> str | None:
    """Check one explicit positive-integer triple; leave other wording to the learner."""
    if not isinstance(answer, str) or len(answer) > 2000 or _NEGATION.search(answer):
        return None
    matches = list(_TRIPLE.finditer(answer))
    if len(matches) != 1:
        return None
    # The set of primes is consecutive regardless of the order in which the
    # learner lists its members; repeated values still fail nextprime checks.
    values = tuple(sorted(int(value) for value in matches[0].groups()))
    if any(value > 1_000_000 for value in values):
        return None
    try:
        from sympy import isprime, nextprime
        valid = all(isprime(value) for value in values) and all(
            nextprime(first) == second for first, second in zip(values, values[1:]))
    except ImportError:
        return None
    if not valid:
        return "These numbers are not three consecutive primes. Check the domain before accepting marks."
    return None
