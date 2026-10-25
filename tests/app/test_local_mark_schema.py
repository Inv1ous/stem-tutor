"""Constrained local point copying prevents harmless LaTeX rewrites without weakening marking identity."""
import copy

from tutor_app import ai, prompts


def test_local_mark_schema_preserves_points_exactly_and_does_not_mutate_shared_schema():
    before=copy.deepcopy(prompts.JUDGE)
    points=['Probability = 5/8','p = 4e-4 Pa']
    schema=prompts.local_judge_schema(points)
    array=schema['properties']['points']
    assert array['minItems']==array['maxItems']==2
    assert array['items']['properties']['point']=={'type':'string','enum':points}
    assert prompts.JUDGE==before and 'enum' not in before['properties']['points']['items']['properties']['point']
    good={'points':[{'point':point,'met':True} for point in points],'feedback':'Both ideas are present.'}
    assert ai.matches_points(good,points)
    rewritten=copy.deepcopy(good)
    rewritten['points'][0]['point']=r'Probability = $\frac{5}{8}$'
    assert not ai.matches_points(rewritten,points)  # the host guard is intentionally unchanged
    assert not ai.matches_points({**good,'points':good['points'][::-1]},points)
