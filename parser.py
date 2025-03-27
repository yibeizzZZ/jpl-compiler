from typing import List, Union , Optional
from dataclasses import dataclass,field
from enum import Enum
from lexer import *  # <-- 这里保持导入你现有的 lexer.py
# =================================================================
#  1) AST 节点 (与已有代码合并；若你已定义，可直接覆盖/跳过)
# =================================================================

@dataclass
class ASTNode:
    start_idx: int
    def to_s_expression(self) -> str:
        raise NotImplementedError("to_s_expression must be implemented in subclasses")

# ---------------- Commands (HW3 + HW4) ----------------
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
    lvalue: "LValue"
    def to_s_expression(self) -> str:
        return f'(ReadCmd "{self.filename}" {self.lvalue.to_s_expression()})'

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

# HW4: FnCmd, StructCmd
@dataclass
class FnCmd(Cmd):
    name: str
    bindings: List["Binding"]
    return_type: "TypeNode"
    body: List["Stmt"]

    def to_s_expression(self) -> str:
        # 0) 若无 binding => "(())"
        if not self.bindings:
            param_str = "(())"
        else:
            # 1) 将每个 binding => "(VarLValue a) (StructType a)" 这种对
            # 注意：测试希望最终出现形如 (((VarLValue a) (StructType a) (VarLValue b) (StructType b))) => 3层括号
            pairs = []
            for b in self.bindings:
                lv = b.lvalue.to_s_expression()      # e.g. (VarLValue a)
                ty = b.type_node.to_s_expression()   # e.g. (StructType a)
                # 目标: (VarLValue a) (StructType a)
                pairs.append(f"{lv} {ty}")
            # 多个 binding 用空格拼起来
            joined = " ".join(pairs)  # e.g. "(VarLValue a) (StructType a) (VarLValue b) (StructType b)"

            # 3) 再包一层三重括号 => '(((...)))'
            param_str = f"(({joined}))"  # 如果作业只要双括号，就 "((" + joined + "))"; 如果要三重，就 "(((" + joined + ')))'

        # 4) return type
        ret_s = self.return_type.to_s_expression()

        # 5) body => space separated
        if not self.body:
            # 无 body => (FnCmd f (()) (IntType))
            return f"(FnCmd {self.name} {param_str} {ret_s})"
        else:
            # 有 body => (FnCmd f (()) (IntType) (AssertStmt...) (ReturnStmt...))
            body_s = " ".join(stmt.to_s_expression() for stmt in self.body)
            return f"(FnCmd {self.name} {param_str} {ret_s} {body_s})"


@dataclass
class StructCmd(Cmd):
    """
    改为存一个 field_pairs: List[Tuple[str, TypeNode]]
    而不使用 StructField 对象。输出时拼成(StructCmd name f1Name f1Type f2Name f2Type ...)
    """
    name: str
    field_pairs: List[Tuple[str, "TypeNode"]]

    def to_s_expression(self) -> str:
        # 如果没有字段 => (StructCmd name)
        if len(self.field_pairs) == 0:
            return f"(StructCmd {self.name})"

        # 如果有字段 => 依次拼接
        # 例如: f1Name (type1) f2Name (type2)
        pairs_s = " ".join(
            f"{fname} {ftype.to_s_expression()}"
            for (fname, ftype) in self.field_pairs
        )
        return f"(StructCmd {self.name} {pairs_s})"

# ---------------- Expressions ----------------
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
        # 保持你HW3的做法 => 转为 int 输出
        return f"(FloatExpr {int(self.value)})"

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
        if self.elements:
            return f"(ArrayLiteralExpr {' '.join(e.to_s_expression() for e in self.elements)})"
        else:
            return "(ArrayLiteralExpr)"

# HW4: 新增的表达式
@dataclass
class VoidExpr(Expr):
    def to_s_expression(self) -> str:
        return "(VoidExpr)"

@dataclass
class StructLiteralExpr(Expr):
    struct_name: str
    fields: List[Expr]
    def to_s_expression(self) -> str:
        if len(self.fields) == 0:
            # 无字段 => 不要多余空格
            return f"(StructLiteralExpr {self.struct_name})"
        else:
            fields_s = " ".join(f.to_s_expression() for f in self.fields)
            return f"(StructLiteralExpr {self.struct_name} {fields_s})"

