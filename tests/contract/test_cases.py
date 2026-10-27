"""Runs the app (uvicorn src.main:app, as the platform does) on every case in cases/ against a real instance.

Opt-in: SLY_CONTRACT_TESTS=1 and credentials in ~/supervisely.env (SERVER_ADDRESS, API_TOKEN). The source
project of each case must live in SLY_CONTRACT_WORKSPACE_ID (default 733, the dev sandbox): the app always
creates its "<source>(images)" project next to the source. The source is only read; nothing is deleted.

    SLY_CONTRACT_TESTS=1 pytest -m contract tests/contract
"""

import glob
import json
import os
import socket
import subprocess
import sys

import pytest
import supervisely as sly
from dotenv import dotenv_values, load_dotenv

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CASES = sorted(glob.glob(os.path.join(ROOT, "cases", "*.env")))

pytestmark = [
    pytest.mark.contract,
    pytest.mark.skipif(os.getenv("SLY_CONTRACT_TESTS") != "1", reason="contract tests are opt-in"),
]


@pytest.fixture(scope="module")
def api():
    load_dotenv(os.path.expanduser("~/supervisely.env"))
    return sly.Api.from_env()


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _paths(api, project_id):
    datasets = {ds.id: ds for ds in api.dataset.get_list(project_id, recursive=True)}

    def path(ds):
        return (path(datasets[ds.parent_id]) + "/" if ds.parent_id else "") + ds.name

    return {ds_id: path(ds) for ds_id, ds in datasets.items()}, datasets


def expected_output(api, case):
    """{dataset path: {image name: number of labels}} the app should produce for this case."""
    state = {k.removeprefix("modal.state."): v for k, v in case.items()}
    project_id = int(case["PROJECT_ID"])
    meta = sly.ProjectMeta.from_json(api.project.get_meta(project_id))
    step = int(state["framesStep"]) if state["sampleResultFrames"].lower() == "true" else 1
    nested = (state.get("includeNestedDatasets") or "false").lower() == "true"
    copy_anns = state["copyAnnotations"].lower() == "true"
    paths, datasets = _paths(api, project_id)
    selected = json.loads(state["selectedDatasets"].replace("'", '"'))
    if state["allDatasets"].lower() == "true" or not selected:
        roots = [ds for ds in datasets.values() if ds.parent_id is None]
    else:  # by name, top-level first (the cases select top-level datasets)
        roots = [next(ds for ds in datasets.values() if ds.name == name and ds.parent_id is None) for name in selected]
    processed = list(roots)
    if nested:
        queue = list(roots)
        while queue:
            children = [ds for ds in datasets.values() if ds.parent_id == queue.pop().id]
            processed += children
            queue += children
    expected = {}
    for ds in processed:
        expected[paths[ds.id]] = {}
        for video in api.video.get_list(ds.id):
            ann = sly.VideoAnnotation.from_json(api.video.annotation.download(video.id), meta, sly.KeyIdMap())
            figures = {frame.index: len(frame.figures) for frame in ann.frames}
            indices = list(range(video.frames_count))
            if state["Options"] == "annotated":
                indices = [i for i in indices if figures.get(i)]
            digits = len(str(video.frames_count))
            expected[f"{paths[ds.id]}/{video.name}"] = {
                f"{video.name}_frame_{str(i).zfill(digits)}.png": figures.get(i, 0) if copy_anns else 0
                for i in indices[::step]
            }
    return expected


def actual_output(api, project_id):
    paths, _ = _paths(api, project_id)
    result = {}
    for ds_id, path in paths.items():
        images = api.image.get_list(ds_id)
        anns = {a.image_id: a.annotation for a in api.annotation.download_batch(ds_id, [i.id for i in images])}
        result[path] = {i.name: len(anns[i.id]["objects"]) for i in images}
    return result


@pytest.mark.parametrize("case_path", CASES, ids=os.path.basename)
def test_case(case_path, api, tmp_path):
    case = dotenv_values(case_path)
    workspace_id = int(os.getenv("SLY_CONTRACT_WORKSPACE_ID", "733"))
    source = api.project.get_info_by_id(int(case["PROJECT_ID"]))
    assert source.workspace_id == workspace_id, "the app writes next to its source: keep sources in the sandbox"
    before = {p.id for p in api.project.get_list(workspace_id)}

    env = {k: v for k, v in os.environ.items() if not k.startswith("modal.state.")}
    env.pop("ENV", None)
    env.update({k: v for k, v in case.items() if v is not None})
    port = str(_free_port())
    cmd = [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", port]
    proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=1800)
    (tmp_path / "app.log").write_text(proc.stdout + proc.stderr)
    assert proc.returncode == 0, proc.stderr[-3000:]

    created = [
        p
        for p in api.project.get_list(workspace_id)
        if p.id not in before and p.name.startswith(f"{source.name}(images)")
    ]
    assert len(created) == 1, created
    result = created[0]
    assert result.type == str(sly.ProjectType.IMAGES)
    assert result.custom_data == {
        "is_sample": True,
        "video_project_id": source.id,
        "video_project_name": source.name,
    }
    src_meta = sly.ProjectMeta.from_json(api.project.get_meta(source.id))
    new_meta = sly.ProjectMeta.from_json(api.project.get_meta(result.id))
    assert {c.name for c in src_meta.obj_classes} <= {c.name for c in new_meta.obj_classes}
    assert actual_output(api, result.id) == expected_output(api, case)
