import string
from typing import List, Tuple
from dataclasses import dataclass

@dataclass
class Token:
    start_idx: int

# Punctuation
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

# Operators
@dataclass
class Operator(Token):
    pass

@dataclass
class OP(Operator):
    symbol: str

@dataclass
class EQUALS(Operator):
    pass

# Special Tokens
@dataclass
class Special(Token):
    pass

@dataclass
class NEWLINE(Special):
    pass

@dataclass
class END_OF_FILE(Special):
    pass

# Keywords
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

# Data types
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

# Literals
@dataclass
class Literal(Token):
    pass

@dataclass
class INTVAL(Literal):
    value: int

@dataclass
class FLOATVAL(Literal):
    value: str

@dataclass
class STRING(Literal):
    value: str

# Variable names
@dataclass
class VARIABLE(Token):
    name: str

def is_digit(char: str):
    return char in "0123456789"

def is_letter_or_underscore(ch: str) -> bool:
    return ch.isalpha() or ch == "_"

def is_alnum_or_underscore(ch: str) -> bool:
    return ch.isalnum() or ch == "_"

def lex_number(source: str, start_index: int) -> Tuple[Token, int]:
    """
    Read a sequence of digits. If a '.' is encountered, convert to a float.
    Return (parsed Token, end position)
    """
    curr_index = start_index
    has_dot = False
    acc = ""

    while curr_index < len(source):
        ch = source[curr_index]
        # If it's a digit
        if is_digit(ch):
            acc += ch
            curr_index += 1
        elif ch == '.' and not has_dot:
            # First time encountering a dot
            has_dot = True
            acc += ch
            curr_index += 1
        else:
            break

    if has_dot:
        # Convert to float
        return (FLOATVAL(start_index, acc), curr_index)
    else:
        # Convert to int
        return (INTVAL(start_index, int(acc)), curr_index)

def lex_string(source: str, start_index: int) -> Tuple[Token, int]:
    """
    Parse strings enclosed in double quotes (").
    Rejects empty strings, strings with newlines, or unterminated strings.
    """
    curr_index = start_index
    opening_quote = source[curr_index]
    assert opening_quote == '"', "lex_string: expected '\"'"

    curr_index += 1  # Skip opening quote
    acc = ""

    while curr_index < len(source):
        char = source[curr_index]

        # Reject strings with newlines
        if char == '\n':
            raise ValueError(f"Error: Unterminated string literal at position {start_index}")

        # Reject non-printable/control characters except space
        if char not in string.printable or (char in string.whitespace and char != ' '):
            raise ValueError(f"Error: Non-printable or control character in string at position {curr_index}")

        # Closing quote found
        if char == '"':
            curr_index += 1
            # if acc == "":
            #     raise ValueError(f"Error: Empty string literal at position {start_index}")
            return (STRING(start_index, acc), curr_index)

        # Append character to string
        acc += char
        curr_index += 1

    # If we reach here, the string is unterminated
    raise ValueError(f"Error: Unterminated string literal at position {start_index}")

