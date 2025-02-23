from typing import List, Dict, Tuple, Optional, Set
from parser import *
from enum import Enum

# For user-defined functions, we store a tuple: (number of parameters, return type)
Environment = Dict[str, object]

# -------------------- Cycle Detection --------------------
def detect_cycle(struct_name: str, env: Environment, visited: Set[str]) -> bool:
    """
    Recursively detects if there is a cyclic dependency starting from struct_name.
    The visited set tracks the structs encountered in the current chain.
    Returns True if a cycle is detected.
    """
    if struct_name in visited:
        return True
    if struct_name not in env or struct_name == "rgba":
        return False
    st = env[struct_name]
    if not isinstance(st, StructType) or st.fields is None:
        return False
    visited.add(struct_name)
    for field in st.fields.values():
        if isinstance(field, StructType):
            if detect_cycle(field.name, env, visited.copy()):
                return True
        elif isinstance(field, ArrayType) and isinstance(field.element_type, StructType):
            if detect_cycle(field.element_type.name, env, visited.copy()):
                return True
    return False

# -------------------- Environment Building --------------------
def build_struct_env(cmds: List[Cmd]) -> Environment:
    env: Environment = {}
    # Reserve built-in variables.
    env["argnum"] = IntType(start_idx=0)
    env["args"] = ArrayType(start_idx=0, element_type=IntType(start_idx=0), dimension=1)
    # Reserve built-in function names.
    for builtin in ["sin", "cos", "tan", "asin", "acos", "atan", "sqrt", "exp", "log", "to_int", "to_float", "pow", "atan2"]:
        env[builtin] = "builtin"  # mark as reserved
    # Predefine the 'rgba' struct.
    st_rgba = StructType(start_idx=0, name="rgba")
    st_rgba.fields = {}
    env["rgba"] = st_rgba

    # First pass: add each struct declaration.
    for cmd in cmds:
        if isinstance(cmd, StructCmd):
            if cmd.name in env:
                raise TypeError(f"Duplicate struct declaration: '{cmd.name}'")
            st = StructType(start_idx=cmd.start_idx, name=cmd.name)
            st.fields = {}
            env[cmd.name] = st

    # Second pass: fill in field information and check for duplicate field names.
    for cmd in cmds:
        if isinstance(cmd, StructCmd):
            st = env[cmd.name]
            fields: Dict[str, TypeNode] = {}
            for fname, ftype in cmd.field_pairs:
                if fname in fields:
                    raise TypeError(f"Duplicate field '{fname}' in struct '{cmd.name}'.")
                if isinstance(ftype, StructType) and ftype.name in env:
                    fields[fname] = env[ftype.name]
                else:
                    fields[fname] = ftype
            st.fields = fields

    # Third pass: detect cyclic struct definitions.
    for key, val in env.items():
        if isinstance(val, StructType) and key != "rgba":
            if detect_cycle(key, env, set()):
                raise TypeError(f"Cyclic struct definition detected in struct '{key}'.")
    return env

# -------------------- Utility --------------------
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

# -------------------- Free Variables in Expression --------------------
def free_vars_expr(expr: Expr) -> Set[str]:
    """
    Recursively collects the free variable names in an expression.
    """
    if isinstance(expr, VarExpr):
        return {expr.name}
    elif isinstance(expr, (IntExpr, FloatExpr, TrueExpr, FalseExpr, VoidExpr)):
        return set()
    elif isinstance(expr, ArrayLiteralExpr):
        s = set()
        for subexpr in expr.elements:
            s |= free_vars_expr(subexpr)
        return s
    elif isinstance(expr, BinopExpr):
        return free_vars_expr(expr.left) | free_vars_expr(expr.right)
    elif isinstance(expr, StructLiteralExpr):
        s = set()
        for field in expr.fields:
            s |= free_vars_expr(field)
        return s
    elif isinstance(expr, DotExpr):
        return free_vars_expr(expr.left)
    elif isinstance(expr, CallExpr):
        s = free_vars_expr(expr.function)
        for arg in expr.arguments:
            s |= free_vars_expr(arg)
        return s
    elif isinstance(expr, ArrayLoopExpr) or isinstance(expr, SumLoopExpr):
        # Variables bound in the loop are not free in the body.
        bound = {var for var, _ in expr.bounds}
        s = set()
        for _, b in expr.bounds:
            s |= free_vars_expr(b)
        s |= free_vars_expr(expr.body)
        return s - bound
    elif isinstance(expr, ArrayIndexExpr):
        s = free_vars_expr(expr.array)
        for idx in expr.indexes:
            s |= free_vars_expr(idx)
        return s
    else:
        return set()

