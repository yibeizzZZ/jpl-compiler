import string
from typing import List, Tuple
from dataclasses import dataclass
from typechecker import *


def process_tokens(tokens):
    for tk in tokens:
        if isinstance(tk, NEWLINE):
            print("NEWLINE")
        elif isinstance(tk, END_OF_FILE):
            print("END_OF_FILE")
        elif isinstance(tk, LET):
            print("LET 'let'")
        elif isinstance(tk, FN):
            print("FN 'fn'")
        elif isinstance(tk, RETURN):
            print("RETURN 'return'")
        elif isinstance(tk, SHOW):
            print("SHOW 'show'")
        elif isinstance(tk, ASSERT):
            print("ASSERT 'assert'")
        elif isinstance(tk, FALSE):
            print("FALSE 'false'")
        elif isinstance(tk, VARIABLE):
            print(f"VARIABLE '{tk.name}'")
        elif isinstance(tk, EQUALS):
            print("EQUALS '='")
        elif isinstance(tk, INTVAL):
            print(f"INTVAL '{tk.value}'")
        elif isinstance(tk, FLOATVAL):
            print(f"FLOATVAL '{tk.value}'")
        elif isinstance(tk, STRING):
            print(f"STRING \'\"{tk.value}\"\'")
        elif isinstance(tk, OP):
            print(f"OP '{tk.symbol}'")
        elif isinstance(tk, COLON):
            print("COLON ':'")
        elif isinstance(tk, INT):
            print("INT 'int'")
        elif isinstance(tk, LCURLY):
            print("LCURLY '{'")
        elif isinstance(tk, RCURLY):
            print("RCURLY '}'")
        elif isinstance(tk, LPAREN):
            print("LPAREN '('")
        elif isinstance(tk, RPAREN):
            print("RPAREN ')'")
        elif isinstance(tk, LSQUARE):
            print("LSQUARE '['")
        elif isinstance(tk, RSQUARE):
            print("RSQUARE ']'")
        elif isinstance(tk, COMMA):
            print("COMMA ','")
        elif isinstance(tk, DOT):
            print("DOT '.'")
        elif isinstance(tk, BOOL):
            print("BOOL 'bool'")
        elif isinstance(tk, ARRAY):
            print("ARRAY 'array'")
        elif isinstance(tk, FLOAT):
            print("FLOAT 'float'")
        elif isinstance(tk, TRUE):
            print("TRUE 'true'")
        elif isinstance(tk, STRUCT):
            print("STRUCT 'struct'")
        elif isinstance(tk, ELSE):
            print("ELSE 'else'")
        elif isinstance(tk, THEN):
            print("THEN 'then'")
        elif isinstance(tk, IF):
            print("IF 'if'")
        elif isinstance(tk, SUM):
            print("SUM 'sum'")
        elif isinstance(tk, READ):
            print("READ 'read'")
        elif isinstance(tk, IMAGE):
            print("IMAGE 'image'")
        elif isinstance(tk, TO):
            print("TO 'to'")
        elif isinstance(tk, WRITE):
            print("WRITE 'write'")
        elif isinstance(tk, TIME):
            print("TIME 'time'")
        elif isinstance(tk, PRINT):
            print("PRINT 'print'")
        elif isinstance(tk, VOID):
            print("VOID 'void'")
        else:
            print("Compilation failed")
            
    print("Compilation succeeded")
        
if __name__ == "__main__":
    import sys

    # Check the number of command line arguments
    if len(sys.argv) < 3:
        print("Usage: python compiler.py -l <input_file.jpl>")
        sys.exit(1)

    # Check if the -l parameter is passed
    if sys.argv[1] == "-l":
        filename = sys.argv[2]
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()

            tokens = lex(source_code)
            process_tokens(tokens)
            # Custom print format
        except Exception as e:
            print(f"Compilation failed")
            sys.exit(1)    

    elif sys.argv[1] == "-p":
        filename = sys.argv[2]
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()

            tokens = lex(source_code)
            parser = Parser(tokens)
            ast = parser.parse_program()

            for cmd in ast:
                print(cmd.to_s_expression())

            print("Compilation succeeded")

        except Exception as e:
            print(f"Compilation failed , {e}")
            sys.exit(1)

    elif sys.argv[1] == "-t":
        filename = sys.argv[2]
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()
                tokens = lex(source_code)
            parser = Parser(tokens)
            ast = parser.parse_program()
            annotated_ast = typecheck_and_annotate(ast)  # 确保返回的是一个列表
            for cmd in annotated_ast:
                print(cmd)
            print("Compilation succeeded")
        except Exception as e:
            print(f"Compilation failed, {e}")
            sys.exit(1)
    
    elif sys.argv[1] == "-i":
        # 新增的代码生成分支
        filename = sys.argv[2]
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()
            tokens = lex(source_code)
            parser = Parser(tokens)
            ast = parser.parse_program()
            typecheck_program(ast)  # 进行类型检查
            from codegen import generate_c_code
            c_code = generate_c_code(ast)
            print(c_code)
        except Exception as e:
            print("Compilation failed,", e)
            sys.exit(1)

    elif sys.argv[1] == "-s":

        filename = sys.argv[2]
        try:
            with open(filename, "r", encoding="utf-8") as f:
                source_code = f.read()
            tokens = lex(source_code)
            parser = Parser(tokens)
            ast = parser.parse_program()
            typecheck_program(ast)
            from assembly import generate_asm_code
            asm_code = generate_asm_code(ast)
            print(asm_code)
        except Exception as e:
            print("Compilation failed,", e)
            sys.exit(1)
            
    else:
        print("unknown flag")
        sys.exit(1)



