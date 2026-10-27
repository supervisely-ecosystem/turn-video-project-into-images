from types import SimpleNamespace

import pytest

from src.utils import resolve_dataset_ids, strtobool


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


def _ds(ds_id, name, parent_id=None):
    return SimpleNamespace(id=ds_id, name=name, parent_id=parent_id)


# a/ (1) -> x (3), b/ (2) -> x (4), b/ -> a (5), c (6) under a/x
TREE = [_ds(1, "a"), _ds(2, "b"), _ds(3, "x", 1), _ds(4, "x", 2), _ds(5, "a", 2), _ds(6, "c", 3)]


@pytest.mark.parametrize(
    ("selected", "expected"),
    [
        (["b", "a"], [2, 1]),  # selection order kept
        (["a"], [1]),  # top-level wins over a nested namesake
        (["c"], [6]),  # unique nested name
        ([6, "c", 2], [6, 2]),  # ids, no duplicates
        ([], []),
    ],
)
def test_resolve_dataset_ids(selected, expected):
    assert resolve_dataset_ids(selected, TREE) == expected


@pytest.mark.parametrize(
    ("selected", "message"),
    [(["x"], "matches 2 nested datasets"), (["nope"], "'nope' is not in the project"), ([42], "id 42")],
)
def test_resolve_dataset_ids_rejects_unknown_or_ambiguous(selected, message):
    with pytest.raises(ValueError, match=message):
        resolve_dataset_ids(selected, TREE)
