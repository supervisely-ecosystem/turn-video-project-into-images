import json
import os

import supervisely as sly
from dotenv import load_dotenv

from src.utils import strtobool

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

# region envvars
team_id = sly.env.team_id()
workspace_id = sly.env.workspace_id()
project_id = sly.env.project_id()
task_id = sly.env.task_id(raise_not_found=False)
if sly.is_development():
    sly.logger.warning("Development mode, will set task_id to 0 to avoid errors")
    # task_id = 0

# endregion
sly.logger.info(f"Api initialized. Team: {team_id}. Workspace: {workspace_id}. Project: {project_id}")

api = sly.Api.from_env()

# region modalvars
sample_result_frames = strtobool(os.getenv("modal.state.sampleResultFrames"))
if sample_result_frames:
    frames_step = int(os.environ["modal.state.framesStep"])
else:
    frames_step = 1

options = os.environ["modal.state.Options"]
if options == "annotated":
    only_annotated = True
else:
    only_annotated = False

selected_datasets = json.loads(os.environ["modal.state.selectedDatasets"].replace("'", '"'))
selected_datasets_ids = []
for dataset_name in selected_datasets:
    dataset = api.dataset.get_info_by_name(project_id, dataset_name)
    selected_datasets_ids.append(dataset.id)
all_datasets = os.getenv("modal.state.allDatasets").lower() in ("true", "1", "t")
include_nested_datasets = (os.getenv("modal.state.includeNestedDatasets") or "false").lower() in (
    "true",
    "1",
    "t",
)

run = os.getenv("modal.state.run", "false").lower() in ("true", "1", "t")

# endregion
sly.logger.info(
    f"Sample result frames: {sample_result_frames}. Frames step: {frames_step}. "
    f"Options: {options}. Selected datasets: {selected_datasets}. "
    f"All datasets: {all_datasets}. Include nested datasets: {include_nested_datasets}."
)

project = api.project.get_info_by_id(project_id)
sly.logger.info(f"Working with project {project.name}...")
if project is None:
    raise RuntimeError(f"Project {project.name!r} not found")
if project.type != str(sly.ProjectType.VIDEOS):
    raise TypeError(f"Project type is {project.type!r}, but have to be {sly.ProjectType.VIDEOS!r}")

meta_json = api.project.get_meta(project.id)
meta = sly.ProjectMeta.from_json(meta_json)
sly.logger.info("Project meta received...")
if options == "annotated" and len(meta.obj_classes) == 0 and len(meta.tag_metas) == 0:
    raise ValueError(f"Nothing to convert, there are no tags and classes in project {project.name!r}")

copy_annotations = os.getenv("modal.state.copyAnnotations", "true").lower() in ("true", "1", "t")
