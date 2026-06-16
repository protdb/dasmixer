.PHONY: dev-install dev-uninstall help

help:
	@echo "DASMixer Development Makefile"
	@echo ""
	@echo "Targets:"
	@echo "  dev-install    Install all packages in editable mode"
	@echo "  dev-uninstall  Uninstall all DASMixer packages"

dev-install:
	pip install -e "dasmixer-core[all]"
	pip install -e "dasmixer-gui"
	pip install -e "dasmixer-cli"
	pip install -e "metapackage"
	@echo ""
	@echo "All packages installed. Run 'dasmixer' or 'dasmixer-cli --help' to test."

dev-uninstall:
	pip uninstall -y dasmixer-core dasmixer-gui dasmixer-cli dasmixer
	@echo "Done."