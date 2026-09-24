# AGENTS.md

Guidance for AI coding agents working in this repo.

## What this is

Three Azure Function apps that make up the data-collection and enforcement
half of [RCTab](https://rctab.readthedocs.io/), a cloud FinOps package for
Azure. Each app runs on a timer trigger, authenticates to the RCTab API with
an RSA key pair, and talks to it over HTTP:

- `usage_function/` — collects subscription usage and cost data
  (`usage` hourly, `monthly_usage` for the previous month, plus a currently
  disabled `costmanagement` function).
- `status_function/` — collects subscription status data.
- `controller_function/` — asks the API which subscriptions should be on/off and
  tries to enable/disable them.

The API itself lives in
[rctab-api](https://github.com/alan-turing-institute/rctab-api) and the
deployment in the RCTab Infrastructure repository; neither is in this repo.
Shared payload models come from
[rctab-models](https://github.com/alan-turing-institute/rctab-models), pinned
by git tag.

## Layout

Each app is an independent Poetry project — its own `pyproject.toml`,
`poetry.lock`, in-project `.venv/`, `README.md`, `tests/` and `run_tests.sh`.
There is no shared top-level Python package, so `usage_function/utils/` is not
used by the other two apps. `docs/` is a fourth Poetry project that installs
all three by path.

Within an app: `<name>/__init__.py` holds the function entry point,
`function.json` its timer schedule, `settings.py` a `pydantic_settings`
config class, `auth.py` the API authentication, `logutils.py` the logging
setup, and `run_now.py` (or `run_usage.py` etc.) a local runner.

## Working in this repo

- Work inside one function app directory at a time; `cd` there first.
- Install with `poetry install`; the venv is `.venv/` in that directory.
- Run `./run_tests.sh` in that directory after changing it — it runs isort,
  pylint, unit tests with coverage, and mypy.
- Run `pre-commit run --all-files` for repo-wide formatting and lint (black,
  pydocstyle, pymarkdown, gitleaks).
- If you change a dependency, commit the updated `poetry.lock`; CI runs
  `poetry check --lock`.
- Do not change the `version` field in a `pyproject.toml` — it is fixed at
  `0.1.0` and releases are identified by git tag.
- Never commit secrets or a real `.env`; gitleaks runs in pre-commit and CI.
- A change that affects all three apps needs making three times, once per app.

## Docs first

Prefer documenting behaviour in `docs/` over expanding this file:

- [docs/content/setup.md](docs/content/setup.md) — prerequisites, environment
  variables, running an app locally, triggering one on Azure.
- [docs/content/developing.md](docs/content/developing.md) — the full check
  and test story, CI workflows, and coding conventions.
- [docs/content/releasing.md](docs/content/releasing.md) — GitHub releases,
  Docker Hub image tags, and how deployed apps pick up new code.
- [docs/content/usage.rst](docs/content/usage.rst),
  [status.rst](docs/content/status.rst),
  [controller.rst](docs/content/controller.rst) — per-app permissions and
  settings.

## Conventions, in brief

Python 3.13, black formatting, isort with `--profile=black`, full type
annotations checked by mypy (`disallow_untyped_defs`), Google-style docstrings
enforced by pydocstyle, absolute imports, a pylint score of 10.0, `unittest`
tests under `tests/`, and configuration through `pydantic_settings`. See
[docs/content/developing.md](docs/content/developing.md) for the details and
the reasoning.

## Lastly

Remember to update this file and the docs if something changes.
