from typing import List, Dict, Tuple, Optional
from parser import *  
from enum import Enum
from dataclasses import dataclass
RESERVED = {"argnum", "args", "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "exp", "log", "sqrt", "pow", "to_int", "to_float"}
# 环境类：同时管理变量/函数绑定和结构体定义
class Env:
    def __init__(self, vars: Dict[str, TypeNode] = None, structs: Dict[str, Dict[str, TypeNode]] = None):
        self.vars = vars if vars is not None else {}
        self.structs = structs if structs is not None else {}
    def copy(self):
        return Env(vars=self.vars.copy(), structs=self.structs)

# 新的函数类型
@dataclass
class FnType(TypeNode):
    param_types: List[TypeNode]
    return_type: TypeNode
    def to_s_expression(self) -> str:
        params_s = " ".join(p.to_s_expression() for p in self.param_types)
        return f"(FnType ({params_s}) {self.return_type.to_s_expression()})"

def types_equal(t1: TypeNode, t2: TypeNode) -> bool:
    if type(t1) != type(t2):
        return False
    if isinstance(t1, (IntType, FloatType, BoolType, VoidType)):
        return True
    if isinstance(t1, StructType):
        return t1.name == t2.name
    if isinstance(t1, ArrayType):
        return types_equal(t1.element_type, t2.element_type) and t1.dimension == t2.dimension
    if isinstance(t1, FnType):
        if len(t1.param_types) != len(t2.param_types):
            return False
        for pt1, pt2 in zip(t1.param_types, t2.param_types):
            if not types_equal(pt1, pt2):
                return False
        return types_equal(t1.return_type, t2.return_type)
    return False

# --- 表达式类型检查 ---
def type_of_expr(expr: Expr, env: Env) -> TypeNode:
    if isinstance(expr, ArrayLValue):
        # 将数组左值视作变量引用，取其 array 字段
        new_expr = VarExpr(start_idx=expr.start_idx, name=expr.array)
        return type_of_expr(new_expr, env)
    if isinstance(expr, IntExpr):
        rt = IntType(start_idx=expr.start_idx)
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, FloatExpr):
        rt = FloatType(start_idx=expr.start_idx)
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, TrueExpr) or isinstance(expr, FalseExpr):
        rt = BoolType(start_idx=expr.start_idx)
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, VoidExpr):
        rt = VoidType(start_idx=expr.start_idx)
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, ArrayLiteralExpr):
        if not expr.elements:
            raise TypeError("Empty array literal is ambiguous")
        first_t = type_of_expr(expr.elements[0], env)
        for subexpr in expr.elements[1:]:
            t = type_of_expr(subexpr, env)
            if not types_equal(first_t, t):
                raise TypeError("Array literal elements have mismatched types")
        rt = ArrayType(start_idx=expr.start_idx, element_type=first_t, dimension=1)
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, StructLiteralExpr):
        if expr.struct_name not in env.structs:
            raise TypeError(f"Undefined struct type: {expr.struct_name}")
        struct_def = env.structs[expr.struct_name]
        fields = expr.fields or []
        if len(fields) != len(struct_def):
            raise TypeError(f"Struct literal for {expr.struct_name} has incorrect number of fields")
        for ((fname, ftype), field_expr) in zip(struct_def.items(), fields):
            t = type_of_expr(field_expr, env)
            if not types_equal(t, ftype):
                raise TypeError(f"Field '{fname}' expected {ftype.to_s_expression()}, got {t.to_s_expression()}")
        rt = StructType(start_idx=expr.start_idx, name=expr.struct_name)
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, DotExpr):
        base_t = type_of_expr(expr.left, env)
        if not isinstance(base_t, StructType):
            raise TypeError("Dot operator applied to non-struct type")
        if base_t.name not in env.structs:
            raise TypeError(f"Undefined struct type: {base_t.name}")
        struct_def = env.structs[base_t.name]
        if expr.right not in struct_def:
            raise TypeError(f"Struct {base_t.name} has no field '{expr.right}'")
        rt = struct_def[expr.right]
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, ArrayIndexExpr):
        base_t = type_of_expr(expr.array, env)
        if not isinstance(base_t, ArrayType):
            raise TypeError("Indexing applied to non-array type")
        for idx_expr in expr.indexes:
            idx_t = type_of_expr(idx_expr, env)
            if not isinstance(idx_t, IntType):
                raise TypeError("Array index must be of type int")
        remaining = base_t.dimension - len(expr.indexes)
        if remaining < 0:
            raise TypeError("Too many indices for array")
        if remaining == 0:
            rt = base_t.element_type
        else:
            rt = ArrayType(start_idx=expr.start_idx, element_type=base_t.element_type, dimension=remaining)
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, UnopExpr):
        operand_t = type_of_expr(expr.operand, env)
        if expr.op == Unop.NEG:
            if not (isinstance(operand_t, IntType) or isinstance(operand_t, FloatType)):
                raise TypeError("Unary '-' requires a numeric type")
            expr.resolved_type = operand_t
            return operand_t
        elif expr.op == Unop.NOT:
            if not isinstance(operand_t, BoolType):
                raise TypeError("Logical '!' requires a bool type")
            rt = BoolType(start_idx=expr.start_idx)
            expr.resolved_type = rt
            return rt
        else:
            raise TypeError("Unknown unary operator")
    elif isinstance(expr, BinopExpr):
        left_t = type_of_expr(expr.left, env)
        right_t = type_of_expr(expr.right, env)
        op = expr.op
        if op in (Binop.PLUS, Binop.MINUS, Binop.MULT, Binop.DIV, Binop.MOD):
            if not (isinstance(left_t, (IntType, FloatType)) and isinstance(right_t, (IntType, FloatType))):
                raise TypeError("Arithmetic operators require numeric types")
            rt = FloatType(start_idx=expr.start_idx) if isinstance(left_t, FloatType) or isinstance(right_t, FloatType) else IntType(start_idx=expr.start_idx)
            expr.resolved_type = rt
            return rt
        elif op in (Binop.LT, Binop.GT, Binop.LE, Binop.GE):
            if not (isinstance(left_t, (IntType, FloatType)) and isinstance(right_t, (IntType, FloatType))):
                raise TypeError("Comparison operators require numeric types")
            rt = BoolType(start_idx=expr.start_idx)
            expr.resolved_type = rt
            return rt
        elif op in (Binop.EQ, Binop.NE):
            if not types_equal(left_t, right_t):
                raise TypeError("Equality operators require operands of the same type")
            rt = BoolType(start_idx=expr.start_idx)
            expr.resolved_type = rt
            return rt
        elif op in (Binop.AND, Binop.OR):
            if not (isinstance(left_t, BoolType) and isinstance(right_t, BoolType)):
                raise TypeError("Boolean operators require bool types")
            rt = BoolType(start_idx=expr.start_idx)
            expr.resolved_type = rt
            return rt
        else:
            raise TypeError("Unknown binary operator")
    elif isinstance(expr, IfExpr):
        cond_t = type_of_expr(expr.cond, env)
        if not isinstance(cond_t, BoolType):
            raise TypeError("If condition must be bool")
        then_t = type_of_expr(expr.then_branch, env)
        else_t = type_of_expr(expr.else_branch, env)
        if not types_equal(then_t, else_t):
            raise TypeError("Then and else branches of if must have the same type")
        expr.resolved_type = then_t
        return then_t
    elif isinstance(expr, ArrayLoopExpr):
        if len(expr.bounds) == 0:
            raise TypeError("ArrayLoopExpr must have at least one bound")
        local_env = env.copy()
        for var, bound_expr in expr.bounds:
            bound_t = type_of_expr(bound_expr, env)
            if not isinstance(bound_t, IntType):
                raise TypeError("Loop bound must be int")
            local_env.vars[var] = IntType(start_idx=expr.start_idx)
        body_t = type_of_expr(expr.body, local_env)
        rt = ArrayType(start_idx=expr.start_idx, element_type=body_t, dimension=len(expr.bounds))
        expr.resolved_type = rt
        return rt
    elif isinstance(expr, SumLoopExpr):
        if len(expr.bounds) == 0:
            raise TypeError("SumLoopExpr must have at least one bound")
        local_env = env.copy()
        for var, bound_expr in expr.bounds:
            bound_t = type_of_expr(bound_expr, env)
            if not isinstance(bound_t, IntType):
                raise TypeError("Loop bound must be int")
            local_env.vars[var] = IntType(start_idx=expr.start_idx)
        body_t = type_of_expr(expr.body, local_env)
        if not (isinstance(body_t, IntType) or isinstance(body_t, FloatType)):
            raise TypeError("SumLoopExpr body must be numeric")
        expr.resolved_type = body_t
        return body_t

    elif isinstance(expr, VarExpr):
        if expr.name in env.vars:
            t = env.vars[expr.name]
            expr.resolved_type = t
            return t
        else:
            raise TypeError(f"Undefined variable: {expr.name}")
    elif isinstance(expr, CallExpr):
        fn_type = type_of_expr(expr.function, env)
        if not isinstance(fn_type, FnType):
            raise TypeError("Attempted to call a non-function")
        if len(expr.arguments) != len(fn_type.param_types):
            raise TypeError("Incorrect number of arguments in function call")
        for arg_expr, param_type in zip(expr.arguments, fn_type.param_types):
            arg_type = type_of_expr(arg_expr, env)
            if not types_equal(arg_type, param_type):
                raise TypeError("Function argument type mismatch")
        rt = fn_type.return_type
        expr.resolved_type = rt
        return rt
    else:
        raise TypeError(f"Type checking not implemented for node type: {type(expr)}")