# -------------------- Expression Type-checking --------------------
def type_of_expr(expr: Expr, env: Environment) -> TypeNode:
    if isinstance(expr, IntExpr):
        expr.resolved_type = IntType(start_idx=expr.start_idx)
    elif isinstance(expr, FloatExpr):
        expr.resolved_type = FloatType(start_idx=expr.start_idx)
    elif isinstance(expr, TrueExpr) or isinstance(expr, FalseExpr):
        expr.resolved_type = BoolType(start_idx=expr.start_idx)
    elif isinstance(expr, VoidExpr):
        expr.resolved_type = VoidType(start_idx=expr.start_idx)
    elif isinstance(expr, VarExpr):
        if expr.name in env:
            if isinstance(env[expr.name], tuple):
                expr.resolved_type = env[expr.name][1]
            else:
                expr.resolved_type = env[expr.name]
        else:
            raise TypeError(f"Undefined variable: {expr.name}")
    elif isinstance(expr, ArrayLiteralExpr):
        if not expr.elements:
            raise TypeError("Empty array literal is ambiguous")
        first_t = type_of_expr(expr.elements[0], env)
        for subexpr in expr.elements[1:]:
            t = type_of_expr(subexpr, env)
            if not types_equal(first_t, t):
                raise TypeError("Array literal elements have mismatched types")
        expr.resolved_type = ArrayType(start_idx=expr.start_idx, element_type=first_t, dimension=1)
    elif isinstance(expr, BinopExpr):
        left_t = type_of_expr(expr.left, env)
        right_t = type_of_expr(expr.right, env)
        if expr.op in (Binop.LT, Binop.GT, Binop.LE, Binop.GE, Binop.EQ, Binop.NE):
            if not types_equal(left_t, right_t):
                raise TypeError("Comparison operators require operands of the same type")
            expr.resolved_type = BoolType(start_idx=expr.start_idx)
        elif expr.op in (Binop.PLUS, Binop.MINUS, Binop.MULT, Binop.DIV, Binop.MOD):
            expr.resolved_type = (FloatType(start_idx=expr.start_idx)
                                  if isinstance(left_t, FloatType) or isinstance(right_t, FloatType)
                                  else IntType(start_idx=expr.start_idx))
        elif expr.op in (Binop.AND, Binop.OR):
            expr.resolved_type = BoolType(start_idx=expr.start_idx)
        else:
            raise TypeError("Unknown binary operator")
    elif isinstance(expr, StructLiteralExpr):
        if expr.struct_name not in env:
            raise TypeError(f"Undefined struct: {expr.struct_name}")
        stype = env[expr.struct_name]
        if not isinstance(stype, StructType):
            raise TypeError(f"{expr.struct_name} is not a struct type")
        for field_expr in expr.fields:
            type_of_expr(field_expr, env)
        expr.resolved_type = stype
    elif isinstance(expr, DotExpr):
        left_type = type_of_expr(expr.left, env)
        if not isinstance(left_type, StructType):
            raise TypeError("Dot operator applied to non-struct type")
        if not hasattr(left_type, "fields") or left_type.fields is None:
            raise TypeError(f"Struct type {left_type.name} does not have field information")
        if expr.right not in left_type.fields:
            raise TypeError(f"Field {expr.right} not found in struct {left_type.name}")
        expr.resolved_type = left_type.fields[expr.right]
    elif isinstance(expr, CallExpr):
        if isinstance(expr.function, VarExpr):
            fname = expr.function.name
            builtins_one = {"sin", "cos", "tan", "asin", "acos", "atan", "sqrt", "exp", "log", "to_int", "to_float"}
            builtins_two = {"pow", "atan2"}
            if fname in builtins_one:
                if len(expr.arguments) != 1:
                    raise TypeError(f"{fname} takes exactly one argument")
                arg_type = type_of_expr(expr.arguments[0], env)
                if fname == "to_int":
                    if not isinstance(arg_type, FloatType):
                        raise TypeError("to_int argument must be a float")
                    expr.resolved_type = IntType(start_idx=expr.start_idx)
                elif fname == "to_float":
                    if not (isinstance(arg_type, IntType) or isinstance(arg_type, FloatType)):
                        raise TypeError("to_float argument must be a number")
                    expr.resolved_type = FloatType(start_idx=expr.start_idx)
                else:
                    if not isinstance(arg_type, FloatType):
                        raise TypeError(f"{fname} argument must be a float")
                    expr.resolved_type = FloatType(start_idx=expr.start_idx)
            elif fname in builtins_two:
                if len(expr.arguments) != 2:
                    raise TypeError(f"{fname} takes exactly two arguments")
                arg1 = type_of_expr(expr.arguments[0], env)
                arg2 = type_of_expr(expr.arguments[1], env)
                if not (isinstance(arg1, FloatType) and isinstance(arg2, FloatType)):
                    raise TypeError(f"{fname} arguments must be floats")
                expr.resolved_type = FloatType(start_idx=expr.start_idx)
            else:
                for arg in expr.arguments:
                    type_of_expr(arg, env)
                if fname not in env:
                    raise TypeError(f"Undefined function: {fname}")
                func_info = env[fname]
                if not isinstance(func_info, tuple):
                    raise TypeError(f"Function {fname} is not user-defined properly")
                expected = func_info[0]
                if len(expr.arguments) != expected:
                    raise TypeError(f"{fname} takes exactly {expected} arguments")
                expr.resolved_type = func_info[1]
        else:
            raise TypeError(f"Unhandled function call: {expr.function}")
    elif isinstance(expr, ArrayLoopExpr):
        # Reject empty bounds.
        if not expr.bounds:
            raise TypeError("Array loop bounds cannot be empty")
        new_env = env.copy()
        for var, bound_expr in expr.bounds:
            bound_type = type_of_expr(bound_expr, env)
            if isinstance(bound_type, ArrayType):
                new_env[var] = bound_type.element_type
            elif isinstance(bound_type, IntType):
                new_env[var] = IntType(start_idx=bound_expr.start_idx)
            else:
                raise TypeError("Array loop bound expression must be of array type or int")
        body_type = type_of_expr(expr.body, new_env)
        expr.resolved_type = ArrayType(start_idx=expr.start_idx, element_type=body_type, dimension=len(expr.bounds))
    elif isinstance(expr, SumLoopExpr):
        if not expr.bounds:
            raise TypeError("Sum loop must have at least one bound")
        new_env = env.copy()
        for var, bound_expr in expr.bounds:
            bound_type = type_of_expr(bound_expr, env)
            if not isinstance(bound_type, IntType):
                raise TypeError("Sum loop bound expression must be int")
            new_env[var] = IntType(start_idx=bound_expr.start_idx)
        body_type = type_of_expr(expr.body, new_env)
        if not (isinstance(body_type, IntType) or isinstance(body_type, FloatType)):
            raise TypeError("Sum loop body must be numeric")
        expr.resolved_type = body_type
    elif isinstance(expr, ArrayIndexExpr):
        if not expr.indexes:
            raise TypeError("Array index expression must have at least one index")
        arr_type = type_of_expr(expr.array, env)
        if not isinstance(arr_type, ArrayType):
            raise TypeError("Attempting to index a non-array type")
        for idx_expr in expr.indexes:
            idx_type = type_of_expr(idx_expr, env)
            if not isinstance(idx_type, IntType):
                raise TypeError("Array index must be of int type")
        n = len(expr.indexes)
        # NEW: Require that the number of indexes exactly equals the array's dimension.
        if n != arr_type.dimension:
            raise TypeError("Array indexing must provide exactly as many indexes as the array's dimension")
        expr.resolved_type = arr_type.element_type
    else:
        raise TypeError(f"Unhandled expression type: {type(expr)}")
    return expr.resolved_type

