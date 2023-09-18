"""Configuration file for the Sphinx documentation builder."""
import os
import pathlib
import sys
from importlib import metadata
from unittest.mock import MagicMock

import pydantic


# Add repo root to path for autodoc

sys.path.insert(0, os.path.abspath(".."))

# Patch Pulumi so that importing constants.py doesn't cause errors


pydantic.BaseSettings = MagicMock()

# General configuration

project = "rctab-functions"
author = "The Alan Turing Institute's Research Computing Team"
copyright = f"2023, {author}"

version = "n/a"
release = version

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- Options for HTML output -------------------------------------------------

html_theme = "alabaster"
html_static_path = ["_static"]

# -- General configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
]

# -- Options for HTML output

html_theme = "sphinx_rtd_theme"
