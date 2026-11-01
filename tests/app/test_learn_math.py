from tutor_app.learn_math import check_equality


def test_symbolic_and_numeric_equalities_are_checked():
    assert check_equality("(2*k+1)**2", "4*k**2+4*k+1") is True
    assert check_equality("2+2", "5") is False


def test_unsupported_or_unsafe_expressions_are_not_certified():
    assert check_equality("sin(x)", "x") is None
    assert check_equality("__import__('os')", "1") is None
    assert check_equality("2**100000000", "0") is None
    assert check_equality("1/0", "1") is None


def test_unbounded_expansion_and_variable_denominators_are_not_certified():
    assert check_equality("((((x+1)**8)**8)**8)**8", "0") is None
    assert check_equality("x/x", "1") is None
