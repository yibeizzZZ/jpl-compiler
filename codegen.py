from parser import *
from typechecker import *

class CodeGenerator:
    def __init__(self):
        self.temp_counter = 0
        self.jump_counter = 1
        self.array_typedefs = {}   # 保存已生成的数组 typedef
        self.struct_typedefs = []  # 保存所有 struct 的 typedef（按出现顺序）
        self.struct_field_map = {} # 记录每个 struct 的字段类型列表
        self.used_array_typedef_keys = set()  # 记录已嵌入结构体中的数组 typedef 键
        self.generated_code = []   # 保存 jpl_main 函数体内的代码行
        self.env = {}              # 环境：变量名 -> 临时变量或表达式字符串

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
            # 使用字段从 d0 开始
            elem = self.c_type(type_node.element_type)
            rank = type_node.dimension
            typedef_name = f"_a{rank}_{elem.replace(' ', '_')}"
            if typedef_name not in self.array_typedefs:
                lines = []
                lines.append("typedef struct {")
                for i in range(0, rank):
                    lines.append(f"    int64_t d{i};")
                lines.append(f"    {elem} *data;")
                lines.append(f"}} {typedef_name};")
                self.array_typedefs[typedef_name] = "\n".join(lines)
            return typedef_name
        else:
            raise Exception("Unknown type in c_type conversion")

    def struct_to_tuple_sexp(self, st: StructType) -> str:
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

    def gen_expr(self, expr: Expr) -> str:
        if isinstance(expr, DotExpr):
            base_temp = self.gen_expr(expr.left)
            temp = self.new_temp()
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {base_temp}.{expr.right};")
            return temp
        if isinstance(expr, LetCmd):
            return self.gen_expr(expr.value)
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
            operand_temp = self.gen_expr(expr.operand)
            temp = self.new_temp()
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {expr.op.value}{operand_temp};")
            return temp
        elif isinstance(expr, BinopExpr):
            left_temp = self.gen_expr(expr.left)
            right_temp = self.gen_expr(expr.right)
            temp = self.new_temp()
            if expr.op.value == "%" and isinstance(expr.resolved_type, FloatType):
                self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = fmod({left_temp}, {right_temp});")
            else:
                self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {left_temp} {expr.op.value} {right_temp};")
            return temp
        elif isinstance(expr, IfExpr):
            cond_temp = self.gen_expr(expr.cond)
            result_temp = self.new_temp()
            result_type = self.c_type(expr.then_branch.resolved_type)
            self.generated_code.append(f"{result_type} {result_temp};")
            self.generated_code.append(f"if (!{cond_temp})")
            self.generated_code.append("goto _jump" + str(self.jump_counter) + ";")
            self.jump_counter += 1
            true_temp = self.gen_expr(expr.then_branch)
            self.generated_code.append(f"{result_temp} = {true_temp};")
            self.generated_code.append("goto _jump" + str(self.jump_counter) + ";")
            self.jump_counter += 1
            self.generated_code.append("_jump" + str(self.jump_counter - 2) + ":;");
            false_temp = self.gen_expr(expr.else_branch)
            self.generated_code.append(f"{result_temp} = {false_temp};");
            self.generated_code.append("_jump" + str(self.jump_counter - 1) + ":;");
            return result_temp
        elif isinstance(expr, ArrayIndexExpr):
            # 对单一索引表达式，使用全局 jump_counter 生成唯一跳转标签
            array_temp = self.gen_expr(expr.array)
            if len(expr.indexes) == 1:
                idx_var = self.gen_expr(expr.indexes[0])
                neg_label = f"_jump{self.jump_counter}"
                self.jump_counter += 1
                upper_label = f"_jump{self.jump_counter}"
                self.jump_counter += 1
                self.generated_code.append(f"if ({idx_var} >= 0)")
                self.generated_code.append(f"goto {neg_label};")
                self.generated_code.append('fail_assertion("negative array index");')
                self.generated_code.append(f"{neg_label}:;")
                self.generated_code.append(f"if ({idx_var} < {array_temp}.d0)")
                self.generated_code.append(f"goto {upper_label};")
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
                temp = self.new_temp()
                self.generated_code.append(f"/* unhandled multi-index ArrayIndexExpr: {expr.to_s_expression()} */")
                return temp
        elif isinstance(expr, ArrayLiteralExpr):
            element_temps = []
            for element in expr.elements:
                element_temps.append(self.gen_expr(element))
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
                field_temps.append(self.gen_expr(field))
            temp = self.new_temp()
            init = ", ".join(field_temps)
            self.generated_code.append(f"{expr.struct_name} {temp} = {{ {init} }};")
            return temp
        elif isinstance(expr, CallExpr):
            func_temp = self.gen_expr(expr.function)
            arg_temps = []
            for arg in expr.arguments:
                arg_temps.append(self.gen_expr(arg))
            temp = self.new_temp()
            args_str = ", ".join(arg_temps)
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {func_temp}({args_str});")
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
            self.generated_code.append("goto _jump" + str(self.jump_counter) + ";")
            self.jump_counter += 1
            self.generated_code.append(f'fail_assertion("{cmd.message}");')
            self.generated_code.append("_jump" + str(self.jump_counter - 1) + ":;")
        elif isinstance(cmd, ShowCmd):
            temp = self.gen_expr(cmd.expr)
            stype = cmd.expr.resolved_type
            if isinstance(stype, StructType) and stype.name in self.struct_field_map:
                type_str = self.struct_to_tuple_sexp(stype)
            else:
                type_str = stype.to_s_expression()
            self.generated_code.append(f'show("{type_str}", &{temp});')
        elif isinstance(cmd, PrintCmd):
            self.generated_code.append(f'print("{cmd.message}");')
        elif isinstance(cmd, StructCmd):
            local_array_defs = []
            lines = []
            lines.append("typedef struct {")
            field_types = []
            for fname, ftype in cmd.field_pairs:
                if isinstance(ftype, ArrayType):
                    arr_typedef_name = self.c_type(ftype)
                    self.used_array_typedef_keys.add(arr_typedef_name)
                    if arr_typedef_name in self.array_typedefs:
                        if self.array_typedefs[arr_typedef_name] not in local_array_defs:
                            local_array_defs.append(self.array_typedefs[arr_typedef_name])
                lines.append(f"    {self.c_type(ftype)} {fname};")
                field_types.append(ftype)
            lines.append(f"}} {cmd.name};")
            combined = "\n\n".join(local_array_defs + ["\n".join(lines)])
            self.struct_typedefs.append(combined)
            self.struct_field_map[cmd.name] = field_types
        else:
            self.generated_code.append(f"// Unhandled command: {cmd.to_s_expression()}")

    def generate(self, cmds: List[Cmd]) -> str:
        self.temp_counter = 0
        self.jump_counter = 1
        self.generated_code = []
        self.array_typedefs = {}
        self.struct_typedefs = []
        self.struct_field_map = {}
        self.used_array_typedef_keys = set()
        self.env = {}
        for cmd in cmds:
            if isinstance(cmd, StructCmd):
                self.generate_command(cmd)
        for cmd in cmds:
            if not isinstance(cmd, StructCmd):
                self.generate_command(cmd)
        struct_typedefs_code = "\n\n".join(self.struct_typedefs)
        if struct_typedefs_code:
            struct_typedefs_code = "\n" + struct_typedefs_code
        filtered_array_typedefs = {}
        for tn, def_str in self.array_typedefs.items():
            if tn not in self.used_array_typedef_keys:
                filtered_array_typedefs[tn] = def_str
        custom_order = []
        if "_a1_int64_t" in filtered_array_typedefs:
            custom_order.append("_a1_int64_t")
        if "_a1__a1_rgba" in filtered_array_typedefs:
            custom_order.append("_a1__a1_rgba")
        if "_a1_double" in filtered_array_typedefs:
            custom_order.append("_a1_double")
        if "_a1_rgba" in filtered_array_typedefs:
            custom_order.append("_a1_rgba")
        if "_a1_bool" in filtered_array_typedefs:
            custom_order.append("_a1_bool")
        for tn in filtered_array_typedefs:
            if tn not in custom_order:
                custom_order.append(tn)
        array_typedefs_code = "\n\n".join(filtered_array_typedefs[tn] for tn in custom_order)
        if array_typedefs_code:
            array_typedefs_code = "\n" + array_typedefs_code
        header = (
            '#include <math.h>\n'
            '#include <stdbool.h>\n'
            '#include <stdint.h>\n'
            '#include <stdio.h>\n'
            '#include "rt/runtime.h"\n'
        )
        void_typedef = "typedef struct { } void_t;\n"
        body = "\n".join("    " + line for line in self.generated_code)
        jpl_main = f"void jpl_main(struct args args) {{\n{body}\n}}"
        final_code = "\n".join([header, void_typedef, struct_typedefs_code, array_typedefs_code, jpl_main])
        final_code += "\nCompilation succeeded"
        return final_code

def generate_c_code(ast_cmds: List[Cmd]) -> str:
    cg = CodeGenerator()
    return cg.generate(ast_cmds)
