"""Convert worked-example faded checks into question items."""
from __future__ import annotations

import copy


def question_item(faded, kc):
    if not isinstance(faded, dict) or any(not isinstance(faded.get(k), str) or not faded[k].strip()
                                          for k in ('id', 'problem')):
        raise ValueError('faded check needs an id and problem')
    base = {'id': faded['id'], 'kcs': [kc], 'stem': faded['problem'], 'difficulty': 3}
    if 'kind' not in faded:
        answer = faded.get('answer')
        if not isinstance(answer, dict) or ('value' in answer) == ('expr' in answer):
            raise ValueError('invalid faded answer')
        return {**base, 'kind': 'numeric' if 'value' in answer else 'expression',
                'answer': copy.deepcopy(answer), 'marks': 2}
    rubric = faded.get('rubric')
    if (faded['kind'] != 'short' or 'answer' in faded or not isinstance(faded.get('review_answer'), str)
            or not faded['review_answer'].strip() or not isinstance(rubric, list) or not rubric
            or any(not isinstance(p, dict) or not isinstance(p.get('point'), str) or not p['point'].strip()
                   or not isinstance(p.get('keywords'), list) or not p['keywords']
                   or any(not isinstance(group, list) or not group or
                          any(not isinstance(k, str) or not k.strip() for k in group)
                          for group in p['keywords']) for p in rubric)):
        raise ValueError('invalid written faded check')
    return {**base, 'kind': 'short', 'written_faded': True, 'review_answer': faded['review_answer'],
            'rubric': copy.deepcopy(rubric), 'marks': len(rubric)}
