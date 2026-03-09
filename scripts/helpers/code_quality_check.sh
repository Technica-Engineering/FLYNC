#! bin/bash
# This file contains all checkers that are used in pipelines.
# Use locally to run all checkers at once, e.g., before pushing code to the repository.
# Usage: bash local_checkers.sh

poetry run isort --check --diff --color --line-length 79 src
poetry run flake8 src
poetry run black --check --diff --color src
poetry run mypy src --show-error-codes --pretty --install-types --non-interactive