@dataclass
class DotExpr(Expr):
    left: Expr
    right: str
    def to_s_expression(self) -> str:
        return f"(DotExpr {self.left.to_s_expression()} {self.right})"
    
@dataclass
class ArrayIndexExpr(Expr):
    array: Expr
    indexes: List[Expr] = field(default_factory=list)  # 支持多个索引

    def to_s_expression(self) -> str:
        if not self.indexes:
            return f"(ArrayIndexExpr {self.array.to_s_expression()})"
        else:
            indexes_s = " ".join(i.to_s_expression() for i in self.indexes)
            return f"(ArrayIndexExpr {self.array.to_s_expression()} {indexes_s})"



        
@dataclass
class CallExpr(Expr):
    function: Expr
    arguments: List[Expr]

    def to_s_expression(self) -> str:
        # 如果 function 是 VarExpr => 只打印它的 name
        if isinstance(self.function, VarExpr):
            fn_part = self.function.name
        else:
            fn_part = self.function.to_s_expression()

        if not self.arguments:
            # 无参
            return f"(CallExpr {fn_part})"
        else:
            # 有参
            args_s = " ".join(a.to_s_expression() for a in self.arguments)
            return f"(CallExpr {fn_part} {args_s})"

# ---------------- LValue ----------------
@dataclass
class LValue(ASTNode):
    pass

@dataclass
class LetCmd(Cmd):
    lvalue: LValue
    value: Expr
    def to_s_expression(self) -> str:
        return f"(LetCmd {self.lvalue.to_s_expression()} {self.value.to_s_expression()})"

@dataclass
class VarLValue(LValue):
    name: str
    def to_s_expression(self) -> str:
        return f"(VarLValue {self.name})"

@dataclass
class ArrayLValue(LValue):
    array: str
    indices: List[str]

    def to_s_expression(self) -> str:
        idx_str = " ".join(self.indices)
        return f"(ArrayLValue {self.array} {idx_str})"

# ---------------- Statements (HW4) ----------------
@dataclass
class Stmt(ASTNode):
    pass

@dataclass
class LetStmt(Stmt):
    lvalue: LValue
    expr: Expr
    def to_s_expression(self) -> str:
        return f"(LetStmt {self.lvalue.to_s_expression()} {self.expr.to_s_expression()})"

@dataclass
class AssertStmt(Stmt):
    expr: Expr
    message: str
    def to_s_expression(self) -> str:
        return f'(AssertStmt {self.expr.to_s_expression()} "{self.message}")'

@dataclass
class ReturnStmt(Stmt):
    expr: Expr
    def to_s_expression(self) -> str:
        return f"(ReturnStmt {self.expr.to_s_expression()})"

# ---------------- 类型 (TypeNode) ----------------
@dataclass
class TypeNode(ASTNode):
    pass

@dataclass
class IntType(TypeNode):
    def to_s_expression(self) -> str:
        return "(IntType)"

@dataclass
class FloatType(TypeNode):
    def to_s_expression(self) -> str:
        return "(FloatType)"

@dataclass
class BoolType(TypeNode):
    def to_s_expression(self) -> str:
        return "(BoolType)"

@dataclass
class VoidType(TypeNode):
    def to_s_expression(self) -> str:
        return "(VoidType)"

@dataclass
class StructType(TypeNode):
    name: str
    def to_s_expression(self) -> str:
        return f"(StructType {self.name})"
    
@dataclass
class ArrayType(TypeNode):
    element_type: TypeNode
    dimension: int = 1
    def to_s_expression(self) -> str:

        return f"(ArrayType {self.element_type.to_s_expression()} {self.dimension})"


# ---------------- Binding----------------
@dataclass
class Binding(ASTNode):
    lvalue: LValue
    type_node: TypeNode
    def to_s_expression(self) -> str:
        return f"(Binding {self.lvalue.to_s_expression()} {self.type_node.to_s_expression()})"