# --- 语句类型检查 ---
def typecheck_stmt(stmt: Stmt, env: Env, expected_return: Optional[TypeNode] = None) -> None:
    if isinstance(stmt, LetStmt):
        t = type_of_expr(stmt.expr, env)
        stmt.expr.resolved_type = t
        if isinstance(stmt.lvalue, VarLValue):
            env.vars[stmt.lvalue.name] = t
        elif isinstance(stmt.lvalue, ArrayLValue):
            var_name = stmt.lvalue.array
            if var_name not in env.vars:
                env.vars[var_name] = t
            else:
                existing = env.vars[var_name]
                if not types_equal(existing, t):
                    raise TypeError("Array assignment type mismatch")
            for idx in stmt.lvalue.indices:
                if idx not in env.vars:
                    env.vars[idx] = IntType(start_idx=stmt.start_idx)
    elif isinstance(stmt, AssertStmt):
        t = type_of_expr(stmt.expr, env)
        if not isinstance(t, BoolType):
            raise TypeError("Assert statement expression must be bool")
        # 允许空字符串作为错误消息，不再拒绝
    elif isinstance(stmt, ReturnStmt):
        t = type_of_expr(stmt.expr, env)
        if not types_equal(t, expected_return):
            raise TypeError("Return statement type does not match function return type")
    else:
        raise TypeError(f"Type checking not implemented for statement type: {type(stmt)}")


