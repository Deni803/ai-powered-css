from app.confidence import compute_confidence


def test_confidence_weighted():
    assert compute_confidence(0.8, 0.6) == 0.72


def test_confidence_fallback():
    assert compute_confidence(0.5, None) == 0.5
    assert compute_confidence(None, 0.4) == 0.4
