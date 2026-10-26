import pytest

from src.utils import strtobool


@pytest.mark.parametrize("value", ["y", "yes", "t", "true", "on", "1", "True", "TRUE", " true "])
def test_true_values(value):
    assert strtobool(value) is True


@pytest.mark.parametrize("value", ["n", "no", "f", "false", "off", "0", "False", "FALSE"])
def test_false_values(value):
    assert strtobool(value) is False


@pytest.mark.parametrize("value", ["", "2", "maybe", "null"])
def test_invalid_values_raise_like_distutils(value):
    with pytest.raises(ValueError, match="invalid truth value"):
        strtobool(value)
