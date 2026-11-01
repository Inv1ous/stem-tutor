"""Unexpected model numbers must not crash answer protection or become false zeroes."""
import pytest
from tutor_app.ai import _numbers, leaks


@pytest.mark.parametrize('text',['10^999','10^{999999999999999999999}','10^'+'9'*4500])
def test_unrepresentable_power_does_not_abort_guard_for_later_answer(text):
    assert leaks(f'Consider {text}; the result is 3 m.', '3 m','numeric',{'value':3,'unit':'m'})


@pytest.mark.parametrize('text',['10^{-9999}','10^999','1e9999'])
def test_unrepresentable_numbers_are_not_yielded_as_finite_values(text):
    assert list(_numbers(text))==[]


def test_extreme_power_is_not_mistaken_for_zero():
    assert not leaks('10^{-9999}','0','numeric',{'value':0,'exact':True})
    assert leaks('0','0','numeric',{'value':0,'exact':True})
    assert list(_numbers('10^-3'))[0][0]==0.001
