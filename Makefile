# SEAGM diary + Dexcom Clarity — convenience targets (XLSX only)
# Run: make help
#
# Put inputs under input/: one file whose name starts with SEAGM (diary) and one
# with Clarity_Export (Clarity). Override paths with condense -i / enrich -d -c if needed.

PYTHON       ?= $(abspath .venv/bin/python)
PIP          ?= $(abspath .venv/bin/pip)
REQUIREMENTS  = requirements.txt
VENV_STAMP    = .venv/.deps-installed

INPUT_DIR    ?= input
OUTDIR       ?= output
GAP_HOURS    ?= 1.0

CONDENSE_OUT  := $(OUTDIR)/diary_intervals.xlsx

.PHONY: help setup install condense enrich verify run-all clean-output

help:
	@echo "Targets:"
	@echo "  make setup        — create .venv and install deps (first run or after requirements.txt changes)"
	@echo "  make install      — same as setup"
	@echo "  make condense     — diary (input/SEAGM*.xlsx) -> $(CONDENSE_OUT)"
	@echo "  make enrich       — Clarity + diary -> $(OUTDIR)/<Clarity_stem>_diary.xlsx"
	@echo "  make verify       — check enriched Clarity vs diary + raw Clarity (recompute)"
	@echo "  make run-all      — condense, enrich, then verify"
	@echo "  make clean-output — remove $(OUTDIR)/"
	@echo ""
	@echo "Variables (make VAR=value):"
	@echo "  INPUT_DIR=$(INPUT_DIR)   (search here for prefixed .xlsx)"
	@echo "  OUTDIR=$(OUTDIR)"
	@echo "  GAP_HOURS=$(GAP_HOURS)"
	@echo "  PYTHON=$(PYTHON)"

$(VENV_STAMP): $(REQUIREMENTS)
	@test -x .venv/bin/python || python3 -m venv .venv
	$(PIP) install -r $(REQUIREMENTS)
	@touch $(VENV_STAMP)

setup install: $(VENV_STAMP)

condense: $(VENV_STAMP)
	@mkdir -p "$(INPUT_DIR)" "$(OUTDIR)"
	$(PYTHON) scripts/condense_diary.py \
		--input-dir "$(INPUT_DIR)" \
		-o "$(CONDENSE_OUT)" \
		--gap-hours "$(GAP_HOURS)"

enrich: $(VENV_STAMP)
	@mkdir -p "$(INPUT_DIR)" "$(OUTDIR)"
	$(PYTHON) scripts/enrich_clarity.py \
		--input-dir "$(INPUT_DIR)" \
		--output-dir "$(OUTDIR)"

verify: $(VENV_STAMP)
	$(PYTHON) scripts/verify_enrich.py \
		--input-dir "$(INPUT_DIR)" \
		--output-dir "$(OUTDIR)"

run-all: condense enrich verify

clean-output:
	rm -rf "$(OUTDIR)"