def typecheck_command(cmd: Cmd, env: Env) -> None:
    if isinstance(cmd, ShowCmd):
        t = type_of_expr(cmd.expr, env)
        cmd.expr.resolved_type = t
    elif isinstance(cmd, LetCmd):
        t = type_of_expr(cmd.value, env)
        cmd.value.resolved_type = t
        if isinstance(cmd.lvalue, VarLValue):
            env.vars[cmd.lvalue.name] = t
        elif isinstance(cmd.lvalue, ArrayLValue):
            var_name = cmd.lvalue.array
            if var_name not in env.vars:
                env.vars[var_name] = t
            else:
                existing = env.vars[var_name]
                if not types_equal(existing, t):
                    raise TypeError("Array assignment type mismatch")
            for idx in cmd.lvalue.indices:
                if idx not in env.vars:
                    env.vars[idx] = IntType(start_idx=cmd.start_idx)
    elif isinstance(cmd, AssertCmd):
        t = type_of_expr(cmd.expr, env)
        if not isinstance(t, BoolType):
            raise TypeError("Assert command expression must be bool")
        # 同样允许空字符串作为错误消息
    elif isinstance(cmd, ReadCmd):
        if isinstance(cmd.lvalue, VarLValue):
            if cmd.lvalue.name in RESERVED:
                raise TypeError(f"Cannot use reserved variable {cmd.lvalue.name} for read")
            env.vars[cmd.lvalue.name] = ArrayType(start_idx=cmd.start_idx, 
                element_type=StructType(start_idx=cmd.start_idx, name="rgba"), dimension=2)
        elif isinstance(cmd.lvalue, ArrayLValue):
            if cmd.lvalue.array in RESERVED:
                raise TypeError(f"Cannot use reserved variable {cmd.lvalue.array} for read")
            env.vars[cmd.lvalue.array] = ArrayType(start_idx=cmd.start_idx, 
                element_type=StructType(start_idx=cmd.start_idx, name="rgba"), dimension=2)
            for idx in cmd.lvalue.indices:
                if idx not in env.vars:
                    env.vars[idx] = IntType(start_idx=cmd.start_idx)
    elif isinstance(cmd, WriteCmd):
        t = type_of_expr(cmd.expr, env)
        cmd.expr.resolved_type = t
    elif isinstance(cmd, TimeCmd):
        typecheck_command(cmd.cmd, env)
        if isinstance(cmd.cmd, LetCmd) and isinstance(cmd.cmd.lvalue, VarLValue):
            env.vars[cmd.cmd.lvalue.name] = type_of_expr(cmd.cmd.value, env)

