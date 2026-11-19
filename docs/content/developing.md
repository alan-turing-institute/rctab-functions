# Developing

This page covers how to run the checks and tests and the coding conventions
that the three function apps follow.
See [Setup](setup.md) for how to install dependencies and run a function app
locally, and [Releasing](releasing.md) for how code gets from `main` to Azure.

## Layout

Each function app is an independent Poetry project with its own
`pyproject.toml`, `poetry.lock`, `.venv/` (Poetry is configured with
`virtualenvs.in-project = true`), `tests/` directory and `run_tests.sh`.
There is no shared top-level Python package, so a change to, say,
`usage_function/utils/` does not affect the other two apps.

The `docs/` directory is a fourth Poetry project.
It depends on all three function apps by path, since Sphinx `autodoc` needs to
import them to build the docstring pages.

## Running the checks

From inside a function app's directory:

```bash
poetry install
./run_tests.sh
```

`run_tests.sh` activates `.venv`, then runs:

* Python linting, with isort and pylint.
* Unit tests, collecting test coverage stats.
* Type checking, with mypy.
* Misc linting, of e.g. mark-down files and shell scripts, but only if those linters are installed.

The script accumulates exit codes, so it reports failures from every stage
rather than stopping at the first one.

Separately, `pre-commit` runs `black`, `pydocstyle` (Google convention),
`pymarkdown`, `gitleaks` and a handful of whitespace/YAML/JSON hooks across
the whole repo:

```bash
pre-commit install   # once
pre-commit run --all-files
```

## Continuous integration

GitHub Actions mirrors the above:

* `linting_usage.yml`, `linting_status.yml` and `linting_controller.yml` each
  run `poetry check --lock`, `poetry install` and `poetry run ./run_tests.sh`
  for one app, on pushes to any branch except `main`, and only when that app's
  directory (or `.github/workflows/`) has changed.
* `pre-commit_checks.yml` runs the pre-commit hooks.
* `gitleaks.yml` scans the full history for secrets.
* `test_build.yml` builds each app's Docker image on pull requests and pushes
  to `main`, to check the images can still be built.

## Coding conventions

* Python 3.13 (`python = "^3.13"` in each `pyproject.toml`); use `pyenv` to
  match the version used in production.
* Formatting is `black`, enforced by pre-commit; imports are sorted by `isort`
  with `--profile=black`.
* Everything is type annotated. `mypy` runs with `disallow_untyped_defs`, the
  Pydantic plugin and `ignore_missing_imports`.
* Docstrings follow the Google convention and are enforced by `pydocstyle`.
  Note that `pylint`'s own `missing-*-docstring` checks are disabled in
  `tests/pylintrc`, so `pydocstyle` is the check that matters.
* `pylint` must score 10.0 (`fail-under=10.0`). Use targeted
  `# pylint: disable=...` comments where a rule genuinely does not apply.
* Imports are absolute, enforced by the `pylint_absolute_imports` plugin.
* Configuration comes from the environment or a `.env` file, via a
  `pydantic_settings.BaseSettings` subclass in each app's `settings.py`.
  Add new options there with a type, a default where sensible and a comment.
* Logging goes through the standard `logging` module, using old-style `%s`
  formatting (`logging-format-style=old`) and lazy arguments, with
  `add_log_handler_once()` from the app's `logutils.py` attaching the central
  Azure handler.
* Tests live in each app's `tests/` directory, are written with
  `unittest` and are discovered by `unittest discover`, so files need the
  `test_*.py` name and tests need to be `unittest.TestCase` methods.
* Shared models come from the
  [rctab-models](https://github.com/alan-turing-institute/rctab-models)
  package, pinned by git tag in `pyproject.toml`. Prefer adding a model there
  over redefining a payload shape locally.
* Dependency changes go through Poetry so that `poetry.lock` stays consistent;
  CI fails on `poetry check --lock` otherwise.
