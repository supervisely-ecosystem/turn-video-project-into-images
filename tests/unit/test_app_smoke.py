"""Imports the app (src.globals + src.main) offline, the way uvicorn does, against a fake API.

Covers the code touched for the hardened image (Python 3.14): modal.state parsing in src/globals.py
(distutils.strtobool replacement), the Sampling widget wiring in src/main.py and the run path
(settings handed to the SDK's sample_video_project, workflow lineage, shutdown).
"""

import importlib
import sys
from types import SimpleNamespace

import pytest
import supervisely as sly
from supervisely.api.dataset_api import DatasetApi
from supervisely.api.project_api import ProjectApi
from supervisely.api.team_api import TeamApi
from supervisely.api.workspace_api import WorkspaceApi
from supervisely.app.singleton import Singleton

PROJECT_ID = 9409
DATASETS = {"ds0": 1, "ds1": 2}


def _project_info():
    return SimpleNamespace(
        id=PROJECT_ID,
        name="videos",
        type=str(sly.ProjectType.VIDEOS),
        workspace_id=733,
        team_id=1,
        items_count=3,
        reference_image_url="https://example.invalid/preview.png",
        image_preview_url="https://example.invalid/preview.png",
        url="https://example.invalid/projects/9409",
        size=0,
        datasets_count=3,
    )


def _dataset_info(name, ds_id, parent_id=None, items=1):
    return SimpleNamespace(id=ds_id, name=name, parent_id=parent_id, items_count=items, project_id=PROJECT_ID)


ALL_DATASETS = [_dataset_info("ds0", 1), _dataset_info("ds1", 2), _dataset_info("child", 3, parent_id=1)]


@pytest.fixture
def load_app(monkeypatch, tmp_path):
    """Returns a loader that imports src.main with the given modal.state values; never touches the network."""

    def blocked(*args, **kwargs):
        raise AssertionError(f"unexpected network call: {args[1] if len(args) > 1 else args}")

    monkeypatch.setattr(sly.Api, "post", blocked)
    monkeypatch.setattr(sly.Api, "get", blocked)
    monkeypatch.setattr(ProjectApi, "get_info_by_id", lambda self, id, *a, **k: _project_info())
    meta = sly.ProjectMeta([sly.ObjClass("car", sly.Rectangle)])
    monkeypatch.setattr(ProjectApi, "get_meta", lambda self, id, *a, **k: meta.to_json())
    monkeypatch.setattr(
        DatasetApi, "get_info_by_name", lambda self, project_id, name, *a, **k: _dataset_info(name, DATASETS[name])
    )
    monkeypatch.setattr(DatasetApi, "get_list", lambda self, project_id, *a, **k: list(ALL_DATASETS))
    monkeypatch.setattr(
        DatasetApi, "get_info_by_id", lambda self, id, *a, **k: next(d for d in ALL_DATASETS if d.id == id)
    )

    monkeypatch.setattr(
        WorkspaceApi, "get_info_by_id", lambda self, id, *a, **k: SimpleNamespace(id=id, team_id=1, name="ws")
    )

    monkeypatch.setattr(TeamApi, "get_info_by_id", lambda self, id, *a, **k: SimpleNamespace(id=id, name="team"))

    # no local.env / ~/supervisely.env: real credentials must never be read by unit tests
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("ENV", raising=False)
    for key in ("TASK_ID", "SUPERVISELY_TASK_ID"):
        monkeypatch.delenv(key, raising=False)
    base = {
        "SERVER_ADDRESS": "https://sly.example.invalid",
        "API_TOKEN": "fake-token",
        "TEAM_ID": "1",
        "WORKSPACE_ID": "733",
        "PROJECT_ID": str(PROJECT_ID),
        "modal.state.slyProjectId": str(PROJECT_ID),
        "modal.state.Options": "all",
        "modal.state.allDatasets": "true",
        "modal.state.selectedDatasets": "[]",
        "modal.state.includeNestedDatasets": "true",
        "modal.state.sampleResultFrames": "false",
        "modal.state.framesStep": "10",
        "modal.state.copyAnnotations": "true",
        "modal.state.run": "false",
        "modal.state.batchSize": "32",
    }

    def load(**state):
        for key, value in {**base, **{f"modal.state.{k}": v for k, v in state.items()}}.items():
            if value is None:
                monkeypatch.delenv(key, raising=False)
            else:
                monkeypatch.setenv(key, value)
        Singleton._instances.clear()
        for name in ("src.main", "src.globals", "src.workflow"):
            sys.modules.pop(name, None)
        return importlib.import_module("src.main")

    yield load
    Singleton._instances.clear()
    for name in ("src.main", "src.globals", "src.workflow"):
        sys.modules.pop(name, None)


