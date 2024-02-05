#!/bin/bash
#
# Run all code style checks and Python unit tests

# Keep track of the exit code of each test
status=0

# Activate our virtual environment
# shellcheck disable=SC1091
source .venv/bin/activate

# Check Python coding style with flake8, using black's default max line length
# To auto-format a file, you can run `python -m black filename.py`
echo "Running flake8..."
python -m flake8 --max-line-length=88 --exclude=.venv
status=$((status+$?))

# Run here rather than as a pre-commit hook so that local imports happen last
echo "Running isort..."
isort . --profile=black
status=$((status+$?))

# Find all .py files (ignoring .venv) and check their code style with pylint,
# using (something close to) Google's default config
echo "Running pylint..."
# shellcheck disable=SC2038
find . -type f -name "*.py" ! -path "./.venv/*" | xargs \
    pylint --rcfile=tests/pylintrc
status=$((status+$?))

# Run our unit tests with code coverage
echo "Running unit tests..."
# shellcheck disable=SC2140
python -m coverage run --omit=".venv/*","tests/*" -m unittest discover --start-directory=tests/
status=$((status+$?))

# Show the lines our tests miss
python -m coverage report --show-missing
status=$((status+$?))

# Check types with MyPy
echo "Running type checking..."
python -m mypy --config-file tests/mypy.ini status/ tests/
status=$((status+$?))

# [optional] Check Markdown coding style with Ruby's markdown lint
# https://github.com/markdownlint/markdownlint
if ! command -v mdl &> /dev/null
then
  echo "Skipping markdown lint..."
else
  echo "Running markdown lint..."
  # With --git-recurse, mdl only checks version controlled files
  mdl --git-recurse --style tests/mdl_style.rb ./
  status=$((status+$?))
fi

# [optional] Check Bash coding style with shellcheck
# https://github.com/koalaman/shellcheck
if ! command -v shellcheck &> /dev/null
then
  echo "Skipping shellcheck..."
else
  echo "Running shellcheck..."
  shellcheck ./*.sh
  status=$((status+$?))
fi

echo ""
RED='\033[0;31m'
GREEN='\033[0;32m'
if [ $status -eq 0 ]
then
  echo -e "${GREEN}All tests passed"
  exit 0
else
  echo -e "${RED}Not all tests passed" >&2
  exit 1
fi
