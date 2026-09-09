PYTHON ?= python3
TEST ?= test.jpl
FLAGS ?= -s
SOURCES := $(wildcard *.py) $(wildcard tests/*.py)

.PHONY: all compile run test help clean

all: help

# Check every compiler and test module for Python syntax errors.
compile:
	$(PYTHON) -m py_compile $(SOURCES)

run:
	$(PYTHON) compiler.py $(FLAGS) "$(TEST)"

# Local smoke and regression tests; no external runtime is needed.
test:
	$(PYTHON) -m unittest discover -s tests -v

help:
	@echo "Available targets:"
	@echo "  run      - Run the compiler: make run TEST=test.jpl FLAGS=-t"
	@echo "  compile  - Check all Python modules for syntax errors"
	@echo "  test     - Run local smoke and regression tests"
	@echo "  clean    - Remove temporary files"
	@echo "Use PYTHON=python to select a different Python 3.12+ executable."

clean:
	rm -f *.out
	rm -rf __pycache__ tests/__pycache__
