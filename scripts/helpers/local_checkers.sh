#!/bin/bash
# This file contains all checkers that are used in pipelines.
# Use locally to run all checkers at once, e.g., before pushing code to the repository.
# Usage: bash local_checkers.sh

LINE_LENGTH=149


echo "=== isort ==="
poetry run isort --check --diff --color --line-length $LINE_LENGTH src
poetry run isort --check --diff --color --line-length $LINE_LENGTH tests

echo "=== flake8 ==="
poetry run flake8 --max-line-length $LINE_LENGTH src
#poetry run flake8 --max-line-length $LINE_LENGTH tests

echo "=== mypy ==="
poetry run mypy src --show-error-codes --pretty --install-types --non-interactive

echo "=== black ==="
poetry run black --target-version py312 --check --diff --color src
poetry run black --target-version py312 --check --diff --color tests