def typecheck_program(cmds: List[Cmd]) -> None:
    global_env = Env(vars={}, structs={})
    # 内置结构体 rgba
    global_env.structs["rgba"] = {
        "r": FloatType(start_idx=0),
        "g": FloatType(start_idx=0),
        "b": FloatType(start_idx=0),
        "a": FloatType(start_idx=0)
    }
    for cmd in cmds:
        if isinstance(cmd, StructCmd):
            fields = {}
            for fname, ftype in cmd.field_pairs:
                fields[fname] = ftype
            global_env.structs[cmd.name] = fields
    # 添加内置变量和函数
    global_env.vars["argnum"] = IntType(start_idx=0)
    global_env.vars["args"] = ArrayType(start_idx=0, element_type=IntType(start_idx=0), dimension=1)
    global_env.vars["sin"]    = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["cos"]    = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["tan"]    = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["asin"]   = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["acos"]   = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["atan"]   = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["atan2"]  = FnType(start_idx=0, param_types=[FloatType(start_idx=0), FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["exp"]    = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["log"]    = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["sqrt"]   = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["pow"]    = FnType(start_idx=0, param_types=[FloatType(start_idx=0), FloatType(start_idx=0)], return_type=FloatType(start_idx=0))
    global_env.vars["to_int"] = FnType(start_idx=0, param_types=[FloatType(start_idx=0)], return_type=IntType(start_idx=0))
    global_env.vars["to_float"] = FnType(start_idx=0, param_types=[IntType(start_idx=0)], return_type=FloatType(start_idx=0))
    
    for cmd in cmds:
        if isinstance(cmd, ShowCmd):
            t = type_of_expr(cmd.expr, global_env)
            cmd.expr.resolved_type = t
        elif isinstance(cmd, LetCmd):
            # 如果目标变量已经声明，则报错
            if isinstance(cmd.lvalue, VarLValue):
                if cmd.lvalue.name in global_env.vars:
                    raise TypeError(f"Duplicate declaration of variable {cmd.lvalue.name}")
                if cmd.lvalue.name in RESERVED:
                    raise TypeError(f"Cannot declare reserved variable {cmd.lvalue.name}")
            elif isinstance(cmd.lvalue, ArrayLValue):
                if cmd.lvalue.array in global_env.vars:
                    raise TypeError(f"Duplicate declaration of variable {cmd.lvalue.array}")
                if cmd.lvalue.array in RESERVED:
                    raise TypeError(f"Cannot declare reserved variable {cmd.lvalue.array}")
            t = type_of_expr(cmd.value, global_env)
            cmd.value.resolved_type = t
            if isinstance(cmd.lvalue, VarLValue):
                global_env.vars[cmd.lvalue.name] = t
            elif isinstance(cmd.lvalue, ArrayLValue):
                global_env.vars[cmd.lvalue.array] = t
                for idx in cmd.lvalue.indices:
                    if idx not in global_env.vars:
                        global_env.vars[idx] = IntType(start_idx=cmd.start_idx)
        elif isinstance(cmd, FnCmd):
            if cmd.name in global_env.vars:
                raise TypeError(f"Duplicate declaration of function {cmd.name}")
            if cmd.name in RESERVED:
                raise TypeError(f"Cannot declare reserved function {cmd.name}")
            param_types = [binding.type_node for binding in cmd.bindings]
            fn_type = FnType(start_idx=cmd.start_idx, param_types=param_types, return_type=cmd.return_type)
            global_env.vars[cmd.name] = fn_type
            local_env = Env(vars=global_env.vars.copy(), structs=global_env.structs)
            for binding in cmd.bindings:
                if isinstance(binding.lvalue, VarLValue):
                    local_env.vars[binding.lvalue.name] = binding.type_node
                elif isinstance(binding.lvalue, ArrayLValue):
                    local_env.vars[binding.lvalue.array] = binding.type_node
                    for idx in binding.lvalue.indices:
                        local_env.vars[idx] = IntType(start_idx=binding.lvalue.start_idx)
                else:
                    raise TypeError("Function parameter must be a variable")
            for stmt in cmd.body:
                typecheck_stmt(stmt, local_env, expected_return=cmd.return_type)
        elif isinstance(cmd, AssertCmd):
            t = type_of_expr(cmd.expr, global_env)
            if not isinstance(t, BoolType):
                raise TypeError("Assert command expression must be bool")
        elif isinstance(cmd, ReadCmd):
            # ReadCmd 目标必须未被声明
            var_name = cmd.lvalue.array if isinstance(cmd.lvalue, ArrayLValue) else cmd.lvalue.name
            if var_name in global_env.vars:
                raise TypeError(f"Duplicate declaration of variable {var_name} in read command")
            if var_name in RESERVED:
                raise TypeError(f"Cannot use reserved variable {var_name} for read")
            if isinstance(cmd.lvalue, VarLValue):
                global_env.vars[cmd.lvalue.name] = ArrayType(start_idx=cmd.start_idx, 
                    element_type=StructType(start_idx=cmd.start_idx, name="rgba"), dimension=2)
            elif isinstance(cmd.lvalue, ArrayLValue):
                global_env.vars[cmd.lvalue.array] = ArrayType(start_idx=cmd.start_idx, 
                    element_type=StructType(start_idx=cmd.start_idx, name="rgba"), dimension=2)
                for idx in cmd.lvalue.indices:
                    if idx not in global_env.vars:
                        global_env.vars[idx] = IntType(start_idx=cmd.start_idx)
        elif isinstance(cmd, WriteCmd):
            typecheck_command(cmd, global_env)
        elif isinstance(cmd, TimeCmd):
            typecheck_command(cmd, global_env)
    return



def annotate_expr(exp: Expr) -> str:
    if isinstance(exp, IntExpr):
        return f"(IntExpr {exp.resolved_type.to_s_expression()} {exp.value})"
    elif isinstance(exp, FloatExpr):
        return f"(FloatExpr {exp.resolved_type.to_s_expression()} {int(exp.value)})"
    elif isinstance(exp, TrueExpr):
        return f"(TrueExpr {exp.resolved_type.to_s_expression()})"
    elif isinstance(exp, FalseExpr):
        return f"(FalseExpr {exp.resolved_type.to_s_expression()})"
    elif isinstance(exp, UnopExpr):
        return f"(UnopExpr {exp.resolved_type.to_s_expression()} {exp.op.value} {annotate_expr(exp.operand)})"
    elif isinstance(exp, BinopExpr):
        return f"(BinopExpr {exp.resolved_type.to_s_expression()} {annotate_expr(exp.left)} {exp.op.value} {annotate_expr(exp.right)})"
    elif isinstance(exp, IfExpr):
        return f"(IfExpr {exp.resolved_type.to_s_expression()} {annotate_expr(exp.cond)} {annotate_expr(exp.then_branch)} {annotate_expr(exp.else_branch)})"
    elif isinstance(exp, DotExpr):
        return f"(DotExpr {exp.resolved_type.to_s_expression()} {annotate_expr(exp.left)} {exp.right})"
    elif isinstance(exp, ArrayIndexExpr):
        if exp.indexes:
            indexes_s = " ".join(annotate_expr(i) for i in exp.indexes)
            return f"(ArrayIndexExpr {exp.resolved_type.to_s_expression()} {annotate_expr(exp.array)} {indexes_s})"
        else:
            return f"(ArrayIndexExpr {exp.resolved_type.to_s_expression()} {annotate_expr(exp.array)})"
    elif isinstance(exp, CallExpr):
        args_s = " ".join(annotate_expr(a) for a in exp.arguments)
        if isinstance(exp.function, VarExpr):
            # 取该函数的返回类型字符串
            if isinstance(exp.function.resolved_type, FnType):
                ret_ty = exp.function.resolved_type.return_type.to_s_expression()
            else:
                ret_ty = exp.function.resolved_type.to_s_expression()
            fn_str = f"{ret_ty} {exp.function.name}"
        else:
            fn_str = annotate_expr(exp.function)
        if args_s:
            return f"(CallExpr {fn_str} {args_s})"
        else:
            return f"(CallExpr {fn_str})"

    elif isinstance(exp, ArrayLiteralExpr):
        elems_s = " ".join(annotate_expr(e) for e in exp.elements)
        return f"(ArrayLiteralExpr {exp.resolved_type.to_s_expression()} {elems_s})"
    elif isinstance(exp, StructLiteralExpr):
        if exp.fields:
            fields_s = " ".join(annotate_expr(f) for f in exp.fields)
            return f"(StructLiteralExpr {exp.resolved_type.to_s_expression()} {exp.struct_name} {fields_s})"
        else:
            return f"(StructLiteralExpr {exp.resolved_type.to_s_expression()} {exp.struct_name})"
    elif isinstance(exp, VarExpr):
        return f"(VarExpr {exp.resolved_type.to_s_expression()} {exp.name})"
    elif isinstance(exp, VoidExpr):
        return f"(VoidExpr {exp.resolved_type.to_s_expression()})"
    elif isinstance(exp, ArrayLoopExpr):
        bounds_s = " ".join(f"{var} {annotate_expr(expr)}" for var, expr in exp.bounds)
        return f"(ArrayLoopExpr {exp.resolved_type.to_s_expression()} {bounds_s} {annotate_expr(exp.body)})"
    elif isinstance(exp, SumLoopExpr):
        bounds_s = " ".join(f"{var} {annotate_expr(expr)}" for var, expr in exp.bounds)
        return f"(SumLoopExpr {exp.resolved_type.to_s_expression()} {bounds_s} {annotate_expr(exp.body)})"
    else:
        return exp.to_s_expression()


def annotate_lvalue(lval: LValue) -> str:
    if isinstance(lval, VarLValue):
        return f"(VarLValue {lval.name})"
    elif isinstance(lval, ArrayLValue):
        idx_str = " ".join(lval.indices)
        return f"(ArrayLValue {lval.array} {idx_str})"
    else:
        return lval.to_s_expression()

def annotate_stmt(stmt: Stmt) -> str:
    if isinstance(stmt, LetStmt):
        return f"(LetStmt {annotate_lvalue(stmt.lvalue)} {annotate_expr(stmt.expr)})"
    elif isinstance(stmt, AssertStmt):
        return f'(AssertStmt {annotate_expr(stmt.expr)} "{stmt.message}")'
    elif isinstance(stmt, ReturnStmt):
        return f"(ReturnStmt {annotate_expr(stmt.expr)})"
    else:
        return stmt.to_s_expression()
    
def annotate_cmd(cmd: Cmd) -> str:
    if isinstance(cmd, ShowCmd):
        return f"(ShowCmd {annotate_expr(cmd.expr)})"
    elif isinstance(cmd, AssertCmd):
        return f'(AssertCmd {annotate_expr(cmd.expr)} "{cmd.message}")'
    elif isinstance(cmd, LetCmd):
        return f"(LetCmd {annotate_lvalue(cmd.lvalue)} {annotate_expr(cmd.value)})"
    elif isinstance(cmd, ReadCmd):
        return f"(ReadCmd \"{cmd.filename}\" {annotate_lvalue(cmd.lvalue)})"
    elif isinstance(cmd, WriteCmd):
        return f"(WriteCmd {annotate_expr(cmd.expr)} \"{cmd.filename}\")"
    elif isinstance(cmd, PrintCmd):
        return f'(PrintCmd "{cmd.message}")'
    elif isinstance(cmd, TimeCmd):
        return f"(TimeCmd {annotate_cmd(cmd.cmd)})"
    elif isinstance(cmd, FnCmd):
        if cmd.bindings:
            pairs = []
            for binding in cmd.bindings:
                pairs.append(f"{annotate_lvalue(binding.lvalue)} {binding.type_node.to_s_expression()}")
            bindings_s = f"(({ ' '.join(pairs) }))"
        else:
            bindings_s = "(())"
        body_s = " ".join(annotate_stmt(s) for s in cmd.body)
        return f"(FnCmd {cmd.name} {bindings_s} {cmd.return_type.to_s_expression()} {body_s})"
    elif isinstance(cmd, StructCmd):
        if len(cmd.field_pairs) == 0:
            return f"(StructCmd {cmd.name})"
        else:
            fields_s = " ".join(f"{fname} {ftype.to_s_expression()}" for fname, ftype in cmd.field_pairs)
            return f"(StructCmd {cmd.name} {fields_s})"
    else:
        return cmd.to_s_expression()



def typecheck_and_annotate(cmds: List[Cmd]) -> List[str]:
    typecheck_program(cmds)
    return [annotate_cmd(cmd) for cmd in cmds]  
