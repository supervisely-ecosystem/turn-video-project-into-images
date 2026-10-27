import threading

import supervisely as sly
from supervisely.app.widgets import Sampling

import src.globals as g
import src.workflow as wf

sampling_widget = Sampling(
    g.project_id,
    copy_annotations=g.copy_annotations,
)


def _init_options():
    sampling_widget.step = g.frames_step
    sampling_widget.only_annotated = g.only_annotated
    sampling_widget.include_nested_datasets = g.include_nested_datasets
    if g.all_datasets:
        sampling_widget.selected_all_datasets = True
    else:
        # ids first: unchecking "all datasets" refreshes the widget from the current selection
        sampling_widget.selected_datasets_ids = g.selected_datasets_ids
        sampling_widget.selected_all_datasets = False


def _result_project_id():
    # Sampling.run() does not return the project it created; it only shows it in result_project_preview
    return sampling_widget.result_project_preview.get_json_data()["id"]


def _report_error(exc: Exception):
    sly.logger.error(f"Failed to convert the videos project: {exc!r}", exc_info=True)
    if g.task_id is None:
        return
    description = repr(exc)
    if len(description) > 255:
        description = description[:252] + "..."
    try:
        g.api.task.set_output_error(g.task_id, "Failed to convert the videos project", description)
    except Exception:  # noqa: BLE001 - the task must still shut down
        sly.logger.warning("Failed to set the task output error", exc_info=True)


def _run():
    sampling_widget.run_button.loading = True
    try:
        Sampling.run(sampling_widget)
        wf.workflow_input(g.api, sampling_widget.selected_project_id)
        result_project_id = _result_project_id()
        if result_project_id is None:
            sly.logger.warning("Result project is unknown, workflow output is not set")
        else:
            wf.workflow_output(g.api, result_project_id)
    except Exception as e:  # noqa: BLE001 - reported to the task output, then the app shuts down
        _report_error(e)
    finally:
        try:
            sampling_widget.run_button.loading = False
        finally:
            app.shutdown()


sampling_widget.run = _run
_init_options()

app = sly.Application(sampling_widget)

if g.run:
    threading.Thread(target=sampling_widget.run, daemon=True).start()
