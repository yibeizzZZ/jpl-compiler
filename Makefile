# Default file for testing (can be overridden using TEST)
TEST=test.jpl

# Default target
all: help

# Compile Python file for syntax errors
compile: compiler.py
	python3 -m py_compile $^

# Run the lexer
run:
	python3 compiler.py -l $(TEST)

# Run tests with the auto-grader
test:
	make -C ./grader DIR=$(PWD) test-hw2

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
