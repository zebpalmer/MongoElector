# Project: mongoelector
## ===========================================================================
## UV Python Project — Standard Makefile
## Source: https://gist.github.com/zebpalmer/3026294e7d0f0db1e5e643ae94b9aa3d
## Update: `make self-update` to pull the latest version
##
## Project configuration variables (set above this banner or in project.mk):
##   DOCS_TOOL     - Documentation tool: mkdocs, sphinx, or empty (default: empty)
##   SETUP_EXTRAS  - Extra setup steps: uv-self-update, clean-venv (default: empty)
##
## Usage:
##   1. Add your project header above the === banner line:
##        # Project: my-project
##        DOCS_TOOL := mkdocs
##        SETUP_EXTRAS := uv-self-update clean-venv
##   2. Everything below the banner is managed — don't edit it by hand.
##   3. Run `make self-update` to pull the latest version from the gist.
##   4. Use project.mk for additional project-specific targets.
## ===========================================================================

# ---- Gist URL for self-update (override in project.mk if forked) ----
MAKEFILE_GIST_RAW_URL ?= https://gist.githubusercontent.com/zebpalmer/3026294e7d0f0db1e5e643ae94b9aa3d/raw/Makefile.base

SHELL := /bin/bash

# Load project-specific configuration if it exists
-include project.mk

.PHONY: help setup sync install lock upgrade clean all style test format lint lint-check release self-update
.PHONY: check-branch check-dirty check-clean check-sync pre-release post-release push patch minor major prompt-type do-release cleanup-tmp

# Conditionally add docs targets
ifneq ($(DOCS_TOOL),)
.PHONY: docs docs-serve clean-docs
endif

help: ## Show this help message
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

## Setup & Dependencies
setup: ## First-time setup: install UV and dependencies
	@command -v uv >/dev/null 2>&1 || { echo "UV not found. Install from: https://docs.astral.sh/uv/getting-started/installation/"; exit 1; }
ifneq ($(filter uv-self-update,$(SETUP_EXTRAS)),)
	@echo "Checking for UV updates"
	@uv self update
	@uv --version
endif
ifneq ($(filter clean-venv,$(SETUP_EXTRAS)),)
	@echo "Removing old virtual environments if any..."
	@rm -rf .venv/
endif
	@echo "Installing dependencies..."
	uv sync --all-extras --all-groups
	@echo "Setup complete! Run 'make test' to verify."

sync: ## Sync dependencies from lock file
	uv sync --all-extras --all-groups

install: sync ## Alias for sync (for muscle memory)

lock: ## Update lock file from pyproject.toml
	uv lock

upgrade: ## Upgrade all dependencies to latest compatible versions
	uv lock --upgrade
	uv sync --all-extras --all-groups

## Common Tasks
all: sync style test ## Run full local verification (sync, format, lint, test)

style: format lint ## Format and lint code

test: ## Run tests
	uv run pytest tests/

format: ## Format code with ruff
	uv run ruff format .

lint: ## Lint and fix code with ruff
	uv run ruff check --fix .

lint-check: ## Lint without fixing (for CI)
	uv run ruff check .

## Documentation (conditional on DOCS_TOOL)
ifeq ($(DOCS_TOOL),mkdocs)
docs: clean-docs ## Build documentation with mkdocs
	uv run mkdocs build

docs-serve: clean-docs ## Build and serve docs locally (with auto-reload)
	uv run mkdocs serve

clean-docs: ## Clean documentation build artifacts
	rm -rf site/
endif

ifeq ($(DOCS_TOOL),sphinx)
docs: clean-docs ## Build Sphinx documentation
	cd docs && uv run sphinx-build -b html . _build/html

docs-serve: clean-docs ## Build and serve docs locally (with auto-reload)
	cd docs && uv run sphinx-autobuild -b html . _build/html

clean-docs: ## Clean documentation build artifacts
	rm -rf docs/_build/ docs/_autosummary/
endif

## Maintenance
ifneq ($(DOCS_TOOL),)
clean: clean-docs ## Clean build artifacts and caches
else
clean: ## Clean build artifacts and caches
endif
	rm -rf build/ dist/ *.egg-info .pytest_cache/ .ruff_cache/ .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

## Self-Update (fetches latest Makefile.base from gist, preserves project header)
self-update: ## Update Makefile from upstream gist
	@echo "Fetching latest Makefile.base from gist..."
	@TMPBASE=$$(mktemp) && \
	curl -fsSL "$(MAKEFILE_GIST_RAW_URL)" -o "$$TMPBASE" || { echo "ERROR: Failed to download Makefile.base"; rm -f "$$TMPBASE"; exit 1; }; \
	HEADER=$$(awk '/^## ={5,}/{exit} {print}' Makefile) && \
	{ echo "$$HEADER"; cat "$$TMPBASE"; } > Makefile && \
	rm -f "$$TMPBASE" && \
	echo "Makefile updated. Review with: git diff Makefile"

