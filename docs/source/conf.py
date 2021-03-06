# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys

module_path = os.path.join(os.path.dirname(__file__), '../..')
sys.path.insert(0, os.path.abspath(module_path))

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]
source_suffix = [".rst", ".ipynb"]

master_doc = "index"



# the following are borrowed from scvelo
# -- Retrieve notebooks ------------------------------------------------

from urllib.request import urlretrieve

notebooks_url = "https://github.com/aristoteleo/dynamo-tutorials/raw/master/"
notebooks = [
    "Introduction.ipynb",
    "zebrafish.ipynb",
    "dentategyrus_subset_scvelo.ipynb",
    "pancreatic_endocrinogenesis.ipynb",
    "scNT_seq_readthedocs.ipynb",
    "scEU_seq_rpe1_analysis_kinetic.ipynb",
    "scEU_seq_organoid_analysis_kinetic.ipynb",
]
for nb in notebooks:
    try:
        urlretrieve(notebooks_url + nb, nb)
    except:
        pass


# Add notebooks prolog to Google Colab and nbviewer
nbsphinx_prolog = r"""
{% set docname = 'github/aristoteleo/dynamo-tutorials/blob/master/' + env.doc2path(env.docname, base=None) %}
.. raw:: html

    <div class="note">
      <a href="https://colab.research.google.com/{{ docname|e }}" target="_parent">
      <img src="https://colab.research.google.com/assets/colab-badge.svg" alt="Open In Colab"/></a>
      <a href="https://nbviewer.jupyter.org/{{ docname|e }}" target="_parent">
      <img src="https://github.com/aristoteleo/dynamo-release/raw/master/docs/source/_static/nbviewer-badge.svg" alt="Open In nbviewer"/></a>
    </div>
"""

# -- Project information -----------------------------------------------------

project = "dynamo"
copyright = "2020, Xiaojie Qiu, Yan Zhang"
author = "Xiaojie Qiu, Yan Zhang"

# The full version, including alpha/beta/rc tags
release = "0.95.2"

# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
needs_sphinx = "1.7"

extensions = [
    "nbsphinx",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx.ext.napoleon",
    "sphinx.ext.intersphinx", # Link to other project's documentation (see mapping below)
    'sphinx.ext.viewcode',  # Add a link to the Python source code for classes, functions etc.
    "sphinx.ext.githubpages",
    'sphinx.ext.autosectionlabel',
    "sphinx_autodoc_typehints",  # Automatically document param types (less noise in class signature)
]

# Mappings for sphinx.ext.intersphinx. Projects have to have Sphinx-generated doc! (.inv file)
intersphinx_mapping = {
    "python": ("https://docs.python.org/3/", None),
}


# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []

# Generate the API documentation when building
autosummary_generate = True
autodoc_member_order = 'bysource'
autoclass_content = "both"  # Add __init__ doc (ie. params) to class summaries
html_show_sourcelink = True  # Remove 'view source code' from top of page (for html, not python)
autodoc_inherit_docstrings = True  # If no class summary, inherit base class summary

autodoc_default_flags = [
    # Make sure that any autodoc declarations show the right members
    "members",
    "inherited-members",
    "private-members",
    "show-inheritance",
]
# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = "sphinx_rtd_theme"
html_theme_options = dict(navigation_depth=2)
html_context = dict(
    display_github=True,  # Integrate GitHub
    github_user="aristoteleo",  # organization
    github_repo="dynamo",  # Repo name
    github_version="master",  # Version
    conf_py_path="/docs/source/",
)

def setup(app):
    app.add_css_file("custom.css")

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

sphinx_enable_epub_build=False
sphinx_enable_pdf_build=False
