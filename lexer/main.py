# Monday Jan 13
# Today, Ben said we'd tackle step 2 and then outlined a plan for step 3.
# What a disaster.
# Don't write a parser for HW2.
# The code below gives a reasonable lexer for the array language.
# -----------------------------------------------------------------------------
# Goal: parse JSON-style arrays
#
# An array starts with [ and is followed by any number of elements
# and ends with a bracket ]. An element is either an array
# or an nonnegative integer.
#
# Examples:
# []
# [[]]
# [1, 2, 3, 4]
# [1, [2, 3], 5]
#
# parse("[1,4,[[3]]]") == [1,4,[[3]]]
# parse("[") == error
# parse("]") == error
#
# Subgoals:
# 0. Grammar
# 1. Lexer
# 2. Parser
# GRAMMAR
# array := [ elem , ... ]
# (where "..." means zero or more repeats of the previous things)
#
# elem := nonnegative integer
# | array
# -----------------------------------------------------------------------------
# LEXER
# --- Classes for tokens, punctuation, and int values
from dataclasses import dataclass
@dataclass
class Token:
    start_idx: int
    @dataclass
    class Punctuation(Token):
        pass
        @dataclass
        class LBRACKET(Punctuation):
            pass
        @dataclass
        class RBRACKET(Punctuation):
            pass
        @dataclass
        class COMMA(Punctuation):
            pass
@dataclass
class Num(Token):
# non-negative integers
value: int
def lex(input: str) -> list[Token]:
"""
Examples --- omitting the start index:
lex("[1]") ==
[LBRACKET(),
Num(1),
RBRACKET()]
lex("[1, 3]") ==
[LBRACKET(),
Num(1),
COMMA(),
Num(3),
RBRACKET()]
lex("[1323]") ==
[LBRACKET(),
Num(1323),
RBRACKET()]
lex("]") == [RBRACKET()]
lex("[22, 1, , ][]") ==
[LBRACKET(),
Num(22),
COMMA(),
Num(1),
COMMA(),
COMMA(),
RBRACKET(),
LBRACKET(),
RBRACKET()]
HW2 is similar, turn a string (sequence of characters) into a flat sequence of
tokens
"""
### DON'T CHECK THAT INPUT STARTS WITH A [ OR ENDS WITH A ]
### THIS NOT THE JOB OF A LEXER
### if input[0] == "[":
### # lex array
### lex_array(input, 0)
### elif is_digit(input[0]):
### # ??? lex number
### assert False, f"expected array, got digit"
### elif input[0] == "]":
### # end of array
### assert False, f"expected array, got ]"
### elif input[0] == ",":
### # comma between elements?
### assert False, f"expected array, got comma (,)"
### else:
### assert False, f"invalid character {input[0]}"
### -----
out_tokens = []
curr_index = 0
while curr_index < len(input):
if input[curr_index] == "[":
out_tokens.append(LBRACKET(curr_index))
curr_index += 1
elif input[curr_index] == "]":
out_tokens.append(RBRACKET(curr_index))
curr_index += 1
elif input[curr_index] == ",":
out_tokens.append(COMMA(curr_index))
curr_index += 1
elif input[curr_index] == " ":
curr_index += 1
elif is_digit(input[curr_index]):
num_token, next_index = lex_number(input, curr_index)
out_tokens.append(num_token)
curr_index = next_index
else:
assert False, f"invalid character {input[curr_index]}"
return out_tokens
def is_digit(char: str):
"""
Examples:
is_digit("0") == True
is_digit("A") == False
is_digit("42") ==> invalid input
"""
return char in "0123456789"

def lex_number(input:str, start_index: int) -> tuple[Token, int]:
acc = "" # digits found so far
curr_index = start_index
while curr_index < len(input):
if is_digit(input[curr_index]):
acc += input[curr_index]
curr_index += 1
        else:
        break
    return (Num(start_index, int(acc)), curr_index)
