# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import importlib.metadata

from packaging.version import Version

project = "FLYNC"
copyright = "2026, Technica Engineering GmbH"
author = "Iago Alvarez"

# Read the version from the installed distribution rather than hardcoding it, so a
# release never requires editing the docs. The version itself comes from git tags via
# uv-dynamic-versioning, so this tracks whatever is actually being documented.
try:
    release = importlib.metadata.version("flync")
except importlib.metadata.PackageNotFoundError:
    release = "0.0.0"

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration


extensions = [
    "sphinx.ext.duration",
    "sphinx.ext.doctest",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.autosummary",
    "sphinx_copybutton",
    "myst_parser",
    "sphinx_design",
    "sphinxcontrib.mermaid",
    "sphinx_needs",
]

templates_path = ["_templates"]
exclude_patterns = []
python_use_unqualified_type_names = True  # Helps Sphinx resolve local types without full paths


# -- Options for HTML output -------------------------------------------------

add_module_names = False  # Omit module names in class signatures (optional)
html_static_path = ["_static"]
html_theme = "furo"
html_theme_options = {
    "light_logo": "images/flync_light_mode.svg",
    "dark_logo": "images/flync_dark_mode.svg",
    "sidebar_hide_name": True,
    "dark_css_variables": {
        "font-stack": "Open Sans, Helvetica, Arial, sans-serif",
        "font-stack--monospace": "Fira Code, Menlo, monospace",
        "color-brand-primary": "#8EFFAA",
        "color-brand-content": "#8EFFAA",
    },
    "light_css_variables": {
        "font-stack": "Open Sans, Helvetica, Arial, sans-serif",
        "font-stack--monospace": "Fira Code, Menlo, monospace",
        "color-brand-primary": "#287C5F",
        "color-brand-content": "#287C5F",
    },
}
html_title = "FLYNC Documentation"
html_favicon = "_static/images/flync_logo_darker.svg"  # or favicon.png
html_css_files = [
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap",
]


# -- Sphinx Needs settings ---------------------------------------------

needs_types = [
    {
        "directive": "err",
        "title": "Error",
        "prefix": "FLYNC-",
        "color": "#7BBEA5",
    },
]

needs_id_regex = "^[A-Z0-9_-]+$"
needs_fields = {
    "module": {"nullable": True},
    "severity": {"nullable": True},
    "category": {"nullable": True},
    "number": {"nullable": True},
    "location": {"nullable": True},
}


# -- Autodoc settings  -------------------------------------------------

autosummary_generate = True
autodoc_typehints = "signature"  # Forces types to appear in signatures (may help with resolving)
autodoc_typehints_format = "short"  # Shortens paths (e.g., `phy.BASET1` instead of full module path)
autodoc_default_options = {
    "show-inheritance": True,
    "member-order": "bysource",
}
autodoc_pydantic_field_doc_policy = "description"
autodoc_templates = "_templates/autodoc"


mermaid_params = [
    "--theme",
    "forest",
    "--width",
    "600",
    "--backgroundColor",
    "transparent",
]
mermaid_verbose = True
mermaid_d3_zoom = True


#: Placeholder expanded to the current FLYNC version anywhere in the documentation
#: sources. Sphinx already provides ``|release|``, but docutils substitutions are not
#: expanded inside ``.. code-block::``, and the sample YAML files in the SDK reference
#: need a real version number while keeping their syntax highlighting. Replacing the
#: token in the raw source before parsing works in every context, prose included.
VERSION_PLACEHOLDER = "|flync_version|"

#: The release portion of :data:`release` only. Docs built from an untagged commit get a
#: development version such as ``0.13.0.post66+5d920655``; sample configuration files
#: should show what a user of a released FLYNC would actually find on disk.
flync_version = Version(release).base_version


def _expand_version_placeholder(app, docname, source):
    """Substitute :data:`VERSION_PLACEHOLDER` in a source file before it is parsed."""
    source[0] = source[0].replace(VERSION_PLACEHOLDER, flync_version)


def setup(app):
    app.add_css_file("custom.css")
    app.connect("source-read", _expand_version_placeholder)
