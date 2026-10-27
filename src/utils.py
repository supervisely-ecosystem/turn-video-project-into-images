"""Small helpers with no platform access (unit-tested offline)."""

_TRUE = ("y", "yes", "t", "true", "on", "1")
_FALSE = ("n", "no", "f", "false", "off", "0")


def strtobool(value: str) -> bool:
    """Same rules as the removed ``distutils.util.strtobool`` (gone in Python 3.12), returning a bool.

    Raises ValueError for anything else, as distutils did.
    """
    normalized = value.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ValueError(f"invalid truth value {value!r}")


def resolve_dataset_ids(selected: list, datasets: list) -> list[int]:
    """Maps the modal's dataset selection to dataset ids, in selection order without duplicates.

    ``selected`` holds dataset names (what ``sly-select-dataset`` stores in ``modal.state.selectedDatasets``)
    or dataset ids (launch via API). ``datasets`` is the project's whole tree (``get_list(recursive=True)``).
    A name matches a top-level dataset first (as ``get_info_by_name`` did), otherwise a nested dataset whose
    name is unique among nested ones. Unknown or ambiguous entries raise ValueError.
    """
    by_id = {ds.id: ds for ds in datasets}
    ids = []
    for entry in selected:
        if isinstance(entry, int) and not isinstance(entry, bool):
            if entry not in by_id:
                raise ValueError(f"Selected dataset id {entry} is not in the project")
            ds_id = entry
        else:
            matches = [ds for ds in datasets if ds.name == entry]
            top_level = [ds for ds in matches if ds.parent_id is None]
            if top_level:
                matches = top_level
            if not matches:
                raise ValueError(f"Selected dataset {entry!r} is not in the project")
            if len(matches) > 1:
                raise ValueError(f"Selected dataset name {entry!r} matches {len(matches)} nested datasets")
            ds_id = matches[0].id
        if ds_id not in ids:
            ids.append(ds_id)
    return ids