# ----------------HW5 ----------------
class Binop(Enum):
    PLUS = '+'
    MINUS = '-'
    MULT = '*'
    DIV = '/'
    MOD = '%'
    LT = '<'
    GT = '>'
    LE = '<='
    GE = '>='
    EQ = '=='
    NE = '!='
    AND = '&&'
    OR = '||'

class Unop(Enum):
    NEG = '-'   # 负号
    NOT = '!'   # 逻辑非

@dataclass
class UnopExpr(Expr):
    op: Unop
    operand: Expr
    def to_s_expression(self) -> str:
        return f"(UnopExpr {self.op.value} {self.operand.to_s_expression()})"

@dataclass
class BinopExpr(Expr):
    left: Expr
    op: Binop
    right: Expr
    def to_s_expression(self) -> str:
        return f"(BinopExpr {self.left.to_s_expression()} {self.op.value} {self.right.to_s_expression()})"

@dataclass
class IfExpr(Expr):
    cond: Expr
    then_branch: Expr
    else_branch: Expr
    def to_s_expression(self) -> str:
        return f"(IfExpr {self.cond.to_s_expression()} {self.then_branch.to_s_expression()} {self.else_branch.to_s_expression()})"


@dataclass
class ArrayLoopExpr(Expr):
    bounds: List[Tuple[str, Expr]]
    body: Expr
    def to_s_expression(self) -> str:
        if self.bounds:
            bounds_s = " ".join(f"{var} {expr.to_s_expression()}" for var, expr in self.bounds)
            return f"(ArrayLoopExpr {bounds_s} {self.body.to_s_expression()})"
        else:
            return f"(ArrayLoopExpr {self.body.to_s_expression()})"

@dataclass
class SumLoopExpr(Expr):
    bounds: List[Tuple[str, Expr]]
    body: Expr
    def to_s_expression(self) -> str:
        if self.bounds:
            bounds_s = " ".join(f"{var} {expr.to_s_expression()}" for var, expr in self.bounds)
            return f"(SumLoopExpr {bounds_s} {self.body.to_s_expression()})"
        else:
            return f"(SumLoopExpr {self.body.to_s_expression()})"

