from typing import List, Union , Optional
from dataclasses import dataclass,field
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
        elif isinstance(current, FN):
            return self.parse_fn_cmd()
        elif isinstance(current, STRUCT):
            return self.parse_struct_cmd()
        else:
            raise SyntaxError(f"Unexpected command: {current}")

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
        var_name = self.parse_mixed_var_expr().name
        return ReadCmd(start_idx=self.pos, filename=filename, var_name=var_name)

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
    def parse_expr(self) -> Expr:
        current = self.current_token()

        # 1) 整数
        if isinstance(current, INTVAL):
            expr = self.parse_int_expr()
        # 2) 浮点数
        elif isinstance(current, FLOATVAL):
            expr = self.parse_float_expr()
        # 3) true / false
        elif isinstance(current, TRUE):
            expr = self.parse_true_expr()
        elif isinstance(current, FALSE):
            expr = self.parse_false_expr()
        # 4) void
        elif isinstance(current, VOID):
            expr = self.parse_void_expr()
        # 5) [ ... ] => array literal
        elif isinstance(current, LSQUARE):
            expr = self.parse_array_literal_expr()
        # 6) ( expr ) => parenthesized
        elif isinstance(current, LPAREN):
            self.match(LPAREN)
            inner = self.parse_expr()
            self.match(RPAREN)
            expr = inner
        # 7) variable 或 struct literal?
        elif isinstance(current, VARIABLE):
            lookahead = self._peek_next()
            if isinstance(lookahead, LCURLY):
                expr = self.parse_struct_literal_expr()
            else:
                base = self.parse_var_expr()
                expr = self.parse_expr_suffix(base)
    # 8) dot => (极少见的情况：一开始就是 '.')
        elif isinstance(current, DOT):
            base = self.parse_mixed_var_expr()
            expr = base  # 不做后缀处理
    # 9) string => 你曾尝试 parse_string_expr，如果语法不支持就报错
        elif isinstance(current, STRING):
            expr = self.parse_string_expr()
        else:
            raise SyntaxError(f"Unexpected expression: {current}")

    # # 关键：对 expr 再做一次后缀解析（除了已经在分支内处理的情况）
    #     if isinstance(expr, (VarExpr, ArrayIndexExpr, CallExpr, DotExpr, StructLiteralExpr)):
    #         expr = self.parse_expr_suffix(expr)

        expr = self.parse_expr_suffix(expr)
        return expr


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
        """
        假设可以: int, float, structName, plus array [..], multi-d
        """
        cur = self.current_token()
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
            # 解析 struct Type
            name_ = cur.name
            self.advance()
            base = StructType(start_idx=self.pos, name=name_)
        else:
            raise SyntaxError(f"Unexpected type: {cur}")

        # 看看是否有 [..] => multi-dim
        total_dim = 0
        while isinstance(self.current_token(), LSQUARE):
            self.match(LSQUARE)
            dim = 1
            while isinstance(self.current_token(), COMMA):
                self.advance()
                dim += 1
            total_dim += dim
            self.match(RSQUARE)

        if total_dim > 0:
            return ArrayType(start_idx=self.pos, element_type=base, dimension=total_dim)
        else:
            return base


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
