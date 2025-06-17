import threading
from supervisely.app.widgets import Sampling
import supervisely as sly
import src.globals as g
import src.workflow as wf


sampling_widget = Sampling(
    g.project_id,
)


def _init_options():
    sampling_widget.step = g.frames_step
    sampling_widget.only_annotated = g.only_annotated
    sampling_widget.include_nested_datasets = g.include_nested_datasets
    sampling_widget.resize = g.resize
    if g.all_datasets:
        sampling_widget.selected_all_datasets = True
    else:
        sampling_widget.selected_datasets_ids = g.selected_datasets_ids
    if g.output_project_id:
        sampling_widget.selected_output_project_id = g.output_project_id


def run_sampling():
    Sampling.run(sampling_widget)
    wf.workflow_input(g.api, sampling_widget.selected_project_id)
    wf.workflow_output(g.api, sampling_widget.selected_project_id)


def run_and_finish_app():
    try:
        run_sampling()
    except Exception as e:
        g.api.task.update_status(g.task_id, g.api.task.Status.ERROR)
    finally:
        app.shutdown()


sampling_widget.run = run_sampling
_init_options()

app = sly.Application(sampling_widget)

if g.run:
    threading.Thread(target=run_and_finish_app, daemon=True).start()