# -------------------- Statement Type-checking --------------------
def typecheck_stmt(stmt: Stmt, env: Environment) -> None:
    if isinstance(stmt, LetStmt):
        if isinstance(stmt.lvalue, VarLValue):
            if stmt.lvalue.name in env:
                raise TypeError(f"Variable '{stmt.lvalue.name}' is already declared in this scope.")
            expr_type = type_of_expr(stmt.expr, env)
            env[stmt.lvalue.name] = expr_type
        elif isinstance(stmt.lvalue, ArrayLValue):
            arr_name = stmt.lvalue.array
            for idx_name in stmt.lvalue.indices:
                if idx_name in env:
                    raise TypeError(f"Index variable '{idx_name}' is already declared in this scope.")
                env[idx_name] = IntType(start_idx=stmt.start_idx)
            if arr_name in env:
                raise TypeError(f"Variable '{arr_name}' is already declared in this scope.")
            # NEW: Check that none of the index variables appear free in the initializer.
            free = free_vars_expr(stmt.expr)
            for idx_name in stmt.lvalue.indices:
                if idx_name in free:
                    raise TypeError(f"Index variable '{idx_name}' cannot appear free in the array initializer.")
            rhs_type = type_of_expr(stmt.expr, env)
            if not isinstance(rhs_type, ArrayType):
                raise TypeError("Right-hand side must be an array for array element assignment")
            if rhs_type.dimension != len(stmt.lvalue.indices):
                raise TypeError("Array literal dimension does not match the array lvalue indices")
            env[arr_name] = rhs_type
        else:
            raise TypeError("Unhandled lvalue type in let statement")
    elif isinstance(stmt, LetCmd):
        if isinstance(stmt.lvalue, VarLValue):
            if stmt.lvalue.name in env:
                raise TypeError(f"Variable '{stmt.lvalue.name}' is already declared in this scope.")
            expr_type = type_of_expr(stmt.value, env)
            env[stmt.lvalue.name] = expr_type
        elif isinstance(stmt.lvalue, ArrayLValue):
            arr_name = stmt.lvalue.array
            for idx_name in stmt.lvalue.indices:
                if idx_name in env:
                    raise TypeError(f"Index variable '{idx_name}' is already declared in this scope.")
                env[idx_name] = IntType(start_idx=stmt.start_idx)
            if arr_name in env:
                raise TypeError(f"Variable '{arr_name}' is already declared in this scope.")
            free = free_vars_expr(stmt.value)
            for idx_name in stmt.lvalue.indices:
                if idx_name in free:
                    raise TypeError(f"Index variable '{idx_name}' cannot appear free in the array initializer.")
            rhs_type = type_of_expr(stmt.value, env)
            if not isinstance(rhs_type, ArrayType):
                raise TypeError("Right-hand side must be an array for array element assignment")
            if rhs_type.dimension != len(stmt.lvalue.indices):
                raise TypeError("Array literal dimension does not match the array lvalue indices")
            env[arr_name] = rhs_type
        else:
            raise TypeError("Unhandled lvalue type in let command")
    elif isinstance(stmt, ReturnStmt):
        type_of_expr(stmt.expr, env)
    elif isinstance(stmt, AssertStmt) or isinstance(stmt, AssertCmd):
        cond_type = type_of_expr(stmt.expr, env)
        if not isinstance(cond_type, BoolType):
            raise TypeError("Assertion condition must be boolean")
    elif isinstance(stmt, PrintCmd):
        if not isinstance(stmt.message, str):
            raise TypeError("Print statement must be a string message")
    elif isinstance(stmt, ShowCmd):
        type_of_expr(stmt.expr, env)
    elif isinstance(stmt, TimeCmd):
        typecheck_stmt(stmt.cmd, env)
    elif isinstance(stmt, StructCmd):
        seen = {}
        for field_name, field_type in stmt.field_pairs:
            if field_name in seen:
                raise TypeError(f"Duplicate field '{field_name}' in struct '{stmt.name}'.")
            seen[field_name] = field_type
            env[field_name] = field_type
    elif isinstance(stmt, ReadCmd):
        if isinstance(stmt.lvalue, VarLValue):
            if stmt.lvalue.name in env:
                raise TypeError(f"Variable '{stmt.lvalue.name}' is already declared in this scope.")
            env[stmt.lvalue.name] = ArrayType(
                start_idx=stmt.start_idx,
                element_type=StructType(start_idx=stmt.start_idx, name="rgba"),
                dimension=2
            )
        elif isinstance(stmt.lvalue, ArrayLValue):
            if len(stmt.lvalue.indices) != 2:
                raise TypeError("ReadCmd target for an image must have exactly two indices.")
            arr_name = stmt.lvalue.array
            for idx_name in stmt.lvalue.indices:
                if idx_name in env:
                    raise TypeError(f"Index variable '{idx_name}' is already declared in this scope.")
                env[idx_name] = IntType(start_idx=stmt.start_idx)
            if arr_name in env:
                raise TypeError(f"Variable '{arr_name}' is already declared in this scope.")
            env[arr_name] = ArrayType(
                start_idx=stmt.start_idx,
                element_type=StructType(start_idx=stmt.start_idx, name="rgba"),
                dimension=2
            )
        else:
            raise TypeError("ReadCmd target must be a variable or an array lvalue.")
    elif isinstance(stmt, WriteCmd):
        etype = type_of_expr(stmt.expr, env)
        # Check that the type is an array type whose element type is a struct "rgba".
        if not (isinstance(etype, ArrayType) and 
                isinstance(etype.element_type, StructType) and 
                etype.element_type.name == "rgba"):
            raise TypeError("WriteCmd expression must be an image type (array of rgba)")
    elif isinstance(stmt, FnCmd):
        new_env = env.copy()
        seen = set()
        for binding in stmt.bindings:
            if isinstance(binding.lvalue, VarLValue):
                if binding.lvalue.name in seen:
                    raise TypeError(f"Duplicate parameter declaration: '{binding.lvalue.name}' in function '{stmt.name}'.")
                seen.add(binding.lvalue.name)
                if isinstance(binding.type_node, StructType) and binding.type_node.name in env:
                    new_env[binding.lvalue.name] = env[binding.type_node.name]
                else:
                    new_env[binding.lvalue.name] = binding.type_node
            elif isinstance(binding.lvalue, ArrayLValue):
                if binding.lvalue.array in seen:
                    raise TypeError(f"Duplicate parameter declaration: '{binding.lvalue.array}' in function '{stmt.name}'.")
                seen.add(binding.lvalue.array)
                new_env[binding.lvalue.array] = binding.type_node
                for idx in binding.lvalue.indices:
                    if idx in seen:
                        raise TypeError(f"Duplicate index parameter: '{idx}' in function '{stmt.name}'.")
                    seen.add(idx)
                    new_env[idx] = IntType(start_idx=binding.lvalue.start_idx)
            else:
                raise TypeError("Unhandled parameter type in function binding.")
        if stmt.name in env:
            raise TypeError(f"Function '{stmt.name}' is already declared.")
        new_env[stmt.name] = (len(stmt.bindings), stmt.return_type)
        env[stmt.name] = (len(stmt.bindings), stmt.return_type)
        for s in stmt.body:
            typecheck_stmt(s, new_env)
        check_function_returns(stmt, new_env)
    else:
        raise TypeError(f"Unhandled statement type: {type(stmt)}")

