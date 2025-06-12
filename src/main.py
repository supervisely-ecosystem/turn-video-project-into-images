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
    if g.all_datasets:
        sampling_widget.selected_all_datasets = True
    else:
        sampling_widget.selected_datasets_ids = g.selected_datasets_ids


def _run():
    Sampling.run(sampling_widget)
    wf.workflow_input(g.api, sampling_widget.selected_project_id)
    wf.workflow_output(g.api, sampling_widget.selected_project_id)


sampling_widget.run = _run
_init_options()

app = sly.Application(sampling_widget)

if g.run:
    sampling_widget.run()