def lex_word(source: str, start_index: int) -> Tuple[Token, int]:
    """
    Read an identifier (variable name) or keyword.
    If a keyword is recognized => return the corresponding Token.
    Otherwise => VARIABLE
    """
    curr_index = start_index
    acc = ""

    # Must start with [a-zA-Z_]
    while curr_index < len(source) and is_alnum_or_underscore(source[curr_index]):
        acc += source[curr_index]
        curr_index += 1

    # Check if it's a keyword
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
    had_content = True
    while curr_index < length:
        ch = source[curr_index]
        
        # Check for non-printable/control characters
        if ch not in string.printable:
            raise ValueError(f"Compilation failed: Unexpected control character at index {curr_index}")

        # 1. Skip spaces and tabs
        if ch in [' ', '\t']:
            curr_index += 1
            continue

        if ch in "\\":
            curr_index += 2
            continue 

        # 2. Handle newlines (preserve had_content logic)
        if ch == '\n':
            if had_content and (len(tokens) == 0 or not isinstance(tokens[-1], NEWLINE)):
                tokens.append(NEWLINE(curr_index))
            curr_index += 1
            had_content = False
            continue
        
        if ch == '"':
            string_token, next_idx = lex_string(source, curr_index)
            tokens.append(string_token)
            curr_index = next_idx
            continue

        had_content = True

        # 3. Skip "//" until newline or EOF
        if ch == '/' and curr_index + 1 < length and source[curr_index + 1] == '/':
            # Skip "//" to end of line
            curr_index += 2
            while curr_index < length and source[curr_index] != '\n':
                curr_index += 1
            continue

        if ch == '/' and curr_index + 1 < length and source[curr_index + 1] == '*':

            curr_index += 2
            
            while curr_index < length + 1 and not (source[curr_index] == '*' and source[curr_index + 1] == '/'):
                curr_index += 1

            curr_index += 2
            continue

        # 4. Handle square brackets [ / ]
        if ch == '[':
            tokens.append(LSQUARE(curr_index))
            curr_index += 1
            continue
        if ch == ']':
            tokens.append(RSQUARE(curr_index))
            curr_index += 1
            continue

        # 5. Handle curly braces { / }
        if ch == '{':
            tokens.append(LCURLY(curr_index))
            curr_index += 1
            continue
        if ch == '}':
            tokens.append(RCURLY(curr_index))
            curr_index += 1
            continue

        # 6. Handle parentheses ( / )
        if ch == '(':
            tokens.append(LPAREN(curr_index))
            curr_index += 1
            continue
        if ch == ')':
            tokens.append(RPAREN(curr_index))
            curr_index += 1
            continue

        # 7. Handle comma, colon, dot, equals
        if ch == ',':
            tokens.append(COMMA(curr_index))
            curr_index += 1
            continue
        if ch == ':':
            tokens.append(COLON(curr_index))
            curr_index += 1
            continue
        if ch == '.':
            if curr_index + 1 < length and is_digit(source[curr_index + 1]):
                acc = "."
                start_index=curr_index

                while curr_index < len(source) - 1 and is_digit(source[curr_index+1]):
                    curr_index += 1
                    acc += source[curr_index]
                curr_index += 1
                tokens.append(FLOATVAL(start_index, acc))
            else:
                tokens.append(DOT(curr_index))
                curr_index += 1
            continue

        if ch == '=':
            # Distinguish between single equals and ==
            if curr_index + 1 < length and source[curr_index + 1] == '=':
                tokens.append(OP(curr_index, symbol="=="))
                curr_index += 2
            else:
                tokens.append(EQUALS(curr_index))
                curr_index += 1
            continue

        # 8. Handle numbers (int or float)
        if is_digit(ch):
            number_token, next_idx = lex_number(source, curr_index)
            tokens.append(number_token)
            curr_index = next_idx
            continue

        # 9. Handle strings (starting with double quote)
        if ch == '"':
            string_token, next_idx = lex_string(source, curr_index)
            tokens.append(string_token)
            curr_index = next_idx
            continue

        # 10. Handle operators (e.g., +, -, *, /, <, >, !, etc.)
        #     Here, we simply treat + - * / as OP
        if ch in "+-*/!%":
            tokens.append(OP(curr_index, symbol=ch))
            curr_index += 1
            continue

        # 11. Handle identifiers (variables) or keywords
        if is_letter_or_underscore(ch):
            word_token, next_idx = lex_word(source, curr_index)
            tokens.append(word_token)
            curr_index = next_idx
            continue

        if ch in ">":
            if curr_index + 1 < length and source[curr_index + 1] == '=':
                tokens.append(OP(curr_index, symbol=">="))
                curr_index += 2
            else:
                tokens.append(OP(curr_index, symbol=ch))
                curr_index += 1
            continue

        if ch in "<":
            if curr_index + 1 < length and source[curr_index + 1] == '=':
                tokens.append(OP(curr_index, symbol="<="))
                curr_index += 2
            else:
                tokens.append(OP(curr_index, symbol=ch))
                curr_index += 1
            continue
        
        if ch in "|":
            if curr_index + 1 < length and source[curr_index + 1] == '|':
                tokens.append(OP(curr_index, symbol="||"))
                curr_index += 2
            else:
                tokens.append(OP(curr_index, symbol=ch))
                curr_index += 1
            continue

        if ch in "&":
            if curr_index + 1 < length and source[curr_index + 1] == '&':
                tokens.append(OP(curr_index, symbol="&&"))
                curr_index += 2
            else:
                tokens.append(OP(curr_index, symbol=ch))
                curr_index += 1
            continue

        # If we encounter a null character or any other unexpected character
        if ch == '\0':
            raise ValueError(f"Compilation failed: Unexpected null character at index {curr_index}")

        # If we reach here => invalid character
        raise ValueError(f"Invalid character '{ch}' at index {curr_index}")

    # Finally, append an END_OF_FILE Token
    tokens.append(END_OF_FILE(curr_index))
    return tokens