# -------------------- Function Return Type Checking --------------------
def check_function_returns(fn: FnCmd, env: Environment) -> None:
    if not isinstance(fn.return_type, VoidType):
        found_return = False
        for stmt in fn.body:
            if contains_return(stmt):
                found_return = True
                break
        if not found_return:
            raise TypeError(
                f"Function '{fn.name}' is declared to return {fn.return_type.to_s_expression()} but no return statement was found."
            )
    for ret in collect_returns(fn.body):
        ret_type = type_of_expr(ret.expr, env)
        if not types_equal(ret_type, fn.return_type):
            raise TypeError(
                f"Function '{fn.name}' is declared to return {fn.return_type.to_s_expression()}, but a return statement returns {ret_type.to_s_expression()}."
            )

def contains_return(stmt: Stmt) -> bool:
    if isinstance(stmt, ReturnStmt):
        return True
    elif isinstance(stmt, TimeCmd):
        return contains_return(stmt.cmd)
    return False

def collect_returns(stmts: List[Stmt]) -> List[ReturnStmt]:
    ret_list = []
    for stmt in stmts:
        if isinstance(stmt, ReturnStmt):
            ret_list.append(stmt)
        elif isinstance(stmt, TimeCmd):
            ret_list.extend(collect_returns([stmt.cmd]))
    return ret_list

