# Modernization notes: turn-video-project-into-images

Mechanical move to the hardened image (`sly-app-standard` §1), not a rewrite. Base: `origin/master` @ bcb0f13
(= published v3.0.7). Branch `local/modernize`, nothing committed.

## Behaviour contract (kept)

Context menu of a videos project → "Videos project to images project". Headless task (`headless: true`) that
still starts a uvicorn server (`uvicorn src.main:app`) hosting the SDK `Sampling` widget; with `run=true` it runs
at once in a thread and shuts the session down when done. All work is the SDK's `sample_video_project`.

| `modal.state` | Default | Meaning |
|---|---|---|
| `Options` | `all` | `annotated` = only frames with figures (fails at start if the project has no classes and no tags) |
| `sampleResultFrames` / `framesStep` | `false` / `10` | take every N-th of those frames |
| `allDatasets`, `selectedDatasets` (names), `includeNestedDatasets` | `true`, `[]`, unset (= false) | see known issue 1 |
| `copyAnnotations` | `true` | frame figures → image labels (+ `object_id`/auto-track tags), video tags in range → image tags |
| `run` | `true` | false = only build the widget, nothing runs (session stays open) |

Output: new images project `<source>(images)` (`_001`… on conflict) **in the source project's workspace**,
custom data `{is_sample, video_project_id, video_project_name}`; dataset tree = source datasets, each with one
child dataset per video; images `<video>_frame_<index zero-padded>.png`. Workflow lineage: source project as
input and (known issue 2) as output.

## Changes

1. `docker_image`: `supervisely/data-operations:6.74.34` (shared legacy image, Python 3.8) →
   `supervisely/base-py-sdk-hardened:6.74.34` (Python 3.14). SDK stays 6.74.34, `min_instance_version` 6.17.22
   (CI range for it: [6.74.29, 6.74.35)).
2. `distutils.util.strtobool` (removed in Python 3.12, the app could not start on the new image) →
   `src/utils.py:strtobool` with the same accepted values and the same `ValueError`.
3. `ruff` (target py314) fixes only: unused imports, import order, f-strings, formatting.
4. Added: `pyproject.toml` (ruff/pytest config), `tests/unit` (offline), `tests/contract` (opt-in), `cases/*.env`;
   `local.env` now points at the sandbox fixture (`cases/annotated-step5-selected.env`).

## Image decision

Bare hardened image, no per-app image. `data-operations` adds `decord`, `moviepy`, `imageio-ffmpeg`, `imutils`,
`pyzbar`/`libzbar0`; the app imports none of them. The only one reached is `decord`: the SDK's
`VideoFrameReader` uses it when installed and falls back to OpenCV otherwise. Checked that the fallback gives
the same pixels: frames decoded by the old image (decord, Py 3.8) and the hardened image (OpenCV 4.14, Py 3.14)
are byte-identical for both reference videos (h264 1080p and 4K) at steps 1/10/25/60 and sparse seeks.
`decord==0.6.0` does import on the hardened image, so if a codec ever decodes differently the per-app template
path with `decord` in `dev_requirements.txt` is the fallback. CI: this repo has no `build-image` job
(`release.yml` only calls `common.yml`), so nothing builds an unused per-app image.

## Known issues kept (found while verifying, not fixed: out of scope for a mechanical move)

1. **Dataset selection is ignored.** `main._init_options` sets `selected_datasets_ids` but never unchecks the
   widget's "all datasets" box, so every top-level dataset is processed. Confirmed with the published v3.0.7
   (case `selected-one-of-two-datasets`: `dsB` converted too). `includeNestedDatasets` does work.
2. **Workflow output is the source project**, not the new one (`wf.workflow_output(api, selected_project_id)`).
3. `if project is None` check comes after `project.name` (dead check). `batchSize` is unused.

## Verification (2026-10-25, dev.internal.supervisely.com, instance 6.18.7)

- **Unit tests** 27 passed on Python 3.14 (venv) and inside `supervisely/base-py-sdk-hardened:6.74.34`
  (3.14.7, amd64). `ruff check` / `ruff format --check` clean.
- **Old vs new, same output.** Published v3.0.7 (`fleet.py run`, tasks 62701/62702/62714/62724) vs new code in the
  hardened image with `ENV=production` on a debug task (62716, port 8012). Compared per dataset path and image name:
  image hash (pixel-identical PNGs), size, image meta, labels (bitmaps compared decoded), tags, project meta and
  custom data — **identical** for all four cases:
  `all-frames-step10-nested` (9416 vs 9449, 83 images, 90 labels), `annotated-step5-selected` (9421 vs 9439,
  106/126), `no-annotations-selected-with-nested` (9437 vs 9453, 34/0), `selected-one-of-two-datasets`
  (9500 vs 9507, 21/3). Encoded bitmap strings differ (newer zlib/PNG encoder), masks are equal.
- **Contract tests** `SLY_CONTRACT_TESTS=1 pytest -m contract tests/contract` (local, Python 3.14, dev mode):
  4 passed — every case's output tree, image names and label counts match what the source videos imply.
- Final code (after ruff) re-run in the image with `ENV=production` (debug task 62716): `selected-one-of-two-datasets`
  → 9542, identical to the published version's 9500; no errors in the log.
- Not verified: platform setting the task output to the new project. Published runs show it (set by the platform
  for app tasks, not by app code); a debug task does not get it. Same code path, so expected unchanged.

## Objects created on dev (none deleted)

- Fixtures (workspace 733): videos projects 9409 "tvpi-src Videos example" (copy of #143 + nested dataset; video
  tags with a frame range longer than 10 frames were dropped from the sea lion video, the platform now rejects
  them) and 9491 "tvpi-src two datasets" (videos from #7894).
- Outputs (workspace 733): 9416, 9421, 9437, 9500 (old); 9439, 9449, 9453, 9507 (new); 9542 (final production run);
  contract tests 9522, 9528, 9535, 9537.
- Tasks: 62701, 62702, 62714, 62724 (old app); debug task 62716.
