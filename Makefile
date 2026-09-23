.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: help venv install dev check

help:
	@printf '%s\n' \
	  'make install  Create the virtual environment and install dependencies' \
	  'make dev      Run main.py (Ctrl+C to disconnect and stop)' \
	  'make check    Check Python syntax and installed dependency compatibility' \
	  'make venv     Create the virtual environment if missing' \
	  'make help     Show available commands'

venv: $(VENV_PYTHON)

$(VENV_PYTHON):
	$(PYTHON) -m venv "$(VENV)"

install: venv
	"$(VENV_PYTHON)" -m pip install -r requirements.txt

dev:
	"$(VENV_PYTHON)" main.py

check:
	"$(VENV_PYTHON)" -m compileall -q main.py src config
	"$(VENV_PYTHON)" -m pip check
