import json
import os
from distutils.util import strtobool
from typing import Tuple
import supervisely as sly
from dotenv import load_dotenv
from supervisely.io.fs import mkdir

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

# region constants
AUTOTRACKED_TAG_NAME = "auto-tracked"
# endregion
# region envvars
team_id = sly.env.team_id()
workspace_id = sly.env.workspace_id()
project_id = sly.env.project_id()
task_id = sly.env.task_id(raise_not_found=False)
if sly.is_development():
    sly.logger.warning("Development mode, will set task_id to 0 to avoid errors")
    # task_id = 0

# endregion
sly.logger.info(
    f"Api initialized. Team: {team_id}. Workspace: {workspace_id}. Project: {project_id}"
)

api = sly.Api.from_env()

# region modalvars
sample_result_frames = bool(strtobool(os.getenv("modal.state.sampleResultFrames")))
if sample_result_frames:
    frames_step = int(os.environ["modal.state.framesStep"])
else:
    frames_step = None

options = os.environ["modal.state.Options"]
batch_size = int(os.environ["modal.state.batchSize"])

selected_datasets = json.loads(
    os.environ["modal.state.selectedDatasets"].replace("'", '"')
)

all_datasets = os.getenv("modal.state.allDatasets").lower() in ("true", "1", "t")
if all_datasets or len(selected_datasets) == 0:
    selected_datasets = [dataset.name for dataset in api.dataset.get_list(project_id)]
# endregion
sly.logger.info(
    f"Sample result frames: {sample_result_frames}. Frames step: {frames_step}. "
    f"Options: {options}. Batch size: {batch_size}. Selected datasets: {selected_datasets}. "
    f"All datasets: {all_datasets}"
)

need_download_threshold = 0.15

storage_dir = os.path.join(os.getcwd(), "storage")
mkdir(storage_dir, True)
video_dir = os.path.join(storage_dir, "video")
mkdir(video_dir)
img_dir = os.path.join(storage_dir, "images")
mkdir(img_dir)
sly.logger.debug(
    f"Storage directory: {storage_dir}, video directory: {video_dir}, images directory: {img_dir}"
)

project = api.project.get_info_by_id(project_id)
sly.logger.info(f"Working with project {project.name}...")
if project is None:
    raise RuntimeError("Project {!r} not found".format(project.name))
if project.type != str(sly.ProjectType.VIDEOS):
    raise TypeError(
        "Project type is {!r}, but have to be {!r}".format(
            project.type, sly.ProjectType.VIDEOS
        )
    )

meta_json = api.project.get_meta(project.id)
meta = sly.ProjectMeta.from_json(meta_json)
sly.logger.info("Project meta received...")

if "object_id" not in [tag.name for tag in meta.tag_metas]:
    vobj_id_tag_meta = sly.TagMeta(
        name="object_id",
        value_type=sly.TagValueType.ANY_NUMBER,
        applicable_to=sly.TagApplicableTo.OBJECTS_ONLY,
    )
    meta = meta.add_tag_meta(vobj_id_tag_meta)

if options == "annotated" and len(meta.obj_classes) == 0 and len(meta.tag_metas) == 0:
    raise ValueError(
        "Nothing to convert, there are no tags and classes in project {!r}".format(
            project.name
        )
    )


def add_auto_tag_meta(meta: sly.ProjectMeta) -> Tuple[sly.ProjectMeta, sly.TagMeta]:
    def get_free_tag_name(meta: sly.ProjectMeta, tag_name: str) -> str:
        new_tag_name = tag_name
        i = 1
        while meta.get_tag_meta(new_tag_name) is not None:
            new_tag_name = f"{tag_name}_{i}"
            i += 1
        return new_tag_name

    new_tag_name = get_free_tag_name(meta, AUTOTRACKED_TAG_NAME)
    new_tag_meta = sly.TagMeta(new_tag_name, sly.TagValueType.NONE)
    return meta.add_tag_meta(new_tag_meta), new_tag_meta


meta, autotracked_tag_meta = add_auto_tag_meta(meta)
sly.logger.info("Tag meta for auto-tracked added...")
