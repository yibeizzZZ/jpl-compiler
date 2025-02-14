from typing import List, Dict, Tuple, Optional
from parser import *  
from enum import Enum


Environment = Dict[str, Dict[str, TypeNode]]


def build_struct_env(cmds: List[Cmd]) -> Environment:
    env: Environment = {}
    for cmd in cmds:
        if isinstance(cmd, StructCmd):
            env[cmd.name] = {fname: ftype for fname, ftype in cmd.field_pairs}
    if "rgba" not in env:
        env["rgba"] = {
            "r": FloatType(start_idx=0),
            "g": FloatType(start_idx=0),
            "b": FloatType(start_idx=0),
            "a": FloatType(start_idx=0)
        }
    return env

def types_equal(t1: TypeNode, t2: TypeNode) -> bool:
    if type(t1) != type(t2):
        return False
    if isinstance(t1, (IntType, FloatType, BoolType, VoidType)):
        return True
    if isinstance(t1, StructType):
        return t1.name == t2.name
    if isinstance(t1, ArrayType):
        return types_equal(t1.element_type, t2.element_type) and t1.dimension == t2.dimension
    return False

def type_of_expr(expr: Expr, env: Environment) -> TypeNode:
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
        if expr.struct_name not in env:
            raise TypeError(f"Undefined struct type: {expr.struct_name}")
        struct_def = env[expr.struct_name]
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
        if base_t.name not in env:
            raise TypeError(f"Undefined struct type: {base_t.name}")
        struct_def = env[base_t.name]
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
    elif isinstance(expr, ArrayLoopExpr) or isinstance(expr, SumLoopExpr):
        local_env = env.copy()
        for var, bound_expr in expr.bounds:
            bound_t = type_of_expr(bound_expr, env)
            if not isinstance(bound_t, IntType):
                raise TypeError("Loop bound must be int")
            # 将循环变量简单地绑定为 int 类型
            local_env[var] = {var: IntType(start_idx=expr.start_idx)}
        body_t = type_of_expr(expr.body, local_env)
        expr.resolved_type = body_t
        return body_t
    else:
        raise TypeError(f"Type checking not implemented for node type: {type(expr)}")

def typecheck_program(cmds: List[Cmd]) -> None:
    env: Environment = {
        "rgba": {
            "r": FloatType(start_idx=0),
            "g": FloatType(start_idx=0),
            "b": FloatType(start_idx=0),
            "a": FloatType(start_idx=0)
        }
    }
    for cmd in cmds:
        if isinstance(cmd, StructCmd):
            fields = {}
            for fname, ftype in cmd.field_pairs:
                fields[fname] = ftype
            env[cmd.name] = fields
        elif isinstance(cmd, ShowCmd):
            t = type_of_expr(cmd.expr, env)
            cmd.expr.resolved_type = t
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
        return f"(CallExpr {annotate_expr(exp.function)} {args_s})"
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
        return f"(VarExpr {exp.name})"
    elif isinstance(exp, VoidExpr):
        return "(VoidExpr)"
    else:
        return exp.to_s_expression()


def annotate_cmd(cmd: Cmd) -> str:
    if isinstance(cmd, ShowCmd):
        return f"(ShowCmd {annotate_expr(cmd.expr)})"
    else:
        return cmd.to_s_expression()

def typecheck_and_annotate(cmds: List[Cmd]) -> List[str]:
    typecheck_program(cmds)
    return [annotate_cmd(cmd) for cmd in cmds]