# -------------------- Annotation --------------------
def annotate_expr(exp: Expr) -> str:
    if isinstance(exp, IntExpr):
        return f"(IntExpr (IntType) {exp.value})"
    elif isinstance(exp, FloatExpr):
        val = int(exp.value) if exp.value.is_integer() else exp.value
        return f"(FloatExpr (FloatType) {val})"
    elif isinstance(exp, TrueExpr):
        return "(TrueExpr (BoolType))"
    elif isinstance(exp, FalseExpr):
        return "(FalseExpr (BoolType))"
    elif isinstance(exp, VoidExpr):
        return "(VoidExpr (VoidType))"
    elif isinstance(exp, VarExpr):
        resolved_type = exp.resolved_type.to_s_expression() if hasattr(exp, 'resolved_type') and exp.resolved_type else "(UnknownType)"
        return f"(VarExpr {resolved_type} {exp.name})"
    elif isinstance(exp, ArrayLiteralExpr):
        array_type = exp.resolved_type.to_s_expression() if hasattr(exp, 'resolved_type') and exp.resolved_type else "(UnknownType)"
        elements = " ".join(annotate_expr(e) for e in exp.elements)
        return f"(ArrayLiteralExpr {array_type} {elements})"
    elif isinstance(exp, BinopExpr):
        return f"(BinopExpr {exp.resolved_type.to_s_expression()} {annotate_expr(exp.left)} {exp.op.value} {annotate_expr(exp.right)})"
    elif isinstance(exp, StructLiteralExpr):
        fields = " ".join(annotate_expr(field) for field in exp.fields)
        stype = getattr(exp, 'resolved_type', None)
        struct_type = stype.to_s_expression() if stype is not None else "(UnknownType)"
        return f"(StructLiteralExpr {struct_type} {exp.struct_name} {fields})"
    elif isinstance(exp, DotExpr):
        left_str = annotate_expr(exp.left)
        return f"(DotExpr {exp.resolved_type.to_s_expression()} {left_str} {exp.right})"
    elif isinstance(exp, CallExpr):
        if isinstance(exp.function, VarExpr):
            func_str = exp.function.name
        else:
            func_str = annotate_expr(exp.function)
        args_str = " ".join(annotate_expr(arg) for arg in exp.arguments).strip()
        if args_str:
            return f"(CallExpr {exp.resolved_type.to_s_expression()} {func_str} {args_str})"
        else:
            return f"(CallExpr {exp.resolved_type.to_s_expression()} {func_str})"
    elif isinstance(exp, ArrayLoopExpr):
        bounds_parts = " ".join(f"{var} {annotate_expr(bound_expr)}" for var, bound_expr in exp.bounds)
        body_str = annotate_expr(exp.body)
        array_type = exp.resolved_type.to_s_expression() if hasattr(exp, 'resolved_type') and exp.resolved_type else "(UnknownType)"
        return f"(ArrayLoopExpr {array_type} {bounds_parts} {body_str})"
    elif isinstance(exp, SumLoopExpr):
        bounds_parts = " ".join(f"{var} {annotate_expr(bound_expr)}" for var, bound_expr in exp.bounds)
        body_str = annotate_expr(exp.body)
        return f"(SumLoopExpr {exp.resolved_type.to_s_expression()} {bounds_parts} {body_str})"
    elif isinstance(exp, ArrayIndexExpr):
        arr_str = annotate_expr(exp.array)
        indexes_str = " ".join(annotate_expr(idx) for idx in exp.indexes)
        return f"(ArrayIndexExpr {exp.resolved_type.to_s_expression()} {arr_str} {indexes_str})"
    else:
        return exp.to_s_expression()

