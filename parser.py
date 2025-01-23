from typing import List, Union
from dataclasses import dataclass
from lexer import *


# Base AST Node
@dataclass
class ASTNode:
    start_idx: int

    def to_s_expression(self) -> str:
        raise NotImplementedError("to_s_expression must be implemented in subclasses")


# Commands
@dataclass
class Cmd(ASTNode):
    pass


@dataclass
class PrintCmd(Cmd):
    message: str

    def to_s_expression(self) -> str:
        return f'(PrintCmd "{self.message}")'


@dataclass
class ReadCmd(Cmd):
    filename: str
    var_name: str

    def to_s_expression(self) -> str:
        return f'(ReadCmd "{self.filename}" (VarLValue {self.var_name}))'


@dataclass
class WriteCmd(Cmd):
    expr: "Expr"
    filename: str

    def to_s_expression(self) -> str:
        return f'(WriteCmd {self.expr.to_s_expression()} "{self.filename}")'


@dataclass
class AssertCmd(Cmd):
    expr: "Expr"
    message: str

    def to_s_expression(self) -> str:
        return f'(AssertCmd {self.expr.to_s_expression()} "{self.message}")'


@dataclass
class ShowCmd(Cmd):
    expr: "Expr"

    def to_s_expression(self) -> str:
        return f"(ShowCmd {self.expr.to_s_expression()})"


@dataclass
class TimeCmd(Cmd):
    cmd: Cmd

    def to_s_expression(self) -> str:
        return f"(TimeCmd {self.cmd.to_s_expression()})"


# Expressions
@dataclass
class Expr(ASTNode):
    pass


@dataclass
class IntExpr(Expr):
    value: int

    def to_s_expression(self) -> str:
        return f"(IntExpr {self.value})"


@dataclass
class FloatExpr(Expr):
    value: float

    def to_s_expression(self) -> str:
        return f"(FloatExpr {int(self.value)})"  # Cast to int for output


@dataclass
class TrueExpr(Expr):
    def to_s_expression(self) -> str:
        return "(TrueExpr)"


@dataclass
class FalseExpr(Expr):
    def to_s_expression(self) -> str:
        return "(FalseExpr)"


@dataclass
class VarExpr(Expr):
    name: str

    def to_s_expression(self) -> str:
        return f"(VarExpr {self.name})"


@dataclass
class ArrayLiteralExpr(Expr):
    elements: List[Expr]

    def to_s_expression(self) -> str:
        elements_s = " ".join(e.to_s_expression() for e in self.elements)
        if elements_s:  # 如果非空
            return f"(ArrayLiteralExpr {elements_s})"
        else:
            return "(ArrayLiteralExpr)"


# LValue@dataclass

@dataclass
class LValue(ASTNode):
    pass

@dataclass
class LetCmd(Cmd):
    lvalue: LValue       # 存一个左值对象
    value: Expr          # 存一个表达式
    def to_s_expression(self) -> str:
        return f"(LetCmd {self.lvalue.to_s_expression()} {self.value.to_s_expression()})"
    
@dataclass
class VarLValue(LValue):
    name: str

    def to_s_expression(self) -> str:
        return f"(VarLValue {self.name})"


