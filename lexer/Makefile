.PHONY: compile run clean

compile:
	python3 -m py_compile lexer.py

run: compile
	python3 lexer.py $(TEST)

clean:
	rm -rf __pycache__/
