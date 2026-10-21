"""Answer protection for keys that retain the requested equation subject."""
from tutor_app import ai


def test_an_equation_key_still_protects_its_bare_right_side():
    """B-059: adding the required subject must not let the AI reveal the right side."""
    key = "v^2 = u**2 + 2*a*s"
    for reply in ("u^2+2as", "Try $u² + 2as$.", "The answer is 2as + u^2", "v^2 = 2as + u^2"):
        assert ai.leaks(reply, key, "expression"), reply
    assert not ai.leaks("Eliminate the time using the two equations.", key, "expression")