# =================================================================
#  2) Parser 类 — 在你的原代码基础上做【最小改动】，以支持HW4语法
# =================================================================
class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current_token(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def advance(self):
        self.pos += 1

    def match(self, expected_type):
        cur = self.current_token()
        if isinstance(cur, expected_type):
            self.advance()
            return cur
        else:
            raise SyntaxError(f"Expected {expected_type}, got {type(cur)} at pos={self.pos}")


    # --------------------------------------------------
    #  parse_program (HW3 主入口) - 保持原逻辑
    # --------------------------------------------------
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
            # 再跳过结尾的 NEWLINE
            while isinstance(self.current_token(), NEWLINE):
                self.advance()
        return commands

    # --------------------------------------------------
    #  parse_cmd - 与HW3保持一致 + 增加 fn / struct
    # --------------------------------------------------
    def parse_cmd(self) -> Cmd:
        current = self.current_token()
    
        # ✅ Parse a single command
        if isinstance(current, LET):
            cmd = self.parse_let_cmd()
        elif isinstance(current, PRINT):
            cmd = self.parse_print_cmd()
        elif isinstance(current, READ):
            cmd = self.parse_read_cmd()
        elif isinstance(current, WRITE):
            cmd = self.parse_write_cmd()
        elif isinstance(current, ASSERT):
            cmd = self.parse_assert_cmd()
        elif isinstance(current, SHOW):
            cmd = self.parse_show_cmd()
        elif isinstance(current, TIME):
            cmd = self.parse_time_cmd()
        elif isinstance(current, FN):
            cmd = self.parse_fn_cmd()
        elif isinstance(current, STRUCT):
            cmd = self.parse_struct_cmd()
        else:
            raise SyntaxError(f"Unexpected command: {current}")
    
        # ✅ Check for another command **before returning**
        next_token = self.current_token()
        if isinstance(next_token, (PRINT, SHOW, READ, WRITE, ASSERT, LET, TIME, FN, STRUCT)):
            raise SyntaxError("Commands must be on separate lines.")
    
        return cmd  # ✅ Now, `cmd` is always definedparse_cmd(self) -> Cmd:
        
    # ---------------- HW3: let_cmd ----------------
    def parse_let_cmd(self) -> LetCmd:
        self.match(LET)
        lval = self.parse_lvalue()
        self.match(EQUALS)
        rhs = self.parse_expr()
        return LetCmd(start_idx=self.pos, lvalue=lval, value=rhs)

    # ---------------- lvalue (包含 arrayLValue) ----------------
    def parse_lvalue(self) -> LValue:
        token = self.match(VARIABLE)
        var_name = token.name
        indices = []
        # 如果出现 [ ... ] 则解析数组下标
        while isinstance(self.current_token(), LSQUARE):
            self.match(LSQUARE)

        # 先解析第一个索引
            idx_token = self.match(VARIABLE)
            current_indices = [idx_token.name]

        # 如果还有逗号就继续
            while isinstance(self.current_token(), COMMA):
                self.match(COMMA)
                next_idx_token = self.match(VARIABLE)
                current_indices.append(next_idx_token.name)

            self.match(RSQUARE)
        # 把当前 bracket 里的所有索引 append 到 indices
            indices.extend(current_indices)

        if indices:
        # 如果我们收集到1或多个索引 => ArrayLValue
            return ArrayLValue(start_idx=token.start_idx, array=var_name, indices=indices)
        else:
        # 没有索引 => 普通 VarLValue
            return VarLValue(start_idx=token.start_idx, name=var_name)

    # ---------------- parse_print_cmd 等 (HW3) ----------------
    def parse_print_cmd(self) -> PrintCmd:
        self.match(PRINT)
        msg = self.match(STRING).value
        return PrintCmd(start_idx=self.pos, message=msg)

    def parse_read_cmd(self) -> ReadCmd:
        self.match(READ)
    # 跳过 'image' (如果存在)
        if isinstance(self.current_token(), IMAGE):
            self.advance()
        filename = self.match(STRING).value
        self.match(TO)
        lval = self.parse_lvalue()   # 使用支持数组下标的 lvalue 解析器
        return ReadCmd(start_idx=self.pos, filename=filename, lvalue=lval)

    def parse_write_cmd(self) -> WriteCmd:
        self.match(WRITE)
        # 跳过 'image' (如果存在)
        if isinstance(self.current_token(), IMAGE):
            self.advance()
        expr = self.parse_expr()
        self.match(TO)
        filename = self.match(STRING).value
        return WriteCmd(start_idx=self.pos, expr=expr, filename=filename)

    def parse_assert_cmd(self) -> AssertCmd:
        self.match(ASSERT)
        expr = self.parse_expr()
        self.match(COMMA)
        msg = self.match(STRING).value
        return AssertCmd(start_idx=self.pos, expr=expr, message=msg)

    def parse_show_cmd(self) -> ShowCmd:
        self.match(SHOW)
        expr = self.parse_expr()
        return ShowCmd(start_idx=self.pos, expr=expr)

    def parse_time_cmd(self) -> TimeCmd:
        self.match(TIME)
        cmd = self.parse_cmd()
        if isinstance(self.current_token(), PRINT) or isinstance(self.current_token(), TIME):
            raise SyntaxError("Invalid syntax: 'time' must be followed by exactly one command.")
        return TimeCmd(start_idx=self.pos, cmd=cmd)

    # ---------------- parse_mixed_var_expr (旧需求) ----------------
    def parse_mixed_var_expr(self) -> VarExpr:
        current = self.current_token()
        parts = []
        while isinstance(current, (VARIABLE, FLOATVAL, DOT)):
            if isinstance(current, VARIABLE):
                parts.append(current.name)
            elif isinstance(current, FLOATVAL):
                parts.append(str(current.value))  # 例如 "123.0"
            elif isinstance(current, DOT):
                parts.append(".")
            self.advance()
            current = self.current_token()
        name = "".join(parts)
        if not name.replace("_", "").replace(".", "").isalnum():
            raise SyntaxError(f"Invalid mixed variable name: {name}")
        return VarExpr(start_idx=self.pos, name=name)

    # ========================================================================
    #  parse_expr: 在 HW3 基础上扩展 HW4 表达式 (void, struct literal, (), call, dot, index, etc.)
    # ========================================================================


    # ========================================================================
    #  这里放的是HW5 在优先级结束再回到之前hw的东西
    # ========================================================================

    # ─────────── 表达式解析入口 ───────────
    def parse_expr(self) -> Expr:
        return self.parse_expr_bool()

    # Level 6: 处理布尔运算 && 和 ||
    def parse_expr_bool(self) -> Expr:
        expr = self.parse_expr_comp()
        while isinstance(self.current_token(), OP) and self.current_token().symbol in ('&&', '||'):
            op_token = self.current_token()
            self.advance()
            right = self.parse_expr_comp()
            op = Binop.AND if op_token.symbol == '&&' else Binop.OR
            expr = BinopExpr(start_idx=expr.start_idx, left=expr, op=op, right=right)
        return expr

    # Level 5: 处理比较运算 (<, >, <=, >=, ==, !=)
    def parse_expr_comp(self) -> Expr:
        expr = self.parse_expr_add()
        while True:
            current = self.current_token()
            op = None
            if isinstance(current, OP) and current.symbol in ('<', '>', '<=', '>=', '=='):
                op_symbol = current.symbol
                self.advance()
                if op_symbol == '<':
                    op = Binop.LT
                elif op_symbol == '>':
                    op = Binop.GT
                elif op_symbol == '<=':
                    op = Binop.LE
                elif op_symbol == '>=':
                    op = Binop.GE
                elif op_symbol == '==':
                    op = Binop.EQ
            # 处理 "!="：lexer把 "!=" 分解为 OP("!") + EQUALS
            elif isinstance(current, OP) and current.symbol == '!' and isinstance(self._peek_next(), EQUALS):
                self.advance()  # 消耗 '!'
                self.advance()  # 消耗 EQUALS
                op = Binop.NE
            else:
                break
            right = self.parse_expr_add()
            expr = BinopExpr(start_idx=expr.start_idx, left=expr, op=op, right=right)
        return expr

    # Level 4: 处理加法、减法
    def parse_expr_add(self) -> Expr:
        expr = self.parse_expr_mul()
        while isinstance(self.current_token(), OP) and self.current_token().symbol in ('+', '-'):
            op_token = self.current_token()
            self.advance()
            right = self.parse_expr_mul()
            op = Binop.PLUS if op_token.symbol == '+' else Binop.MINUS
            expr = BinopExpr(start_idx=expr.start_idx, left=expr, op=op, right=right)
        return expr

    # Level 3: 处理乘法、除法、取模
    def parse_expr_mul(self) -> Expr:
        expr = self.parse_expr_unary()
        while isinstance(self.current_token(), OP) and self.current_token().symbol in ('*', '/', '%'):
            op_token = self.current_token()
            self.advance()
            right = self.parse_expr_unary()
            if op_token.symbol == '*':
                op = Binop.MULT
            elif op_token.symbol == '/':
                op = Binop.DIV
            elif op_token.symbol == '%':
                op = Binop.MOD
            expr = BinopExpr(start_idx=expr.start_idx, left=expr, op=op, right=right)
        return expr

    # Level 2: 处理一元前缀运算符 '-' 和 '!'
    def parse_expr_unary(self) -> Expr:
        current = self.current_token()
        if isinstance(current, OP) and current.symbol in ('-', '!'):
            op_symbol = current.symbol
            self.advance()
            # 递归调用 parse_expr_unary() 支持连续一元运算符
            operand = self.parse_expr_unary()
    
            if op_symbol == '-' and isinstance(operand, (TrueExpr, FalseExpr, VoidExpr)):
                raise SyntaxError(f"Invalid use of '-' on {operand}")
            
            op = Unop.NEG if op_symbol == '-' else Unop.NOT
            return UnopExpr(start_idx=operand.start_idx, op=op, operand=operand)
        else:
            # 若不是 '-' 或 '!'，进入基本表达式层（包括前缀关键字 if, array, sum）
            return self.parse_expr_basic()

    # Level 1: 处理前缀关键字 if, array, sum；否则调用后缀解析
    def parse_expr_basic(self) -> Expr:
        current = self.current_token()
        if isinstance(current, IF):
            self.match(IF)
            cond = self.parse_expr()
            self.match(THEN)
            then_expr = self.parse_expr()
            self.match(ELSE)
            else_expr = self.parse_expr()
            return IfExpr(start_idx=cond.start_idx, cond=cond, then_branch=then_expr, else_branch=else_expr)
        elif isinstance(current, ARRAY):
            self.match(ARRAY)
            self.match(LSQUARE)
            bounds = self.parse_loop_bounds()
            self.match(RSQUARE)
            # 调用 parse_expr() 解析整个操作数，确保诸如 "-a" 或 "a+b"能被整体解析
            body = self.parse_expr()
            return ArrayLoopExpr(start_idx=body.start_idx, bounds=bounds, body=body)
        elif isinstance(current, SUM):
            self.match(SUM)
            self.match(LSQUARE)
            bounds = self.parse_loop_bounds()
            self.match(RSQUARE)
            body = self.parse_expr()
            return SumLoopExpr(start_idx=body.start_idx, bounds=bounds, body=body)
        else:
            return self.parse_expr_postfix()

    # 后缀层：处理成员访问、下标索引、函数调用
    def parse_expr_postfix(self) -> Expr:
        expr = self.parse_expr_primary()
        while True:
            current = self.current_token()
            if isinstance(current, DOT):
                self.match(DOT)
                field_tok = self.match(VARIABLE)

                # if isinstance(expr, (TrueExpr, FalseExpr, VoidExpr)):
                #     raise SyntaxError(f"Invalid use of '.' on {expr}")
                expr = DotExpr(start_idx=expr.start_idx, left=expr, right=field_tok.name)
            elif isinstance(current, LSQUARE):
                self.match(LSQUARE)
                args = []
                if not isinstance(self.current_token(), RSQUARE):
                    args.append(self.parse_expr())
                    while isinstance(self.current_token(), COMMA):
                        self.match(COMMA)
                        args.append(self.parse_expr())
                self.match(RSQUARE)
                expr = ArrayIndexExpr(start_idx=expr.start_idx, array=expr, indexes=args)
            elif isinstance(current, LPAREN):
                self.match(LPAREN)
                args = []
                if not isinstance(self.current_token(), RPAREN):
                    args.append(self.parse_expr())
                    while isinstance(self.current_token(), COMMA):
                        self.match(COMMA)
                        args.append(self.parse_expr())
                self.match(RPAREN)
                expr = CallExpr(start_idx=expr.start_idx, function=expr, arguments=args)
            else:
                break
        return expr

    # Primary 表达式：字面量、变量、括号表达式、数组字面量、结构字面量等
    def parse_expr_primary(self) -> Expr:
        current = self.current_token()
        if isinstance(current, INTVAL):
            return self.parse_int_expr()
        elif isinstance(current, FLOATVAL):
            return self.parse_float_expr()
        elif isinstance(current, TRUE):
            return self.parse_true_expr()
        elif isinstance(current, FALSE):
            return self.parse_false_expr()
        elif isinstance(current, VOID):
            return self.parse_void_expr()
        elif isinstance(current, LSQUARE):
            # 如果以 '[' 开始则解析为数组字面量
            return self.parse_array_literal_expr()
        elif isinstance(current, LPAREN):
            self.match(LPAREN)
            expr = self.parse_expr()
            self.match(RPAREN)
            return expr
        elif isinstance(current, VARIABLE):
            lookahead = self._peek_next()
            if isinstance(lookahead, LCURLY):
                return self.parse_struct_literal_expr()
            else:
                return self.parse_var_expr()
        else:
            raise SyntaxError(f"Unexpected expression: {current}")


    def parse_loop_bounds(self) -> List[Tuple[str, Expr]]:
        bounds = []
        if isinstance(self.current_token(), RSQUARE):
            return bounds
        token = self.match(VARIABLE)
        var_name = token.name
        self.match(COLON)
        expr_bound = self.parse_expr()
        bounds.append((var_name, expr_bound))
        while isinstance(self.current_token(), COMMA):
            self.match(COMMA)
            token = self.match(VARIABLE)
            var_name = token.name
            self.match(COLON)
            expr_bound = self.parse_expr()
            bounds.append((var_name, expr_bound))
        return bounds

    def parse_struct_literal_expr(self) -> StructLiteralExpr:
        # structName { expr1, expr2, ... }
        name_token = self.match(VARIABLE)
        struct_name = name_token.name
        self.match(LCURLY)
        fields = []
        while not isinstance(self.current_token(), RCURLY):
            fields.append(self.parse_expr())
            if isinstance(self.current_token(), COMMA):
                self.advance()
        self.match(RCURLY)
        return StructLiteralExpr(start_idx=self.pos, struct_name=struct_name, fields=fields)

    def parse_void_expr(self) -> VoidExpr:
        self.match(VOID)
        return VoidExpr(start_idx=self.pos)

    def parse_string_expr(self) -> Expr:
        raise SyntaxError("Strings cannot be used as expressions in this grammar.")

    def parse_expr_suffix(self, base: Expr) -> Expr:
        while True:
            curr = self.current_token()
        # .field
            if isinstance(curr, DOT):
                self.advance()
                field_token = self.match(VARIABLE)
                base = DotExpr(start_idx=self.pos, left=base, right=field_token.name)
            # [args] => array index
            elif isinstance(curr, LSQUARE):
                self.advance()
                expr_list = []
                if not isinstance(self.current_token(), RSQUARE):
                    expr_list.append(self.parse_expr())
                    while isinstance(self.current_token(), COMMA):
                        self.match(COMMA)
                        expr_list.append(self.parse_expr())
                self.match(RSQUARE)

            # 直接赋值给 indexes
                base = ArrayIndexExpr(start_idx=self.pos, array=base, indexes=expr_list)
        # (args...) => function call
            elif isinstance(curr, LPAREN):
                self.advance()
                args = []
                if not isinstance(self.current_token(), RPAREN):
                    # 解析第一个实参
                   first = self.parse_expr()
                   first = self.parse_expr_suffix(first)  
                   args.append(first)
                   # 若后面还有逗号 => 继续解析下一个
                   while isinstance(self.current_token(), COMMA):
                        self.match(COMMA)
                        nxt = self.parse_expr()
                        nxt = self.parse_expr_suffix(nxt)
                        args.append(nxt)
                self.match(RPAREN)
                base = CallExpr(start_idx=self.pos, function=base, arguments=args)
            else:
                break
        return base


    # ---------------- parse_int_expr / float_expr / true_expr / false_expr 等 ----------------
    def parse_int_expr(self) -> IntExpr:
        tok = self.match(INTVAL)
        val = tok.value
        if val < -(2**63) or val > (2**63 - 1):
            raise SyntaxError(f"Integer out of 64-bit range: {val}")
        return IntExpr(start_idx=tok.start_idx, value=val)

    def parse_float_expr(self) -> FloatExpr:
        tok = self.match(FLOATVAL)
        return FloatExpr(start_idx=tok.start_idx, value=float(tok.value))

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

    def parse_var_expr(self) -> VarExpr:
        # 与 parse_lvalue 类似，但这里只是创建一个 VarExpr
        tok = self.match(VARIABLE)
        return VarExpr(start_idx=tok.start_idx, name=tok.name)

    def _peek_next(self):
        # 简单查看下一个 token（不前进）
        peek_pos = self.pos + 1
        if peek_pos < len(self.tokens):
            return self.tokens[peek_pos]
        return None

    # =====================================================================
    # HW4: parse_fn_cmd, parse_struct_cmd, parse_stmt, parse_binding, parse_type
    #   这些你已有基础，下面仅做参考或保持原样
    # =====================================================================
    def parse_fn_cmd(self) -> FnCmd:
        self.match(FN)
        name_token = self.match(VARIABLE)
        fn_name = name_token.name

        self.match(LPAREN)
        bindings = []
        if not isinstance(self.current_token(), RPAREN):
            bindings.append(self.parse_binding())
            while isinstance(self.current_token(), COMMA):
                self.advance()
                bindings.append(self.parse_binding())
        self.match(RPAREN)
        self.match(COLON)
        ret_type = self.parse_type()
        self.match(LCURLY)
        # 跳过多余换行
        while isinstance(self.current_token(), NEWLINE):
            self.advance()

        body = []
        while not isinstance(self.current_token(), RCURLY):
            s = self.parse_stmt()
            body.append(s)
            while isinstance(self.current_token(), NEWLINE):
                self.advance()

        self.match(RCURLY)
        return FnCmd(start_idx=self.pos, name=fn_name, bindings=bindings, return_type=ret_type, body=body)

    def parse_struct_cmd(self) -> StructCmd:
        """
        解析多字段: struct a { x : int[,]  y : float ... }
        改为存 [(x, ArrayType(IntType,2)), (y, FloatType(...)), ...]
        """
        self.match(STRUCT)
        name_tok = self.match(VARIABLE)
        struct_name = name_tok.name

        self.match(LCURLY)
        # 跳过换行
        while isinstance(self.current_token(), NEWLINE):
            self.advance()

        field_pairs = []  # 存 (fieldName, fieldType)

        # 只要没遇到 RCURLY，就还有字段
        while not isinstance(self.current_token(), RCURLY):
            # 解析一个字段 => varName : type
            var_tok = self.match(VARIABLE)
            field_name = var_tok.name

            self.match(COLON)
            tnode = self.parse_type()

            # 看看是否还有逗号/换行
            # optional: if isinstance(self.current_token(), COMMA):
            #     self.advance()

            field_pairs.append((field_name, tnode))

            # 跳过换行
            while isinstance(self.current_token(), NEWLINE):
                self.advance()

        self.match(RCURLY)

        return StructCmd(
            start_idx=self.pos,
            name=struct_name,
            field_pairs=field_pairs
        )




    def parse_binding(self) -> Binding:
        lv = self.parse_lvalue()
        self.match(COLON)
        t = self.parse_type()
        return Binding(start_idx=self.pos, lvalue=lv, type_node=t)

    def parse_type(self) -> TypeNode:
        cur = self.current_token()
    
    # Parse base type (int, float, bool, struct)
        if isinstance(cur, INT):
            self.advance()
            base = IntType(start_idx=self.pos)
        elif isinstance(cur, FLOAT):
            self.advance()
            base = FloatType(start_idx=self.pos)
        elif isinstance(cur, BOOL):
            self.advance()
            base = BoolType(start_idx=self.pos)
        elif isinstance(cur, VOID):
            self.advance()
            base = VoidType(start_idx=self.pos)
        elif isinstance(cur, VARIABLE):
            name_ = cur.name
            self.advance()
            base = StructType(start_idx=self.pos, name=name_)
        else:
            raise SyntaxError(f"Unexpected type: {cur}")

    # ✅ Fix: Preserve nesting instead of merging
        while isinstance(self.current_token(), LSQUARE):
            self.match(LSQUARE)
        
            dim = 1
            while isinstance(self.current_token(), COMMA):
                self.advance()
                dim += 1
            self.match(RSQUARE)
        
            # ✅ Wrap previous type inside a new `ArrayType`
            base = ArrayType(start_idx=self.pos, element_type=base, dimension=dim)
        
            # ✅ Debugging Nested Arrays

        return base  # ✅ Returns fully nested `ArrayType`


    def parse_stmt(self) -> Stmt:
        curr = self.current_token()
        if isinstance(curr, LET):
            return self.parse_let_stmt()
        elif isinstance(curr, ASSERT):
            return self.parse_assert_stmt()
        elif isinstance(curr, RETURN):
            return self.parse_return_stmt()
        else:
            raise SyntaxError(f"Unexpected statement: {curr}")

    def parse_let_stmt(self) -> LetStmt:
        self.match(LET)
        lv = self.parse_lvalue()
        self.match(EQUALS)
        e = self.parse_expr()
        return LetStmt(start_idx=self.pos, lvalue=lv, expr=e)

    def parse_assert_stmt(self) -> AssertStmt:
        self.match(ASSERT)
        e = self.parse_expr()
        self.match(COMMA)
        msg = self.match(STRING).value
        return AssertStmt(start_idx=self.pos, expr=e, message=msg)

    def parse_return_stmt(self) -> ReturnStmt:
        self.match(RETURN)
        e = self.parse_expr()
        return ReturnStmt(start_idx=self.pos, expr=e)

