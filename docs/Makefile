# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
SPHINXOPTS    ?=
SPHINXBUILD   ?= poetry run python -m sphinx.cmd.build
SOURCEDIR     = source
BUILDDIR      = build/html
EXAMPLE_NAME  = flync_example
EXAMPLE_SOURCE= ../examples/
EXAMPLE_DST	  = ./source/_static/

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

generate_pictures:
# create mermaid schematics
	poetry run python3 ./source/_scripts/create_mermaid.py
	poetry run python3 ./source/_scripts/generate_ecu_diagram.py $(EXAMPLE_SOURCE)/ecu_variants -o $(EXAMPLE_DST)/images/ecu_variants


html: generate_pictures
# copy flync_example for yaml references during runtime of docs build
	cp -a $(EXAMPLE_SOURCE)$(EXAMPLE_NAME) $(EXAMPLE_DST)
# build html docs
	@$(SPHINXBUILD) -b html "$(SOURCEDIR)" "$(BUILDDIR)"
# remove flync_example again
	rm -r $(EXAMPLE_DST)$(EXAMPLE_NAME)
# remove mermaid files again
	rm -r $(EXAMPLE_DST)/mermaid