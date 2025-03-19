from parser import *
from typechecker import *
import re

class CodeGenerator:
    def __init__(self):
        self.temp_counter = 0
        self.jump_counter = 1
        # 用有序列表存储 typedef，保证输出顺序与输入一致
        self.typedefs = []
        self.generated_typedef_names = set()  # 用于检查是否已经生成了某个 typedef
        self.struct_field_map = {}  # Map: struct name -> list of field types
        self.env = {}               # 环境变量
        self.generated_code = []    # 存储 jpl_main 代码行
        self.ordering = "expected"
        self.functions = []

    def new_temp(self):
        t = f"_{self.temp_counter}"
        self.temp_counter += 1
        return t

    def c_type(self, type_node):
        if isinstance(type_node, IntType):
            return "int64_t"
        elif isinstance(type_node, FloatType):
            return "double"
        elif isinstance(type_node, BoolType):
            return "bool"
        elif isinstance(type_node, VoidType):
            return "void_t"
        elif isinstance(type_node, StructType):
            return type_node.name
        elif isinstance(type_node, ArrayType):
            # 直接根据传入维数生成对应的 typedef 名称
            elem = self.c_type(type_node.element_type)
            rank = type_node.dimension
            typedef_name = f"_a{rank}_{elem.replace(' ', '_')}"
            if typedef_name not in self.generated_typedef_names:
                lines = []
                lines.append("typedef struct {")
                for i in range(rank):
                    lines.append(f"    int64_t d{i};")
                lines.append(f"    {elem} *data;")
                lines.append(f"}} {typedef_name};")
                typedef_code = "\n".join(lines)
                self.typedefs.append(typedef_code)
                self.generated_typedef_names.add(typedef_name)
            return typedef_name
        else:
            raise Exception("Unknown type in c_type conversion")

    def struct_to_tuple_sexp(self, st: StructType) -> str:
        if st.name == "rgba":
            return "(TupleType (FloatType) (FloatType) (FloatType) (FloatType))"
        field_types = self.struct_field_map.get(st.name, [])
        field_sexps = []
        for f in field_types:
            if isinstance(f, ArrayType):
                if isinstance(f.element_type, StructType) and f.element_type.name in self.struct_field_map:
                    field_sexps.append(f"(ArrayType {self.struct_to_tuple_sexp(f.element_type)} {f.dimension})")
                else:
                    field_sexps.append(f.to_s_expression())
            elif isinstance(f, StructType) and f.name in self.struct_field_map:
                field_sexps.append(self.struct_to_tuple_sexp(f))
            else:
                field_sexps.append(f.to_s_expression())
        return "(TupleType " + " ".join(field_sexps) + ")"

    def gen_expr(self, expr: Expr, top_level: bool = False) -> str:
        if isinstance(expr, DotExpr):
            base_temp = self.gen_expr(expr.left, top_level)
            temp = self.new_temp()
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {base_temp}.{expr.right};")
            return temp
        if isinstance(expr, LetCmd):
            temp = self.new_temp()
            value_temp = self.gen_expr(expr.value, top_level)
            self.generated_code.append(f"{self.c_type(expr.value.resolved_type)} {temp} = {value_temp};")
            return temp
        elif isinstance(expr, SumLoopExpr):
            result_temp = self.new_temp()
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {result_temp};")
            bound_temps = []
            for (var, bound_expr) in expr.bounds:
                self.generated_code.append(f"// Computing bound for {var}")
                if isinstance(bound_expr, IntExpr):
                    if bound_expr.value < 0:
                        temp_pos = self.new_temp()
                        self.generated_code.append(f"int64_t {temp_pos} = {abs(bound_expr.value)};")
                        bt = self.new_temp()
                        self.generated_code.append(f"int64_t {bt} = -{temp_pos};")
                    else:
                        bt = self.new_temp()
                        self.generated_code.append(f"int64_t {bt} = {bound_expr.value};")
                elif isinstance(bound_expr, FloatExpr):
                    bt = self.new_temp()
                    self.generated_code.append(f"double {bt} = {int(bound_expr.value)}.0;")
                else:
                    bt = self.gen_expr(bound_expr)
                bound_temps.append(bt)
                self.generated_code.append(f"if ({bt} > 0)")
                self.generated_code.append(f"    goto _jump{self.jump_counter};")
                self.generated_code.append(f'fail_assertion("non-positive loop bound");')
                self.generated_code.append(f"_jump{self.jump_counter}:;")
                self.jump_counter += 1
            self.generated_code.append(f"{result_temp} = 0;")
            loop_indices = []
            bound_vars = [var for (var, _) in expr.bounds]
            for var in reversed(bound_vars):
                idx = self.new_temp()
                self.generated_code.append(f"int64_t {idx} = 0; // {var}")
                loop_indices.append(idx)
                self.env[var] = idx
            loop_label = f"_jump{self.jump_counter}"
            self.jump_counter += 1
            self.generated_code.append(f"{loop_label}:; // Begin body of loop")
            body_val = self.gen_expr(expr.body, top_level=False)
            self.generated_code.append(f"{result_temp} += {body_val};")
            for i, idx in enumerate(loop_indices):
                self.generated_code.append(f"{idx}++;")
                self.generated_code.append(f"if ({idx} < {list(reversed(bound_temps))[i]})")
                self.generated_code.append(f"    goto {loop_label};")
                if i < len(loop_indices) - 1:
                    self.generated_code.append(f"{idx} = 0;")
            self.generated_code.append(f"// End body of loop")
            return result_temp
        elif isinstance(expr, ArrayLoopExpr):
            temp = self.new_temp()
            ctyp = self.c_type(expr.resolved_type)
            self.generated_code.append(f"{ctyp} {temp};")
            bound_temps = []
            for i, (var, bound_expr) in enumerate(expr.bounds):
                self.generated_code.append(f"// Computing bound for {var}")
                if isinstance(bound_expr, IntExpr):
                    if bound_expr.value < 0:
                        tp = self.new_temp()
                        self.generated_code.append(f"int64_t {tp} = {abs(bound_expr.value)};")
                        bt = self.new_temp()
                        self.generated_code.append(f"int64_t {bt} = -{tp};")
                    else:
                        bt = self.new_temp()
                        self.generated_code.append(f"int64_t {bt} = {bound_expr.value};")
                elif isinstance(bound_expr, FloatExpr):
                    bt = self.new_temp()
                    self.generated_code.append(f"double {bt} = {int(bound_expr.value)}.0;")
                else:
                    bt = self.gen_expr(bound_expr)
                bound_temps.append(bt)
                self.generated_code.append(f"{temp}.d{i} = {bt};")
                self.generated_code.append(f"if ({bt} > 0)")
                self.generated_code.append(f"    goto _jump{self.jump_counter};")
                self.generated_code.append(f'fail_assertion("non-positive loop bound");')
                self.generated_code.append(f"_jump{self.jump_counter}:;")
                self.jump_counter += 1
            self.generated_code.append(f"// Computing total size of heap memory to allocate")
            size_temp = self.new_temp()
            self.generated_code.append(f"int64_t {size_temp} = 1;")
            for bt in bound_temps:
                self.generated_code.append(f"{size_temp} *= {bt};")
            elem_type = self.c_type(expr.resolved_type.element_type)
            self.generated_code.append(f"{size_temp} *= sizeof({elem_type});")
            self.generated_code.append(f"{temp}.data = jpl_alloc({size_temp});")
            n = len(expr.bounds)
            if n == 1:
                loop_var = expr.bounds[0][0]
                loop_index = self.new_temp()
                self.generated_code.append(f"int64_t {loop_index} = 0; // {loop_var}")
                self.env[loop_var] = loop_index
                loop_label = f"_jump{self.jump_counter}"
                self.jump_counter += 1
                self.generated_code.append(f"{loop_label}:; // Begin body of loop")
                body_val = self.gen_expr(expr.body, top_level=False)
                flat = self.new_temp()
                self.generated_code.append(f"int64_t {flat} = 0;")
                self.generated_code.append(f"{flat} *= {temp}.d0;")
                self.generated_code.append(f"{flat} += {loop_index};")
                self.generated_code.append(f"{temp}.data[{flat}] = {body_val};")
                self.generated_code.append(f"{loop_index}++;")
                self.generated_code.append(f"if ({loop_index} < {bound_temps[0]})")
                self.generated_code.append(f"    goto {loop_label};")
                return temp
            else:
                temp_vars = []
                for (var, _) in reversed(expr.bounds):
                    lv = self.new_temp()
                    self.generated_code.append(f"int64_t {lv} = 0; // {var}")
                    temp_vars.append(lv)
                    self.env[var] = lv
                orig_order = list(reversed(temp_vars))
                loop_label = f"_jump{self.jump_counter}"
                self.jump_counter += 1
                self.generated_code.append(f"{loop_label}:; // Begin body of loop")
                if isinstance(expr.body, IntExpr) and expr.body.value == 1:
                    const_temp = self.new_temp()
                    self.generated_code.append(f"int64_t {const_temp} = 1;")
                    element_val = const_temp
                elif isinstance(expr.resolved_type.element_type, StructType):
                    struct_name = expr.resolved_type.element_type.name
                    struct_var = self.new_temp()
                    self.generated_code.append(f"{struct_name} {struct_var} = {{ {', '.join(orig_order)} }};")
                    element_val = struct_var
                else:
                    sum_temp = orig_order[0]
                    for lv in orig_order[1:]:
                        new_sum = self.new_temp()
                        self.generated_code.append(f"int64_t {new_sum} = {sum_temp} + {lv};")
                        sum_temp = new_sum
                    element_val = sum_temp
                flat = self.new_temp()
                self.generated_code.append(f"int64_t {flat} = 0;")
                for d in range(len(orig_order)):
                    self.generated_code.append(f"{flat} *= _0.d{d};")
                    self.generated_code.append(f"{flat} += {orig_order[d]};")
                self.generated_code.append(f"_0.data[{flat}] = {element_val};")
                self.generated_code.append(f"{temp_vars[0]}++;")
                self.generated_code.append(f"if ({temp_vars[0]} < {bound_temps[-1]})")
                self.generated_code.append(f"    goto {loop_label};")
                self.generated_code.append(f"{temp_vars[0]} = 0;")
                for i in range(1, len(temp_vars)):
                    self.generated_code.append(f"{temp_vars[i]}++;")
                    self.generated_code.append(f"if ({temp_vars[i]} < {bound_temps[len(bound_temps)-1-i]})")
                    self.generated_code.append(f"    goto {loop_label};")
                    if i < len(temp_vars) - 1:
                        self.generated_code.append(f"{temp_vars[i]} = 0;")
                self.generated_code.append(f"// End body of loop")
                return temp
        elif isinstance(expr, IntExpr):
            temp = self.new_temp()
            self.generated_code.append(f"int64_t {temp} = {expr.value};")
            return temp
        elif isinstance(expr, FloatExpr):
            temp = self.new_temp()
            val = int(expr.value)
            self.generated_code.append(f"double {temp} = {val}.0;")
            return temp
        elif isinstance(expr, TrueExpr):
            temp = self.new_temp()
            self.generated_code.append(f"bool {temp} = true;")
            return temp
        elif isinstance(expr, FalseExpr):
            temp = self.new_temp()
            self.generated_code.append(f"bool {temp} = false;")
            return temp
        elif isinstance(expr, VoidExpr):
            temp = self.new_temp()
            self.generated_code.append(f"void_t {temp} = {{}};")
            return temp
        elif isinstance(expr, VarExpr):
            if expr.name in self.env:
                return self.env[expr.name]
            return expr.name
        elif isinstance(expr, UnopExpr):
            operand_temp = self.gen_expr(expr.operand, top_level)
            temp = self.new_temp()
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {expr.op.value}{operand_temp};")
            return temp
        elif isinstance(expr, IfExpr):
            cond_temp = self.gen_expr(expr.cond, top_level)
            result_temp = self.new_temp()
            result_type = self.c_type(expr.then_branch.resolved_type)
            self.generated_code.append(f"{result_type} {result_temp};")
            self.generated_code.append(f"if (!{cond_temp})")
            self.generated_code.append(f"    goto _jump{self.jump_counter};")
            self.jump_counter += 1
            true_temp = self.gen_expr(expr.then_branch, top_level)
            self.generated_code.append(f"{result_temp} = {true_temp};")
            self.generated_code.append(f"goto _jump{self.jump_counter};")
            self.jump_counter += 1
            self.generated_code.append(f"_jump{self.jump_counter - 2}:;")
            false_temp = self.gen_expr(expr.else_branch, top_level)
            self.generated_code.append(f"{result_temp} = {false_temp};")
            self.generated_code.append(f"_jump{self.jump_counter - 1}:;")
            return result_temp
        elif isinstance(expr, ArrayIndexExpr):
            array_temp = self.gen_expr(expr.array, top_level)
            if len(expr.indexes) == 1:
                idx_var = self.gen_expr(expr.indexes[0], top_level)
                neg_label = f"_jump{self.jump_counter}"
                self.jump_counter += 1
                upper_label = f"_jump{self.jump_counter}"
                self.jump_counter += 1
                self.generated_code.append(f"if ({idx_var} >= 0)")
                self.generated_code.append(f"    goto {neg_label};")
                self.generated_code.append('fail_assertion("negative array index");')
                self.generated_code.append(f"{neg_label}:;")
                self.generated_code.append(f"if ({idx_var} < {array_temp}.d0)")
                self.generated_code.append(f"    goto {upper_label};")
                self.generated_code.append('fail_assertion("index too large");')
                self.generated_code.append(f"{upper_label}:;")
                calc_var = self.new_temp()
                self.generated_code.append(f"int64_t {calc_var} = 0;")
                self.generated_code.append(f"{calc_var} *= {array_temp}.d0;")
                self.generated_code.append(f"{calc_var} += {idx_var};")
                result_var = self.new_temp()
                result_type = self.c_type(expr.resolved_type)
                self.generated_code.append(f"{result_type} {result_var} = {array_temp}.data[{calc_var}];")
                return result_var
            else:
                index_temps = []
                for i, idx_expr in enumerate(expr.indexes):
                    if isinstance(idx_expr, IntExpr):
                        temp = self.new_temp()
                        self.generated_code.append(f"int64_t {temp} = {idx_expr.value};")
                    else:
                        temp = self.gen_expr(idx_expr, top_level)
                    index_temps.append(temp)
                for i, temp in enumerate(index_temps):
                    jump_neg = f"_jump{self.jump_counter}"
                    self.jump_counter += 1
                    self.generated_code.append(f"if ({temp} >= 0)")
                    self.generated_code.append(f"    goto {jump_neg};")
                    self.generated_code.append('fail_assertion("negative array index");')
                    self.generated_code.append(f"{jump_neg}:;")
                    jump_upper = f"_jump{self.jump_counter}"
                    self.jump_counter += 1
                    self.generated_code.append(f"if ({temp} < {array_temp}.d{i})")
                    self.generated_code.append(f"    goto {jump_upper};")
                    self.generated_code.append('fail_assertion("index too large");')
                    self.generated_code.append(f"{jump_upper}:;")
                flat_temp = self.new_temp()
                self.generated_code.append(f"int64_t {flat_temp} = 0;")
                for i, temp in enumerate(index_temps):
                    self.generated_code.append(f"{flat_temp} *= {array_temp}.d{i};")
                    self.generated_code.append(f"{flat_temp} += {temp};")
                result_temp = self.new_temp()
                result_type = self.c_type(expr.resolved_type)
                self.generated_code.append(f"{result_type} {result_temp} = {array_temp}.data[{flat_temp}];")
                return result_temp
        elif isinstance(expr, ArrayLiteralExpr):
            element_temps = []
            for element in expr.elements:
                element_temps.append(self.gen_expr(element, top_level))
            temp = self.new_temp()
            ctyp = self.c_type(expr.resolved_type)
            elem_type = self.c_type(expr.resolved_type.element_type)
            n = len(element_temps)
            self.generated_code.append(f"{ctyp} {temp};")
            self.generated_code.append(f"{temp}.d0 = {n};")
            self.generated_code.append(f"{temp}.data = jpl_alloc(sizeof({elem_type}) * {n});")
            for idx, et in enumerate(element_temps):
                self.generated_code.append(f"{temp}.data[{idx}] = {et};")
            return temp
        elif isinstance(expr, StructLiteralExpr):
            field_temps = []
            for field in expr.fields:
                field_temps.append(self.gen_expr(field, top_level))
            temp = self.new_temp()
            init = ", ".join(field_temps)
            self.generated_code.append(f"{expr.struct_name} {temp} = {{ {init} }};")
            return temp
        elif isinstance(expr, CallExpr):
            func_temp = self.gen_expr(expr.function, top_level)
            arg_temps = []
            for arg in expr.arguments:
                arg_temps.append(self.gen_expr(arg, top_level))
            temp = self.new_temp()
            args_str = ", ".join(arg_temps)
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {func_temp}({args_str});")
            return temp
        elif isinstance(expr, BinopExpr):
            if expr.op == Binop.AND:
                if top_level:
                    base = self.temp_counter
                    self.temp_counter = base + 1
                    left_result = self.gen_expr(expr.left, top_level)
                    final_temp = f"_{base}"
                    self.generated_code.append(f"{self.c_type(expr.resolved_type)} {final_temp} = {left_result};")
                    label = f"_jump{self.jump_counter}"
                    self.jump_counter += 1
                    self.generated_code.append(f"if (0 == {left_result})")
                    self.generated_code.append(f"    goto {label};")
                    right_result = self.gen_expr(expr.right, top_level)
                    self.generated_code.append(f"{final_temp} = {right_result};")
                    self.generated_code.append(f"{label}:;")
                    return final_temp
                else:
                    left_result = self.gen_expr(expr.left, top_level)
                    temp = self.new_temp()
                    self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {left_result};")
                    label = f"_jump{self.jump_counter}"
                    self.jump_counter += 1
                    self.generated_code.append(f"if (0 == {left_result})")
                    self.generated_code.append(f"    goto {label};")
                    right_result = self.gen_expr(expr.right, top_level)
                    self.generated_code.append(f"{temp} = {right_result};")
                    self.generated_code.append(f"{label}:;")
                    return temp
            elif expr.op == Binop.OR:
                if top_level:
                    base = self.temp_counter
                    self.temp_counter = base + 1
                    left_result = self.gen_expr(expr.left, top_level)
                    final_temp = f"_{base}"
                    self.generated_code.append(f"{self.c_type(expr.resolved_type)} {final_temp} = {left_result};")
                    label = f"_jump{self.jump_counter}"
                    self.jump_counter += 1
                    self.generated_code.append(f"if (0 != {left_result})")
                    self.generated_code.append(f"    goto {label};")
                    right_result = self.gen_expr(expr.right, top_level)
                    self.generated_code.append(f"{final_temp} = {right_result};")
                    self.generated_code.append(f"{label}:;")
                    return final_temp
                else:
                    left_result = self.gen_expr(expr.left, top_level)
                    temp = self.new_temp()
                    self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {left_result};")
                    label = f"_jump{self.jump_counter}"
                    self.jump_counter += 1
                    self.generated_code.append(f"if (0 != {left_result})")
                    self.generated_code.append(f"    goto {label};")
                    right_result = self.gen_expr(expr.right, top_level)
                    self.generated_code.append(f"{temp} = {right_result};")
                    self.generated_code.append(f"{label}:;")
                    return temp
            else:
                left_t = self.gen_expr(expr.left, top_level)
                right_t = self.gen_expr(expr.right, top_level)
                temp = self.new_temp()
                if expr.op == Binop.MOD and isinstance(expr.resolved_type, FloatType):
                    self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = fmod({left_t}, {right_t});")
                else:
                    op_symbol = expr.op.value
                    self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {left_t} {op_symbol} {right_t};")
                return temp
        elif isinstance(expr, ArrayLoopExpr):
            temp = self.new_temp()
            self.generated_code.append(f"/* unhandled expr: {expr.to_s_expression()} */")
            return temp
        else:
            temp = self.new_temp()
            self.generated_code.append(f"/* unhandled expr: {expr.to_s_expression()} */")
            return temp

    def generate_lvalue(self, lval: LValue) -> str:
        if isinstance(lval, VarLValue):
            return lval.name
        elif isinstance(lval, ArrayLValue):
            return lval.array
        else:
            return f"/* unhandled lvalue: {lval.to_s_expression()} */"

    def generate_command(self, cmd: Cmd):
        if isinstance(cmd, LetCmd):
            if isinstance(cmd.lvalue, ArrayLValue):
                temp = self.gen_expr(cmd.value)
                var_name = self.generate_lvalue(cmd.lvalue)
                self.env[var_name] = temp
                for idx in cmd.lvalue.indices:
                    self.env[idx] = f"{temp}.d0"
            else:
                temp = self.gen_expr(cmd.value)
                var_name = self.generate_lvalue(cmd.lvalue)
                self.env[var_name] = temp
        elif isinstance(cmd, AssertCmd):
            expr_temp = self.gen_expr(cmd.expr)
            self.generated_code.append(f"if (0 != {expr_temp})")
            self.generated_code.append(f"    goto _jump{self.jump_counter};")
            self.jump_counter += 1
            self.generated_code.append(f'fail_assertion("{cmd.message}");')
            self.generated_code.append(f"_jump{self.jump_counter - 1}:;")
        elif isinstance(cmd, ShowCmd):
            temp = self.gen_expr(cmd.expr, top_level=True)
            if isinstance(cmd.expr, VarExpr) and cmd.expr.name == "argnum":
                temp = "args.d0"
            stype = cmd.expr.resolved_type
            if isinstance(stype, ArrayType) and isinstance(stype.element_type, StructType):
                type_str = f"(ArrayType {self.struct_to_tuple_sexp(stype.element_type)} {stype.dimension})"
            elif isinstance(stype, StructType):
                type_str = self.struct_to_tuple_sexp(stype)
            else:
                type_str = stype.to_s_expression()
            self.generated_code.append(f'show("{type_str}", &{temp});')
        elif isinstance(cmd, PrintCmd):
            self.generated_code.append(f'print("{cmd.message}");')
        elif isinstance(cmd, StructCmd):
            lines = []
            lines.append("typedef struct {")
            field_types = []
            for fname, ftype in cmd.field_pairs:
                lines.append(f"    {self.c_type(ftype)} {fname};")
                field_types.append(ftype)
            lines.append(f"}} {cmd.name};")
            typedef_code = "\n".join(lines)
            self.typedefs.append(typedef_code)
            self.struct_field_map[cmd.name] = field_types
        elif isinstance(cmd, ReadCmd):
            temp = self.new_temp()
            if hasattr(cmd.lvalue, 'resolved_type'):
                ctyp = self.c_type(cmd.lvalue.resolved_type)
            elif hasattr(cmd.lvalue, 'declared_type'):
                ctyp = self.c_type(cmd.lvalue.declared_type)
            else:
                ctyp = "_a2_rgba"
            self.generated_code.append(f"{ctyp} {temp} = read_image(\"{cmd.filename}\");")
            if isinstance(cmd.lvalue, ArrayLValue):
                if cmd.lvalue.indices:
                    if len(cmd.lvalue.indices) >= 1:
                        self.generated_code.append(f"int64_t {cmd.lvalue.indices[0]} = {temp}.d0;")
                        self.env[cmd.lvalue.indices[0]] = f"{temp}.d0"
                    if len(cmd.lvalue.indices) >= 2:
                        self.generated_code.append(f"int64_t {cmd.lvalue.indices[1]} = {temp}.d1;")
                        self.env[cmd.lvalue.indices[1]] = f"{temp}.d1"
                self.env[cmd.lvalue.array] = temp
            else:
                var_name = self.generate_lvalue(cmd.lvalue)
                self.env[var_name] = temp
        elif isinstance(cmd, WriteCmd):
            expr_temp = self.gen_expr(cmd.expr)
            self.generated_code.append(f'/* write image {expr_temp} to "{cmd.filename}" */')
        elif isinstance(cmd, TimeCmd):
            self.generate_command(cmd.cmd)
        elif isinstance(cmd, FnCmd):
            self.functions.append(self.generate_function(cmd))
        else:
            self.generated_code.append(f"// Unhandled command: {cmd.to_s_expression()}")

    def generate_function(self, cmd: FnCmd) -> str:
        old_generated = self.generated_code
        old_counter = self.temp_counter
        old_jump = self.jump_counter
        old_env = self.env.copy()
        self.generated_code = []
        self.temp_counter = 0
        self.jump_counter = 1
        self.env = {}
        params = []
        if cmd.bindings:
            for binding in cmd.bindings:
                param_type = self.c_type(binding.type_node)
                if isinstance(binding.lvalue, VarLValue):
                    param_name = binding.lvalue.name
                    self.env[param_name] = param_name
                elif isinstance(binding.lvalue, ArrayLValue):
                    param_name = binding.lvalue.array
                    self.env[param_name] = param_name
                    for i, idx in enumerate(binding.lvalue.indices):
                        self.env[idx] = f"{param_name}.d{i}"
                else:
                    param_name = "unknown"
                params.append(f"{param_type} {param_name}")
            params_str = ", ".join(params)
        else:
            params_str = ""
        ret_type_str = self.c_type(cmd.return_type)
        has_return = False
        for stmt in cmd.body:
            if isinstance(stmt, ReturnStmt):
                expr_temp = self.gen_expr(stmt.expr, top_level=False)
                self.generated_code.append(f"return {expr_temp};")
                has_return = True
            elif isinstance(stmt, LetStmt):
                expr_temp = self.gen_expr(stmt.expr, top_level=False)
                self.env[self.generate_lvalue(stmt.lvalue)] = expr_temp
            else:
                self.gen_expr(stmt, top_level=False)
        if ret_type_str == "void_t" and not has_return:
            temp_void = self.new_temp()
            self.generated_code.append(f"void_t {temp_void} = {{}};")
            self.generated_code.append(f"return {temp_void};")
        body_lines = self.generated_code[:]
        self.generated_code = old_generated
        self.temp_counter = old_counter
        self.jump_counter = old_jump
        self.env = old_env
        lines = []
        lines.append(f"{ret_type_str} {cmd.name}({params_str}) {{")
        for line in body_lines:
            lines.append("    " + line)
        lines.append("}")
        return "\n".join(lines)

    def generate(self, cmds: List[Cmd]) -> str:
        self.temp_counter = 0
        self.jump_counter = 1
        self.generated_code = []
        self.typedefs = []
        self.generated_typedef_names = set()
        self.struct_field_map = {}
        self.env = {}
        self.functions = []
        # 按输入顺序逐条处理命令
        for cmd in cmds:
            self.generate_command(cmd)
        functions_code = "\n\n".join(self.functions)
        self.temp_counter = 0
        self.jump_counter = 1
        body = "\n".join("    " + line for line in self.generated_code)
        header = (
            '#include <math.h>\n'
            '#include <stdbool.h>\n'
            '#include <stdint.h>\n'
            '#include <stdio.h>\n'
            '#include "rt/runtime.h"\n'

            '\ntypedef struct { } void_t;\n\n'

        )
        # 如果有未在 typedefs 中出现但在 struct_field_map 中被引用的结构体，补充默认空定义
        for struct_name in self.struct_field_map:
            if not any(f"}} {struct_name};" in s for s in self.typedefs):
                self.typedefs.append(f"typedef struct {{ }} {struct_name};")
        type_defs_code = "\n\n".join(self.typedefs).strip()
        jpl_main = f"void jpl_main(struct args args) {{\n{body}\n}}"
        final_code = "\n".join([header, type_defs_code, functions_code, jpl_main])
        final_code += "\nCompilation succeeded"
        return final_code

    def is_sum_of_loop_vars(self, expr, expected_vars):
        vars_found = []
        def flatten(e):
            if isinstance(e, BinopExpr) and e.op == Binop.PLUS:
                flatten(e.left)
                flatten(e.right)
            elif isinstance(e, VarExpr):
                vars_found.append(e.name)
            else:
                vars_found.append(None)
        flatten(expr)
        if None in vars_found:
            return False
        return set(vars_found) == set(expected_vars) and len(vars_found) == len(expected_vars)

    def generate_multidimensional_loop_update(self, loop_vars, bounds, loop_label):
        self.generated_code.append(f"{loop_vars[0]}++;")
        self.generated_code.append(f"if ({loop_vars[0]} < {bounds[0]})")
        self.generated_code.append(f"    goto {loop_label};")
        for i in range(1, len(loop_vars)):
            self.generated_code.append(f"{loop_vars[i-1]} = 0;")
            self.generated_code.append(f"{loop_vars[i]}++;")
            self.generated_code.append(f"if ({loop_vars[i]} < {bounds[i]})")
            self.generated_code.append(f"    goto {loop_label};")

def generate_c_code(ast_cmds: List[Cmd]) -> str:
    cg = CodeGenerator()
    return cg.generate(ast_cmds)