def test_defaults_all_frames_all_datasets(load_app):
    main = load_app()
    g = main.g
    assert (g.sample_result_frames, g.frames_step, g.only_annotated) == (False, 1, False)
    assert g.all_datasets and g.include_nested_datasets and g.copy_annotations and not g.run
    w = main.sampling_widget
    assert w.step == 1
    assert w.only_annotated is False
    assert w.include_nested_datasets is True
    assert w.selected_all_datasets is True
    assert w.copy_annotations is True


def test_annotated_sampled_selected_datasets(load_app):
    main = load_app(
        Options="annotated",
        sampleResultFrames="True",
        framesStep="5",
        allDatasets="false",
        selectedDatasets="['ds1']",
        includeNestedDatasets="false",
        copyAnnotations="false",
    )
    g = main.g
    assert (g.sample_result_frames, g.frames_step, g.only_annotated) == (True, 5, True)
    assert g.selected_datasets_ids == [DATASETS["ds1"]]
    w = main.sampling_widget
    assert (w.step, w.only_annotated, w.include_nested_datasets, w.copy_annotations) == (5, True, False, False)
    # known issue kept (MODERNIZE.md): the widget's "all datasets" checkbox is never unchecked, so the
    # selection is ignored and every dataset is processed (confirmed on dev with the published version)
    assert w.selected_all_datasets is True


def test_missing_nested_flag_defaults_to_false(load_app):
    main = load_app(includeNestedDatasets=None)
    assert main.g.include_nested_datasets is False


def test_annotated_without_classes_or_tags_fails_at_startup(load_app, monkeypatch):
    monkeypatch.setattr(ProjectApi, "get_meta", lambda self, id, *a, **k: sly.ProjectMeta().to_json())
    with pytest.raises(ValueError, match="Nothing to convert"):
        load_app(Options="annotated")


def test_invalid_sample_flag_fails_at_startup(load_app):
    with pytest.raises(ValueError, match="invalid truth value"):
        load_app(sampleResultFrames="maybe")


def test_run_passes_settings_to_sdk_and_records_lineage(load_app, monkeypatch):
    main = load_app(Options="annotated", sampleResultFrames="true", framesStep="3")
    calls = {}

    def fake_sample(api, project_id, settings, dst_project_id, datasets_ids, items_progress_cb, video_progress):
        calls["sample"] = dict(project_id=project_id, settings=settings, dst=dst_project_id, ds=datasets_ids)
        return SimpleNamespace(id=100)

    monkeypatch.setattr("supervisely.app.widgets.sampling.sampling.sample_video_project", fake_sample)
    lineage = []
    monkeypatch.setattr(main.wf, "workflow_input", lambda api, pid: lineage.append(("in", pid)))
    monkeypatch.setattr(main.wf, "workflow_output", lambda api, pid: lineage.append(("out", pid)))
    stopped = []
    monkeypatch.setattr(main.app, "shutdown", lambda *a, **k: stopped.append(True))

    main.sampling_widget.run()

    from supervisely.video.sampling import SamplingSettings as S

    assert calls["sample"]["project_id"] == PROJECT_ID
    assert calls["sample"]["dst"] is None  # always a new "<name>(images)" project
    assert calls["sample"]["settings"] == {
        S.ONLY_ANNOTATED: True,
        S.STEP: 3,
        S.RESIZE: None,
        S.COPY_ANNOTATIONS: True,
    }
    assert set(calls["sample"]["ds"]) == {1, 2, 3}  # the SDK widget may list a nested dataset twice
    # kept as is: the old code registers the source project as both input and output
    assert lineage == [("in", PROJECT_ID), ("out", PROJECT_ID)]
    assert stopped == [True]