# Parser
class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def advance(self):
        self.pos += 1

    def match(self, expected_type):
        if isinstance(self.current_token(), expected_type):
            token = self.current_token()
            self.advance()
            return token
        else:
            raise SyntaxError(
                f"Expected {expected_type}, but found {type(self.current_token())}"
            )

    # Parse individual commands
    def parse_cmd(self) -> Cmd:
        current = self.current_token()
        if isinstance(current, LET):
            return self.parse_let_cmd()
        elif isinstance(current, PRINT):
            return self.parse_print_cmd()
        elif isinstance(current, READ):
            return self.parse_read_cmd()
        elif isinstance(current, WRITE):
            return self.parse_write_cmd()
        elif isinstance(current, ASSERT):
            return self.parse_assert_cmd()
        elif isinstance(current, SHOW):
            return self.parse_show_cmd()
        elif isinstance(current, TIME):
            return self.parse_time_cmd()
        else:
            raise SyntaxError(f"Unexpected command: {current}")

    def parse_let_cmd(self) -> LetCmd:
        self.match(LET)
        lval = self.parse_lvalue()
        self.match(EQUALS)
        rhs_expr = self.parse_expr()
        return LetCmd(start_idx=self.pos, lvalue=lval, value=rhs_expr)

    def parse_lvalue(self) -> LValue:
        token = self.match(VARIABLE)
        return VarLValue(start_idx=token.start_idx, name=token.name)
    
    def parse_print_cmd(self) -> PrintCmd:
        self.match(PRINT)
        message = self.match(STRING).value
        return PrintCmd(start_idx=self.pos, message=message)

    def parse_read_cmd(self) -> ReadCmd:
        self.match(READ)
        isinstance(self.current_token(), IMAGE)
        self.advance()
        filename = self.match(STRING).value
        self.match(TO)
        var_name = self.parse_mixed_var_expr().name
        return ReadCmd(start_idx=self.pos, filename=filename, var_name=var_name)

    def parse_write_cmd(self) -> WriteCmd:
        self.match(WRITE)  # Match the 'write' keyword

        # Optionally match the IMAGE token
        if isinstance(self.current_token(), IMAGE):
            self.advance()

        expr = self.parse_expr()  # Parse the expression for the content to write
        self.match(TO)  # Match the 'to' keyword
        filename = self.match(STRING).value  # Match the STRING token for the filename

        return WriteCmd(start_idx=self.pos, expr=expr, filename=filename)

    def parse_assert_cmd(self) -> AssertCmd:
        self.match(ASSERT)  # 匹配 `assert`
        expr = self.parse_expr()  # 解析表达式部分
        self.match(COMMA)  # 显式匹配逗号
        message = self.match(STRING).value  # 解析字符串部分
        return AssertCmd(start_idx=self.pos, expr=expr, message=message)

    def parse_show_cmd(self) -> ShowCmd:
        self.match(SHOW)
        expr = self.parse_expr()
        return ShowCmd(start_idx=self.pos, expr=expr)

    def parse_time_cmd(self) -> TimeCmd:
        self.match(TIME)
        cmd = self.parse_cmd()
        return TimeCmd(start_idx=self.pos, cmd=cmd)

    def parse_mixed_var_expr(self) -> VarExpr:
        current = self.current_token()
        parts = []

        # Collect parts of the mixed variable name
        while isinstance(current, (VARIABLE, FLOATVAL, DOT)):
            if isinstance(current, VARIABLE):
                parts.append(current.name)  # Use `name` for VARIABLE tokens
            elif isinstance(current, FLOATVAL):
                parts.append(str(current.value))  # Use `value` for FLOATVAL tokens
            elif isinstance(current, DOT):
                parts.append(".")  # Append the dot symbol
            self.advance()
            current = self.current_token()

        # Reassemble the parts into a single name
        name = "".join(parts)

        # Validate the resulting name
        if not name.replace("_", "").replace(".", "").isalnum():
            raise SyntaxError(f"Invalid mixed variable name: {name}")

        return VarExpr(start_idx=self.pos, name=name)

    # Parse expressions
    def parse_expr(self) -> Expr:
        current = self.current_token()
        if isinstance(current, INTVAL):
            return self.parse_int_expr()
        elif isinstance(current, FLOATVAL):
            return self.parse_float_expr()
        elif isinstance(current, VARIABLE) or isinstance(current, DOT):
            # Handle mixed variable names with dots
            return self.parse_mixed_var_expr()
        elif isinstance(current, STRING):
            return self.parse_string_expr()
        elif isinstance(current, TRUE):
            return self.parse_true_expr()
        elif isinstance(current, FALSE):
            return self.parse_false_expr()
        elif isinstance(current, LSQUARE):
            return self.parse_array_literal_expr()
        else:
            raise SyntaxError(f"Unexpected expression: {current}")

    def parse_int_expr(self) -> IntExpr:
        token = self.match(INTVAL)
        val = token.value  
        if val < - (2**63) or val > (2**63 - 1):
            raise SyntaxError(f"Integer out of 64-bit range: {val}")
        return IntExpr(start_idx=token.start_idx, value=val)

    def parse_float_expr(self) -> FloatExpr:
        token = self.match(FLOATVAL)
        return FloatExpr(start_idx=token.start_idx, value=float(token.value))

    def parse_var_expr(self) -> VarExpr:
        token = self.match(VARIABLE)

        # Allow valid variable names, even with mixed content
        if not token.name.replace("_", "").isalnum() and "." not in token.name:
            raise SyntaxError(f"Invalid variable name: {token.name}")

        return VarExpr(start_idx=token.start_idx, name=token.name)

    def parse_true_expr(self) -> TrueExpr:
        self.match(TRUE)
        return TrueExpr(start_idx=self.pos)

    def parse_false_expr(self) -> FalseExpr:
        self.match(FALSE)
        return FalseExpr(start_idx=self.pos)

    def parse_array_literal_expr(self) -> ArrayLiteralExpr:
        self.match(LSQUARE)
        elements = []
        while not isinstance(self.current_token(), RSQUARE):
            elements.append(self.parse_expr())
            if isinstance(self.current_token(), COMMA):
                self.advance()
        self.match(RSQUARE)
        return ArrayLiteralExpr(start_idx=self.pos, elements=elements)

    # Parse entire program
    def parse_program(self) -> List[Cmd]:
        commands = []
        while True:
        # 跳过所有 NEWLINE
            while isinstance(self.current_token(), NEWLINE):
                self.advance()
        # 若已经EOF，就break
            if self.current_token() is None or isinstance(self.current_token(), END_OF_FILE):
                break
        # 解析一条命令
            cmd = self.parse_cmd()
            commands.append(cmd)
        # 解析完后，再跳过结尾的 NEWLINE
            while isinstance(self.current_token(), NEWLINE):
                self.advance()
        # 再循环
        return commands