def annotate_lvalue(lval: LValue) -> str:
    if isinstance(lval, VarLValue):
        return f"(VarLValue {lval.name})"
    elif isinstance(lval, ArrayLValue):
        indices_names = " ".join(lval.indices)
        return f"(ArrayLValue {lval.array} {indices_names})"
    else:
        return lval.to_s_expression()

def annotate_cmd(cmd: Cmd) -> str:
    if isinstance(cmd, ShowCmd):
        return f"(ShowCmd {annotate_expr(cmd.expr)})"
    elif isinstance(cmd, AssertCmd):
        msg = cmd.message if cmd.message is not None else ""
        return f"(AssertCmd {annotate_expr(cmd.expr)} \"{msg}\")"
    elif isinstance(cmd, AssertStmt):
        msg = cmd.message if cmd.message else ""
        return f"(AssertStmt {annotate_expr(cmd.expr)} \"{msg}\")"
    elif isinstance(cmd, PrintCmd):
        return f"(PrintCmd \"{cmd.message}\")"
    elif isinstance(cmd, TimeCmd):
        return f"(TimeCmd {annotate_cmd(cmd.cmd)})"
    elif isinstance(cmd, LetCmd):
        return f"(LetCmd {annotate_lvalue(cmd.lvalue)} {annotate_expr(cmd.value)})"
    elif isinstance(cmd, LetStmt):
        return f"(LetStmt {annotate_lvalue(cmd.lvalue)} {annotate_expr(cmd.expr)})"
    elif isinstance(cmd, ReadCmd):
        return f"(ReadCmd \"{cmd.filename}\" {cmd.lvalue.to_s_expression()})"
    elif isinstance(cmd, WriteCmd):
        return f"(WriteCmd {annotate_expr(cmd.expr)} \"{cmd.filename}\")"
    elif isinstance(cmd, FnCmd):
        if not cmd.bindings:
            bindings_str = "(())"
        else:
            bindings_str = " ".join(f"{annotate_lvalue(binding.lvalue)} {binding.type_node.to_s_expression()}"
                                    for binding in cmd.bindings)
            bindings_str = f"(({bindings_str}))"
        body_str = " ".join(annotate_cmd(s) for s in cmd.body)
        return f"(FnCmd {cmd.name} {bindings_str} {cmd.return_type.to_s_expression()} {body_str})"
    elif isinstance(cmd, ReturnStmt):
        return f"(ReturnStmt {annotate_expr(cmd.expr)})"
    else:
        return cmd.to_s_expression()

