# Default file for testing (can be overridden using TEST)
# TEST=./grader/hw4/fail-fuzzer1/001.jpl
# TEST=./grader/hw8/ok-fuzzer/002.jpl
TEST = test.jpl
FLAGS=-s
# Default target
all: help

# Compile Python file for syntax errors
compile: compiler.py
	python3 -m py_compile $^ parser.py

# Run the lexer
run:
	python3 compiler.py $(FLAGS) $(TEST)

# Run tests with the auto-grader
test:
	make -C ./grader DIR=$(PWD)  test-hw14

hi:
	make -C ./grader DIR=$(PWD) PART=2 test-hw11
go:
	make -C ./grader DIR=$(PWD) PART=3 test-hw11
# Display help
help:
	@echo "Available targets:"
	@echo "  run      - Run the lexer with: make run TEST=<input_file.jpl>"
	@echo "  compile  - Check for syntax errors in compiler.py"
	@echo "  test     - Run tests using the auto-grader"
	@echo "  clean    - Remove temporary files"

# Clean up temporary files
clean:
	rm -f *.out
	rm -fr __pycache__