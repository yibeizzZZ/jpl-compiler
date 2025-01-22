# ast_nodes.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ASTNode:
    start_idx: int = 0

    def to_s_expression(self) -> str:
        # 子类覆盖此方法
        return "(ASTNode)"

### 命令 (Cmd) ###

@dataclass
class Cmd(ASTNode):
    pass

@dataclass
class ReadCmd(Cmd):
    filename: str
    lvalue: 'LValue'
    def to_s_expression(self) -> str:
        return f'(ReadCmd "{self.filename}" {self.lvalue.to_s_expression()})'

@dataclass
class WriteCmd(Cmd):
    expr: 'Expr'
    filename: str
    def to_s_expression(self) -> str:
        return f'(WriteCmd {self.expr.to_s_expression()} "{self.filename}")'

@dataclass
class LetCmd(Cmd):
    lvalue: 'LValue'
    expr: 'Expr'
    def to_s_expression(self) -> str:
        return f'(LetCmd {self.lvalue.to_s_expression()} {self.expr.to_s_expression()})'

@dataclass
class AssertCmd(Cmd):
    expr: 'Expr'
    message: str
    def to_s_expression(self) -> str:
        return f'(AssertCmd {self.expr.to_s_expression()} "{self.message}")'

@dataclass
class PrintCmd(Cmd):
    message: str
    def to_s_expression(self) -> str:
        return f'(PrintCmd "{self.message}")'

@dataclass
class ShowCmd(Cmd):
    expr: 'Expr'
    def to_s_expression(self) -> str:
        return f'(ShowCmd {self.expr.to_s_expression()})'

@dataclass
class TimeCmd(Cmd):
    sub_cmd: Cmd
    def to_s_expression(self) -> str:
        return f'(TimeCmd {self.sub_cmd.to_s_expression()})'

### 表达式 (Expr) ###

@dataclass
class Expr(ASTNode):
    pass

@dataclass
class IntExpr(Expr):
    value: int
    def to_s_expression(self) -> str:
        return f'(IntExpr {self.value})'

@dataclass
class FloatExpr(Expr):
    value: float
    def to_s_expression(self) -> str:
        # 作业要求将 float 强制为 64-bit int 输出
        return f'(FloatExpr {int(self.value)})'

@dataclass
class TrueExpr(Expr):
    def to_s_expression(self) -> str:
        return '(TrueExpr)'

@dataclass
class FalseExpr(Expr):
    def to_s_expression(self) -> str:
        return '(FalseExpr)'

@dataclass
class VarExpr(Expr):
    name: str
    def to_s_expression(self) -> str:
        return f'(VarExpr {self.name})'

@dataclass
class ArrayLiteralExpr(Expr):
    elems: List[Expr]
    def to_s_expression(self) -> str:
        # 例如: (ArrayLiteralExpr (IntExpr 1) (VarExpr x) ...)
        inner = ' '.join(e.to_s_expression() for e in self.elems)
        return f'(ArrayLiteralExpr {inner})'

### 左值 (LValue) ###

@dataclass
class LValue(ASTNode):
    pass

@dataclass
class VarLValue(LValue):
    name: str
    def to_s_expression(self) -> str:
        return f'(VarLValue {self.name})'
