.DEFAULT_GOAL := help

PYTHON ?= python3
VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python
export CSV_TIMESTAMP_FORMAT

MASK ?= docs/raw/data_filled_mask.csv

.PHONY: help venv install dev load db-check check train tune

help:
	@printf '%s\n' \
	  'make install  Create the virtual environment and install dependencies' \
	  'make dev      Choose a pipeline operation' \
	  'make load     Prompt for a cleaned CSV path and import into SQL Server' \
	  'make db-check  Show connected SQL identity and effective permissions' \
	  'make check    Check Python syntax and installed dependency compatibility' \
	  'make venv     Create the virtual environment if missing' \
	  'make train DATA=<csv> OUTPUT=<dir> [TARGET=<name>] [MASK=<csv>]' \
	  'make tune SOURCE=<baseline-dir> OUTPUT=<dir>' \
	  'make help     Show available commands'

venv: $(VENV_PYTHON)

$(VENV_PYTHON):
	$(PYTHON) -m venv "$(VENV)"

install: venv
	"$(VENV_PYTHON)" -m pip install -r requirements.txt

dev:
	"$(VENV_PYTHON)" main.py

load:
	"$(VENV_PYTHON)" main.py --load-csv

db-check:
	"$(VENV_PYTHON)" -m src.database_check

check:
	"$(VENV_PYTHON)" -m compileall -q main.py src config
	"$(VENV_PYTHON)" -m pip check

# Supported TARGET values (omit TARGET to train all models):
#   eff_nh3_n       -> Eff_NH4_N
#   eff_no3_n       -> Eff_NO3_N
#   a1_ch3oh_flow   -> A1_FQ_CH3OH
#   a2_ch3oh_flow   -> A2_FQ_CH3OH
#   a1_air_flow     -> A1_Q_air
#   a2_air_flow     -> A2_Q_air
train:
	$(if $(strip $(DATA)),,$(error Set DATA to the prepared CSV path))
	$(if $(strip $(OUTPUT)),,$(error Set OUTPUT to the training results directory))
	"$(VENV_PYTHON)" -m src.training.train --data "$(DATA)" --mask "$(MASK)" $(if $(strip $(TARGET)),--targets "$(TARGET)") --output "$(OUTPUT)"

tune:
	$(if $(strip $(SOURCE)),,$(error Set SOURCE to the baseline training results directory))
	$(if $(strip $(OUTPUT)),,$(error Set OUTPUT to the tuned results directory))
	"$(VENV_PYTHON)" -m src.training.tune --source "$(SOURCE)" --output "$(OUTPUT)"