def typecheck_program(cmds: List[Cmd]) -> None:
    env = build_struct_env(cmds)
    for cmd in cmds:
        typecheck_stmt(cmd, env)

def typecheck_and_annotate(cmds: List[Cmd]) -> List[str]:
    typecheck_program(cmds)
    return [annotate_cmd(cmd) for cmd in cmds]

# -------------------- Function Return Type Checking --------------------
def check_function_returns(fn: FnCmd, env: Environment) -> None:
    if not isinstance(fn.return_type, VoidType):
        found_return = False
        for stmt in fn.body:
            if contains_return(stmt):
                found_return = True
                break
        if not found_return:
            raise TypeError(
                f"Function '{fn.name}' is declared to return {fn.return_type.to_s_expression()} but no return statement was found."
            )
    for ret in collect_returns(fn.body):
        ret_type = type_of_expr(ret.expr, env)
        if not types_equal(ret_type, fn.return_type):
            raise TypeError(
                f"Function '{fn.name}' is declared to return {fn.return_type.to_s_expression()}, but a return statement returns {ret_type.to_s_expression()}."
            )

def contains_return(stmt: Stmt) -> bool:
    if isinstance(stmt, ReturnStmt):
        return True
    elif isinstance(stmt, TimeCmd):
        return contains_return(stmt.cmd)
    return False

def collect_returns(stmts: List[Stmt]) -> List[ReturnStmt]:
    ret_list = []
    for stmt in stmts:
        if isinstance(stmt, ReturnStmt):
            ret_list.append(stmt)
        elif isinstance(stmt, TimeCmd):
            ret_list.extend(collect_returns([stmt.cmd]))
    return ret_list
