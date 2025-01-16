
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class Token:
    start_idx: int

# 标点符号
@dataclass
class Punctuation(Token):
    pass

@dataclass
class LSQUARE(Punctuation):
    pass

@dataclass
class RSQUARE(Punctuation):
    pass

@dataclass
class LCURLY(Punctuation):
    pass

@dataclass
class RCURLY(Punctuation):
    pass

@dataclass
class LPAREN(Punctuation):
    pass

@dataclass
class RPAREN(Punctuation):
    pass

@dataclass
class COMMA(Punctuation):
    pass

@dataclass
class COLON(Punctuation):
    pass

@dataclass
class DOT(Punctuation):
    pass

# 运算符
@dataclass
class Operator(Token):
    pass

@dataclass
class OP(Operator):
    symbol: str

@dataclass
class EQUALS(Operator):
    pass

# 特殊 Token
@dataclass
class Special(Token):
    pass

@dataclass
class NEWLINE(Special):
    pass

@dataclass
class END_OF_FILE(Special):
    pass

# 关键字
@dataclass
class Keyword(Token):
    pass

@dataclass
class ASSERT(Keyword):
    pass

@dataclass
class ELSE(Keyword):
    pass

@dataclass
class FALSE(Keyword):
    pass

@dataclass
class FN(Keyword):
    pass

@dataclass
class IF(Keyword):
    pass

@dataclass
class LET(Keyword):
    pass

@dataclass
class PRINT(Keyword):
    pass

@dataclass
class READ(Keyword):
    pass

@dataclass
class RETURN(Keyword):
    pass

@dataclass
class SHOW(Keyword):
    pass

@dataclass
class SUM(Keyword):
    pass

@dataclass
class THEN(Keyword):
    pass

@dataclass
class TIME(Keyword):
    pass

@dataclass
class TO(Keyword):
    pass

@dataclass
class TRUE(Keyword):
    pass

@dataclass
class VOID(Keyword):
    pass

@dataclass
class WRITE(Keyword):
    pass

# 数据类型
@dataclass
class Datatype(Token):
    pass

@dataclass
class ARRAY(Datatype):
    pass

@dataclass
class BOOL(Datatype):
    pass

@dataclass
class FLOAT(Datatype):
    pass    

@dataclass
class IMAGE(Datatype):
    pass

@dataclass
class INT(Datatype):
    pass

@dataclass
class STRUCT(Datatype):
    pass

# 字面量
@dataclass
class Literal(Token):
    pass

@dataclass
class INTVAL(Literal):
    value: int

@dataclass
class FLOATVAL(Literal):
    value: float

@dataclass
class STRING(Literal):
    value: str

# 变量名
@dataclass
class VARIABLE(Token):
    name: str


'''
-----------------------------------------------------------------------------------------
前面的是class的定义
-----------------------------------------------------------------------------------------
'''

def is_digit(char: str):
    return char in "0123456789"
def is_letter_or_underscore(ch: str) -> bool:
    return ch.isalpha() or ch == "_"
def is_alnum_or_underscore(ch: str) -> bool:
    return ch.isalnum() or ch == "_"
def lex_number(source: str, start_index: int) -> Tuple[Token, int]:
    """
    读取一串数字，如果遇到'.'则转为浮点数。
    返回 (解析到的Token, 终止位置)
    """
    curr_index = start_index
    has_dot = False
    acc = ""

    while curr_index < len(source):
        ch = source[curr_index]
        # 如果是数字
        if is_digit(ch):
            acc += ch
            curr_index += 1
        elif ch == '.' and not has_dot:
            # 第一次遇到小数点
            has_dot = True
            acc += ch
            curr_index += 1
        else:
            break

    if has_dot:
        # 转为float
        return (FLOATVAL(start_index, float(acc)), curr_index)
    else:
        # 转为int
        return (INTVAL(start_index, int(acc)), curr_index)

def lex_string(source: str, start_index: int) -> Tuple[Token, int]:
    """
    解析形如 "hello" 的字符串。
    简化处理，不支持转义字符。
    """
    curr_index = start_index
    # 跳过开头的双引号
    opening_quote = source[curr_index]
    assert opening_quote == '"', "lex_string: expected '\"'"

    curr_index += 1
    acc = ""
    while curr_index < len(source) and source[curr_index] != '"':
        acc += source[curr_index]
        curr_index += 1

    if curr_index >= len(source):
        raise ValueError("Unterminated string literal")

    # 跳过结束引号
    curr_index += 1
    return (STRING(start_index, acc), curr_index)

