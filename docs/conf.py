"""Configuration file for the Sphinx documentation builder."""
import os
import pathlib
import sys
from importlib import metadata
from unittest.mock import MagicMock

import sphinx_rtd_theme
import pydantic


# Patch Pydantic so that missing doen't cause errors

pydantic.BaseSettings = MagicMock()

# General configuration

project = "rctab-functions"
author = "The Alan Turing Institute's Research Computing Team"
copyright = f"2023, {author}"

version = "n/a"
release = version

templates_path = ["_templates"]
exclude_patterns = ["venv", "_build", "Thumbs.db", ".DS_Store"]

# -- General configuration

extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
]

# -- Options for HTML output

html_theme = "sphinx_rtd_theme"
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
html_static_path = ["_static"]

html_logo = "RCTab-hex.png"


def setup(app):
    """Tasks to perform during app setup."""
    app.add_css_file("css/custom.css")


# -- Options for autosummary extension

autosummary_generate = True
