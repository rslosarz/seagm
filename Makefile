# SEAGM diary + Dexcom Clarity — convenience targets (XLSX only)
# Run: make help

PYTHON       ?= $(abspath .venv/bin/python)
PIP          ?= $(abspath .venv/bin/pip)
REQUIREMENTS  = requirements.txt
VENV_STAMP    = .venv/.deps-installed

# Inputs (override on the command line)
DIARY      ?= SEAGM_03_diary.xlsx
CLARITY    ?= Clarity_Export_SeaGM03_JF_2026-03-11_162431.xlsx
OUTDIR     ?= output
GAP_HOURS  ?= 1.0

CONDENSE_OUT  := $(OUTDIR)/diary_intervals.xlsx
ENRICH_OUT    := $(OUTDIR)/Clarity_with_diary.xlsx

.PHONY: help setup install condense enrich all clean-output

help:
	@echo "Targets:"
	@echo "  make setup        — create .venv and install deps (first run or after requirements.txt changes)"
	@echo "  make install      — same as setup"
	@echo "  make condense     — diary .xlsx -> $(CONDENSE_OUT) (three sheets)"
	@echo "  make enrich       — Clarity .xlsx + diary columns -> $(ENRICH_OUT)"
	@echo "  make all          — condense, then enrich"
	@echo "  make clean-output — remove $(OUTDIR)/"
	@echo ""
	@echo "Variables (make VAR=value):"
	@echo "  DIARY=$(DIARY)"
	@echo "  CLARITY=$(CLARITY)"
	@echo "  OUTDIR=$(OUTDIR)"
	@echo "  GAP_HOURS=$(GAP_HOURS)"
	@echo "  PYTHON=$(PYTHON)"

$(VENV_STAMP): $(REQUIREMENTS)
	@test -x .venv/bin/python || python3 -m venv .venv
	$(PIP) install -r $(REQUIREMENTS)
	@touch $(VENV_STAMP)

setup install: $(VENV_STAMP)

condense: $(VENV_STAMP)
	@mkdir -p "$(OUTDIR)"
	$(PYTHON) scripts/condense_diary.py \
		-i "$(DIARY)" \
		-o "$(CONDENSE_OUT)" \
		--gap-hours "$(GAP_HOURS)"

enrich: $(VENV_STAMP)
	@mkdir -p "$(OUTDIR)"
	$(PYTHON) scripts/enrich_clarity.py \
		-d "$(DIARY)" \
		-c "$(CLARITY)" \
		-o "$(ENRICH_OUT)"

all: condense enrich

clean-output:
	rm -rf "$(OUTDIR)"