#
# 解析标识符 / 关键字
#
def lex_word(source: str, start_index: int) -> Tuple[Token, int]:
    """
    读取标识符(变量名)或关键字
    如果识别到关键字 => 返回对应的Token
    否则 => VARIABLE
    """
    curr_index = start_index
    acc = ""

    # 至少要以 [a-zA-Z_] 开头
    while curr_index < len(source) and is_alnum_or_underscore(source[curr_index]):
        acc += source[curr_index]
        curr_index += 1

    # 判断是否是关键字
    kw_map = {
        "array": ARRAY,
        "assert": ASSERT,
        "bool": BOOL,
        "else": ELSE,
        "false": FALSE,
        "float": FLOAT,
        "fn": FN,
        "if": IF,
        "image": IMAGE,
        "int": INT,
        "let": LET,
        "print": PRINT,
        "read": READ,
        "return": RETURN,
        "show": SHOW,
        "struct": STRUCT,
        "sum": SUM,
        "then": THEN,
        "time": TIME,
        "to": TO,
        "true": TRUE,
        "void": VOID,
        "write": WRITE,
    }

    if acc in kw_map:
        return (kw_map[acc](start_index), curr_index)
    else:
        return (VARIABLE(start_index, name=acc), curr_index)
    

def lex(source: str) -> List[Token]:
    tokens: List[Token] = []
    curr_index = 0
    length = len(source)
    had_content = False
    while curr_index < length:
        ch = source[curr_index]
        
        # 1. 跳过空格和制表符
        if ch in [' ', '\t']:
            curr_index += 1
            continue

        # 2. 处理换行符(保留 had_content 逻辑)
        if ch == '\n':
            if had_content:
                tokens.append(NEWLINE(curr_index))
            curr_index += 1
            had_content = False
            continue
        had_content = True

        # 3. 跳过 "//" 直到换行或EOF
        if ch == '/' and curr_index + 1 < length and source[curr_index + 1] == '/':
            # 跳过 "//" 到行尾
            curr_index += 2
            while curr_index < length and source[curr_index] != '\n':
                curr_index += 1
            continue

        # 4. 处理方括号 [ / ]
        if ch == '[':
            tokens.append(LSQUARE(curr_index))
            curr_index += 1
            continue
        if ch == ']':
            tokens.append(RSQUARE(curr_index))
            curr_index += 1
            continue

        # 5. 处理大括号 { / }
        if ch == '{':
            tokens.append(LCURLY(curr_index))
            curr_index += 1
            continue
        if ch == '}':
            tokens.append(RCURLY(curr_index))
            curr_index += 1
            continue

        # 6. 处理小括号 ( / )
        if ch == '(':
            tokens.append(LPAREN(curr_index))
            curr_index += 1
            continue
        if ch == ')':
            tokens.append(RPAREN(curr_index))
            curr_index += 1
            continue

        # 7. 处理逗号、冒号、点、等号
        if ch == ',':
            tokens.append(COMMA(curr_index))
            curr_index += 1
            continue
        if ch == ':':
            tokens.append(COLON(curr_index))
            curr_index += 1
            continue
        if ch == '.':
            tokens.append(DOT(curr_index))
            curr_index += 1
            continue
        if ch == '=':
            # 这里根据需要分辨单等号还是 ==，此处示例认为单等号 => EQUALS
            tokens.append(EQUALS(curr_index))
            curr_index += 1
            continue

        # 8. 处理数字 (int 或 float)
        if is_digit(ch):
            number_token, next_idx = lex_number(source, curr_index)
            tokens.append(number_token)
            curr_index = next_idx
            continue

        # 9. 处理字符串 (双引号开头)
        if ch == '"':
            string_token, next_idx = lex_string(source, curr_index)
            tokens.append(string_token)
            curr_index = next_idx
            continue

        # 10. 处理操作符(例如 +, -, *, /, <, >, !, etc.)
        #    这里示例只做最简单处理: 如果是 + - * / 就当 OP
        if ch in "+-*/<>!&|":
            tokens.append(OP(curr_index, symbol=ch))
            curr_index += 1
            continue

        # 11. 处理标识符(变量)或关键字
        if is_letter_or_underscore(ch):
            word_token, next_idx = lex_word(source, curr_index)
            tokens.append(word_token)
            curr_index = next_idx
            continue

        # 如果走到这里 => 非法字符
        raise ValueError(f"Invalid character '{ch}' at index {curr_index}")

    # 最后，追加一个 END_OF_FILE Token
    tokens.append(END_OF_FILE(curr_index))
    return tokens


'''----test output-------'''
if __name__ == "__main__":
    import sys

    # 检查命令行参数数量
    if len(sys.argv) < 3:
        print("Usage: python lexer.py -l <input_file.jpl>")
        sys.exit(1)

    # 检查是否传入 -l 参数
    if sys.argv[1] != "-l":
        print("Unknown option, expected '-l'")
        sys.exit(1)

    filename = sys.argv[2]

    try:
        with open(filename, "r", encoding="utf-8") as f:
            source_code = f.read()

        tokens = lex(source_code)

        # 自定义打印格式
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
                print(f"STRING \"{tk.value}\"")
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
                print(f"ARRAY 'array'")
            else:
                # 对于未覆盖的 Token，直接打印类名
                print(tk.__class__.__name__)

        # 词法分析成功
        print("Compilation succeeded\n")

    except Exception as e:
        # 词法分析失败，打印具体错误信息
        print("Compilation failed")
        print(e)  # 打印错误信息
        sys.exit(1)