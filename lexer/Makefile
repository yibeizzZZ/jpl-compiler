.PHONY: compile run clean

compile:	
	python3 -m py_compile lexer.py

go: compile	
	python3 lexer.py $(TEST)

run: compile	
	python3 lexer.py -l $(TEST)

clean:	
	rm -rf __pycache__/
