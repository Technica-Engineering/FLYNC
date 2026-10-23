# Minimal makefile for Sphinx documentation
#

# You can set these variables from the command line, and also
# from the environment for the first two.
# -W turns Sphinx warnings into build errors so a broken :ref:/:class: cannot reach the
# published docs unnoticed; --keep-going still reports every warning in one run.
# Override with `SPHINXOPTS= make html` to build a work-in-progress tree anyway.
SPHINXOPTS    ?= -W --keep-going
SPHINXBUILD   ?= uv run python -m sphinx.cmd.build
SOURCEDIR     = source
BUILDDIR      = build
EXAMPLE_NAME  = flync_example
EXAMPLE_NAME2 = flync_example_experimental
EXAMPLE_SOURCE= ../examples/
EXAMPLE_DST	  = ./source/_static/

# Put it first so that "make" without argument is like "make help".
help:
	@$(SPHINXBUILD) -M help "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

.PHONY: help Makefile

generations:
	uv run python3 ./source/_scripts/create_mermaid.py
	uv run python3 ./source/_scripts/generate_ecu_diagram.py $(EXAMPLE_SOURCE)/ecu_variants -o $(EXAMPLE_DST)/images/ecu_variants
	uv run python3 ./source/_scripts/generate_multidrop_segment_diagram.py $(EXAMPLE_SOURCE)/$(EXAMPLE_NAME)
	uv run typer flync_cli.main utils docs --name flync --title Usage --output $(SOURCEDIR)/flync_cli/usage.md
	uv run python3 ../src/flync_cli/main.py errors generate-catalog

clear:
	echo "removing temporary files"
	rm -r $(EXAMPLE_DST)/mermaid
	rm -r $(EXAMPLE_DST)/images/ecu_variants
	rm -r $(EXAMPLE_DST)$(EXAMPLE_NAME)
	rm -r $(EXAMPLE_DST)$(EXAMPLE_NAME2)
	rm $(SOURCEDIR)/flync_cli/usage.md

clean:
	rm -rf $(BUILDDIR)

html_gen: generations
	cp -a $(EXAMPLE_SOURCE)$(EXAMPLE_NAME) $(EXAMPLE_DST)
	cp -a $(EXAMPLE_SOURCE)$(EXAMPLE_NAME2) $(EXAMPLE_DST)
	@$(SPHINXBUILD) -M html "$(SOURCEDIR)" "$(BUILDDIR)" $(SPHINXOPTS) $(O)

html: html_gen clear
