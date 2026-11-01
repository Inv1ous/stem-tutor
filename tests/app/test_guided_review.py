import pytest

from tutor_app.guided_review import consecutive_prime_warning, geometric_subtraction_note


@pytest.mark.parametrize('answer', [
    'It is not true that S-rS = a-ar^n.',
    'Never write rS-S = ar^n-a.',
    'I did not use S-rS = a-ar^n.',
])
def test_geometric_note_does_not_endorse_negated_working(answer):
    assert geometric_subtraction_note(answer) is None


@pytest.mark.parametrize('answer', [
    'The primes 3, 7 and 11 sum to 21, not divisible by 5.',
    'The consecutive primes 1, 2 and 3 sum to 6, not divisible by 5.',
    'The primes 3, 7 and 11 sum to 21, which is not divisible by 5, so the claim is false.',
    'The consecutive primes 1, 2 and 3 sum to 6, not divisible by 5, so the claim is false.',
])
def test_flags_clear_invalid_triples(answer):
    assert 'not three consecutive primes' in consecutive_prime_warning(answer)


@pytest.mark.parametrize('answer', [
    'The consecutive primes 5, 7 and 11 sum to 23.',
    'The consecutive primes 11, 7 and 5 sum to 23.',
    'The primes 7, 5 and 11 sum to 23.',
    'The consecutive primes 5, 7 and 11 sum to 23. It is not divisible by 5, so the claim is false.',
    'Perhaps use a triple of primes.',
    'The primes 3, 7 and 11 are not consecutive primes.',
    'The primes 3, 7 and 11, or primes 5, 7 and 11.',
    'The primes 1000001, 1000003 and 1000033.',
])
def test_valid_negated_ambiguous_or_oversized_input_has_no_warning(answer):
    assert consecutive_prime_warning(answer) is None


@pytest.mark.parametrize('answer', ['Choose x=−1 and y=2.', 'x=0, y=3'])
def test_positive_domain_warning_flags_explicit_invalid_values(answer):
    from tutor_app.guided_review import positive_pair_warning
    assert 'positive' in positive_pair_warning(answer).lower()


@pytest.mark.parametrize('answer', ['x=1 and y=1', 'x=1/2 and y=2', 'x=-1 or x=1, y=2',
                                     'I did not choose x=-1 and y=2', 'x=-1.5, y=2', 'x=-1+2, y=2', 'x=-1e0+2, y=2',
                                     'If x=-1 and y=2, that would be invalid; I choose (1,2).',
                                     'x=-1×-1, y=2', 'x=-1 - (-2), y=2', 'x=1, y=0!', 'Reject x=-1 and y=2; choose (1,2).'])
def test_positive_domain_warning_does_not_guess_ambiguous_or_valid_values(answer):
    from tutor_app.guided_review import positive_pair_warning
    assert positive_pair_warning(answer) is None
