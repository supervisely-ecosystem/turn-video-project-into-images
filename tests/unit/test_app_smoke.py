"""Imports the app (src.globals + src.main) offline, the way uvicorn does, against a fake API.

Covers the code touched for the hardened image (Python 3.14): modal.state parsing in src/globals.py
(distutils.strtobool replacement), the Sampling widget wiring in src/main.py and the run path
(settings handed to the SDK's sample_video_project, workflow lineage, shutdown), plus the three bugs fixed
after the move (MODERNIZE.md): dataset selection, workflow output, shutdown on failure.
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
RESULT_PROJECT_ID = 100
TASK_ID = 555


def _project_info(project_id=PROJECT_ID):
    """The source videos project, or (any other id) the images project the app creates."""
    source = project_id == PROJECT_ID
    return SimpleNamespace(
        id=project_id,
        name="videos" if source else "videos(images)",
        type=str(sly.ProjectType.VIDEOS if source else sly.ProjectType.IMAGES),
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


# ds0 (1) -> child (3); ds1 (2)
ALL_DATASETS = [_dataset_info("ds0", 1), _dataset_info("ds1", 2), _dataset_info("child", 3, parent_id=1)]


@pytest.fixture
def load_app(monkeypatch, tmp_path):
    """Returns a loader that imports src.main with the given modal.state values; never touches the network."""

    def blocked(*args, **kwargs):
        raise AssertionError(f"unexpected network call: {args[1] if len(args) > 1 else args}")

    monkeypatch.setattr(sly.Api, "post", blocked)
    monkeypatch.setattr(sly.Api, "get", blocked)
    monkeypatch.setattr(ProjectApi, "get_info_by_id", lambda self, id, *a, **k: _project_info(id))
    meta = sly.ProjectMeta([sly.ObjClass("car", sly.Rectangle)])
    monkeypatch.setattr(ProjectApi, "get_meta", lambda self, id, *a, **k: meta.to_json())
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
    assert g.selected_datasets_ids == [2]
    w = main.sampling_widget
    assert (w.step, w.only_annotated, w.include_nested_datasets, w.copy_annotations) == (5, True, False, False)
    assert w.selected_all_datasets is False
    assert w.selected_datasets_ids == [2]


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


@pytest.fixture
def run_app(monkeypatch):
    """Runs a loaded app's conversion with the SDK's sample_video_project, lineage, task output error and
    shutdown faked; returns what each of them received. The flags make the conversion, the error report or
    the lineage call fail."""

    def run(main, fail_with=None, report_fails=False, lineage_fails=False):
        rec = SimpleNamespace(sample=None, lineage=[], errors=[], stopped=0)

        def fake_sample(api, project_id, settings, dst_project_id, datasets_ids, items_progress_cb, video_progress):
            rec.sample = dict(project_id=project_id, settings=settings, dst=dst_project_id, ds=datasets_ids)
            video_progress.close()  # else it flushes into the cleared widget state when collected
            if fail_with is not None:
                raise fail_with
            return SimpleNamespace(id=RESULT_PROJECT_ID)

        def fake_shutdown(*a, **k):
            rec.stopped += 1

        def fake_input(api, pid):
            if lineage_fails:
                raise ConnectionError("instance is gone")
            rec.lineage.append(("in", pid))

        def fake_set_output_error(task_id, title, description=None):
            if report_fails:
                raise ConnectionError("instance is gone")
            rec.errors.append((task_id, description))

        monkeypatch.setattr("supervisely.app.widgets.sampling.sampling.sample_video_project", fake_sample)
        monkeypatch.setattr(main.wf, "workflow_input", fake_input)
        monkeypatch.setattr(main.wf, "workflow_output", lambda api, pid: rec.lineage.append(("out", pid)))
        monkeypatch.setattr(main.g, "task_id", TASK_ID)
        monkeypatch.setattr(main.g.api.task, "set_output_error", fake_set_output_error)
        monkeypatch.setattr(main.app, "shutdown", fake_shutdown)
        main.sampling_widget.run()
        return rec

    return run


def test_run_passes_settings_to_sdk_and_records_lineage(load_app, run_app):
    main = load_app(Options="annotated", sampleResultFrames="true", framesStep="3")

    rec = run_app(main)

    from supervisely.video.sampling import SamplingSettings as S

    assert rec.sample["project_id"] == PROJECT_ID
    assert rec.sample["dst"] is None  # always a new "<name>(images)" project
    assert rec.sample["settings"] == {
        S.ONLY_ANNOTATED: True,
        S.STEP: 3,
        S.RESIZE: None,
        S.COPY_ANNOTATIONS: True,
    }
    assert set(rec.sample["ds"]) == {1, 2, 3}  # the SDK widget may list a nested dataset twice
    assert rec.lineage == [("in", PROJECT_ID), ("out", RESULT_PROJECT_ID)]
    assert rec.errors == []
    assert rec.stopped == 1
    assert main.sampling_widget.run_button.loading is False


# Bug 1: the dataset selection was ignored (the widget's "all datasets" box stayed checked).


@pytest.mark.parametrize(
    ("selected", "nested", "expected"),
    [
        ("['ds1']", "false", [2]),  # one of two top-level datasets
        ("['ds0']", "false", [1]),  # its nested dataset is left out
        ("['ds0']", "true", [1, 3]),  # ... or included with includeNestedDatasets
        ("['child']", "false", [3]),  # a nested dataset selected on its own
        ('["ds0", "ds1"]', "false", [1, 2]),
        ("[2]", "false", [2]),  # ids (launch via API) work as well as names
    ],
)
def test_selected_datasets_are_the_only_ones_converted(load_app, run_app, selected, nested, expected):
    main = load_app(allDatasets="false", selectedDatasets=selected, includeNestedDatasets=nested)
    assert main.sampling_widget.selected_all_datasets is False

    rec = run_app(main)

    assert sorted(set(rec.sample["ds"])) == expected
    assert rec.stopped == 1


@pytest.mark.parametrize(("all_datasets", "selected"), [("true", "['ds1']"), ("false", "[]")])
def test_whole_project_when_all_datasets_or_nothing_selected(load_app, run_app, all_datasets, selected):
    main = load_app(allDatasets=all_datasets, selectedDatasets=selected, includeNestedDatasets="true")
    assert main.g.all_datasets is True
    assert main.sampling_widget.selected_all_datasets is True

    rec = run_app(main)

    assert set(rec.sample["ds"]) == {1, 2, 3}


def test_unknown_selected_dataset_fails_at_startup(load_app):
    with pytest.raises(ValueError, match="'gone' is not in the project"):
        load_app(allDatasets="false", selectedDatasets="['gone']")


# Bug 2: the workflow output pointed to the source project instead of the created one (asserted above too).


def test_workflow_output_is_the_created_images_project(load_app, run_app):
    rec = run_app(load_app())

    outputs = [pid for kind, pid in rec.lineage if kind == "out"]
    assert outputs == [RESULT_PROJECT_ID]
    assert PROJECT_ID not in outputs


# Bug 3: a failure in the run never reached app.shutdown(), so the task was left running.


def test_failure_is_reported_and_app_shuts_down(load_app, run_app):
    main = load_app()

    rec = run_app(main, fail_with=RuntimeError("video is broken"))

    assert rec.stopped == 1
    assert rec.errors == [(TASK_ID, "RuntimeError('video is broken')")]
    assert rec.lineage == []  # nothing was created, no lineage
    assert main.sampling_widget.run_button.loading is False


def test_app_shuts_down_even_if_reporting_the_error_fails(load_app, run_app):
    main = load_app()

    rec = run_app(main, fail_with=RuntimeError("video is broken"), report_fails=True)

    assert rec.stopped == 1


def test_failure_after_conversion_is_reported_and_app_shuts_down(load_app, run_app):
    main = load_app()

    rec = run_app(main, lineage_fails=True)

    assert rec.sample is not None
    assert rec.errors == [(TASK_ID, "ConnectionError('instance is gone')")]
    assert rec.stopped == 1
