"""Sphinx configuration for the PokemonGo documentation."""

from __future__ import annotations

from importlib.metadata import version as _version

project = "PokemonGo"
author = "David Guerra"
copyright = "2026, David Guerra"

release = _version("PokemonGo")
version = ".".join(release.split(".")[:2])

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx.ext.doctest",
    "sphinx_autodoc_typehints",
    "myst_parser",
]

# numpy-style docstrings only
napoleon_google_docstring = False
napoleon_numpy_docstring = True

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_type_aliases = {"Image": "PokemonGo.vision.preprocess.Image"}
nitpicky = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

html_theme = "furo"
templates_path = ["_templates"]
exclude_patterns = ["_build"]
