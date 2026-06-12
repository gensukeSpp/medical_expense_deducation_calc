# Development notes

This file documents how to run tests and set up the development environment.

## Python and environment
- Recommended Python: 3.11
- Use pyenv to install: `pyenv install 3.11.6` (or latest 3.11.x)
- Create and activate virtualenv:

  python -m venv .venv
  source .venv/bin/activate

- Install dependencies used by this project via uv or pip. Example:

  uv add pytest
  uv add watchdog

## Running tests
- Activate your virtualenv
- Install pytest
- Run pytest from the repo root:

  pytest -q

## Notes for CI
- CI should install Python 3.11, create a virtualenv, install project test deps (pytest), and run pytest.
