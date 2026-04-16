# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "FLYNC"
copyright = "2026, Technica Engineering GmbH"
author = "Iago Alvarez"
release = "0.9.0"

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
]

templates_path = ["_templates"]
exclude_patterns = []
python_use_unqualified_type_names = (
    True  # Helps Sphinx resolve local types without full paths
)


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


# -- Autodoc settings  -------------------------------------------------

autosummary_generate = True
autodoc_typehints = "signature"  # Forces types to appear in signatures (may help with resolving)
autodoc_typehints_format = (
    "short"  # Shortens paths (e.g., `phy.BASET1` instead of full module path)
)
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


def setup(app):
    app.add_css_file("custom.css")