## Release Management
release: cleanup-tmp check-branch check-dirty prompt-type pre-release do-release post-release cleanup-tmp ## Create a release (interactive or: make release TYPE=patch|minor|major)
	@echo ""
	@echo "================================"
	@echo "Release complete!"
	@echo "================================"

patch: ## Bump patch version (0.0.X)
	@uv run bump-my-version bump patch --dry-run --verbose
	@uv run bump-my-version bump patch

minor: ## Bump minor version (0.X.0)
	@uv run bump-my-version bump minor --dry-run --verbose
	@uv run bump-my-version bump minor

major: ## Bump major version (X.0.0)
	@uv run bump-my-version bump major --dry-run --verbose
	@uv run bump-my-version bump major

######### Internal Helpers (not shown in help) #########

ifneq ($(DOCS_TOOL),)
pre-release: check-branch check-sync style docs check-clean test
else
pre-release: check-branch check-sync style check-clean test
endif

post-release: push

# Prompt for release type if not provided
prompt-type:
	@CURRENT=$$(uv run bump-my-version show current_version 2>/dev/null); \
	V_PATCH=$$(uv run bump-my-version show new_version --increment patch 2>/dev/null); \
	V_MINOR=$$(uv run bump-my-version show new_version --increment minor 2>/dev/null); \
	V_MAJOR=$$(uv run bump-my-version show new_version --increment major 2>/dev/null); \
	if [ -z "$(TYPE)" ]; then \
		echo ""; \
		echo "Current version: $$CURRENT"; \
		echo ""; \
		echo "Select release type:"; \
		echo "  patch  - Bug fixes          -> $$V_PATCH"; \
		echo "  minor  - New features       -> $$V_MINOR"; \
		echo "  major  - Breaking changes   -> $$V_MAJOR"; \
		echo ""; \
		read -p "Enter release type [patch/minor/major]: " choice; \
		case $$choice in \
			patch|minor|major) ;; \
			*) echo "ERROR: Invalid choice '$$choice'. Must be patch, minor, or major."; rm -f .release-type.tmp; exit 1 ;; \
		esac; \
		echo "$$choice" > .release-type.tmp; \
	else \
		if [ "$(TYPE)" != "patch" ] && [ "$(TYPE)" != "minor" ] && [ "$(TYPE)" != "major" ]; then \
			echo "ERROR: Invalid TYPE '$(TYPE)'"; \
			echo "Must be: patch, minor, or major"; \
			exit 1; \
		fi; \
		echo "$(TYPE)" > .release-type.tmp; \
	fi

# Perform the actual release with confirmation for major
do-release:
	@RELEASE_TYPE=$$(cat .release-type.tmp 2>/dev/null) || { \
		echo "ERROR: Failed to read release type"; \
		rm -f .release-type.tmp; \
		exit 1; \
	}; \
	[ -n "$$RELEASE_TYPE" ] || { \
		echo "ERROR: Release type is empty"; \
		rm -f .release-type.tmp; \
		exit 1; \
	}; \
	if [ "$$RELEASE_TYPE" = "major" ]; then \
		echo ""; \
		echo "========================================"; \
		echo "WARNING: MAJOR RELEASE"; \
		echo "========================================"; \
		echo "This will create a BREAKING CHANGE release."; \
		echo "Major releases indicate incompatible API changes."; \
		echo ""; \
		read -p "Are you sure you want to continue? [y/N]: " confirm; \
		case $$confirm in \
			[Yy]*) echo "Proceeding with major release..." ;; \
			*) echo "Release cancelled."; rm -f .release-type.tmp; exit 1 ;; \
		esac; \
		echo ""; \
	fi; \
	$(MAKE) $$RELEASE_TYPE

# Clean up temporary files
cleanup-tmp:
	@rm -f .release-type.tmp

check-branch:
	@if [ "$$(git rev-parse --abbrev-ref HEAD)" != "main" ]; then \
		echo "ERROR: You are not on the 'main' branch. Aborting."; \
		exit 1; \
	fi

check-dirty:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Uncommitted changes detected. Commit or stash changes before starting a release."; \
		exit 1; \
	fi

check-clean:
	@if [ -n "$$(git status --porcelain)" ]; then \
		echo "ERROR: Git working directory is not clean. Commit or stash changes first."; \
		exit 1; \
	fi

check-sync:
	@echo "Verifying environment is synced with uv.lock..."
	@uv sync --all-extras --all-groups --dry-run > /dev/null 2>&1 || { \
		echo "ERROR: Environment is out of sync with uv.lock"; \
		echo "Run 'make sync' to update your environment"; \
		exit 1; \
	}
	@echo "Environment is synced"

push:
	git push && git push --tags
