"""Provider-independent AI marking policy; deterministic grading stays in the engine."""
from __future__ import annotations

LEVELS = ('auto', 'lenient', 'balanced', 'strict')
CHOICES = [(level.title(), level) for level in LEVELS]
DESCRIPTIONS = {
    'auto': 'Auto: Balanced for learning/review; Strict for Practice, Test prep, Long questions, Topical past papers and Challenges.',
    'lenient': 'Lenient: credit a clearly correct core idea despite informal wording or minor nonessential omissions.',
    'balanced': 'Balanced: require each substantive idea; accept equivalent wording and valid methods.',
    'strict': 'Strict: require precise evidence of every required idea, relationship, unit and requested precision; accept equivalent wording.',
}
_EXAM_MODES = frozenset(('test', 'long', 'topical', 'practice', 'challenge'))
_INSTRUCTIONS = {
    'lenient': 'Use a supportive practice standard. Credit a clearly demonstrated correct core idea despite informal '
               'language or a minor nonessential omission. Do not penalise harmless grammar or spelling. '
               'Substantive scientific requirements and causal relationships still have to be present.',
    'balanced': 'Use a fair assessment standard. Require every substantive idea and relationship in the mark point, '
                'but credit clear paraphrases, synonyms and valid alternative methods without demanding model-answer phrasing.',
    'strict': 'Use an exam standard. Require precise, unambiguous evidence of every substantive requirement, including '
              'terminology, units and precision explicitly required by the question. A vague allusion is insufficient; '
              'verbatim model-answer phrasing is never required.',
}


def resolve(level: str, mode: str = '') -> str:
    """Resolve Auto by task purpose, never by model, confidence or previous scores."""
    if level not in LEVELS or level == 'auto':
        return 'strict' if mode in _EXAM_MODES else 'balanced'
    return level


def instruction(level: str = 'auto', mode: str = '') -> str:
    """One shared contract for initial marks and requested second opinions."""
    effective = resolve(level, mode)
    return (f'AI MARKING STRICTNESS: {effective.title()}'
            f'{" (Auto, selected by study mode)" if level == "auto" or level not in LEVELS else ""}.\n'
            f'{_INSTRUCTIONS[effective]}\n'
            'Read the entire student answer, including every paragraph and explicit working, before judging any '
            'point missing. Accept equivalent correct wording and scientifically valid alternative methods. '
            'Evaluate the meaning in context, not an exact phrase match. Do not add requirements beyond the question '
            'and supplied mark points, including extra model-answer detail for a one-mark point. '
            'Ignore self-rated confidence when deciding credit. A point is met only if its substantive idea is '
            'present and not contradicted. Related vocabulary alone is insufficient. Do not infer an unstated mechanism '
            'or award an absent point because another point was discussed. In why, quote the shortest relevant part '
            'of the student answer; if evidence is absent, name the specific missing idea only after checking the '
            'whole answer. Never quote the supplied correct answer as evidence that the student said it.')
