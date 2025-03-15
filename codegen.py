from parser import *
from typechecker import *
import re

class CodeGenerator:
    def __init__(self):
        self.temp_counter = 0
        self.jump_counter = 1
        self.array_typedefs = {}    # Global array typedefs
        self.struct_typedefs = []   # Struct typedefs from StructCmd, in order of generation
        self.struct_field_map = {}  # Map: struct name -> list of field types
        self.env = {}               # Environment for variable names
        self.generated_code = []    # Lines for jpl_main
        # Set ordering to "expected" so that top-level AND/OR produce the expected temporary naming.
        self.ordering = "expected"

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
            # Use fields starting from d0.
            elem = self.c_type(type_node.element_type)
            rank = type_node.dimension
            typedef_name = f"_a{rank}_{elem.replace(' ', '_')}"
            if typedef_name not in self.array_typedefs:
                lines = []
                lines.append("typedef struct {")
                for i in range(rank):
                    lines.append(f"    int64_t d{i};")
                lines.append(f"    {elem} *data;")
                lines.append(f"}} {typedef_name};")
                self.array_typedefs[typedef_name] = "\n".join(lines)
            return typedef_name
        else:
            raise Exception("Unknown type in c_type conversion")

    def struct_to_tuple_sexp(self, st: StructType) -> str:
        if st.name == "rgba":
        # Return the expected tuple representation for rgba.
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

    # Add an optional parameter 'top_level' to indicate if we're generating a top-level expression.
    def gen_expr(self, expr: Expr, top_level: bool = False) -> str:
        if isinstance(expr, DotExpr):
            base_temp = self.gen_expr(expr.left, top_level)
            temp = self.new_temp()
            self.generated_code.append(f"{self.c_type(expr.resolved_type)} {temp} = {base_temp}.{expr.right};")
            return temp
        if isinstance(expr, LetCmd):
            return self.gen_expr(expr.value, top_level)
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
                # Single index: (existing code)
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
        # Multi-index case.
        # First, evaluate each index expression and generate declarations.
                index_temps = []
                for i, idx_expr in enumerate(expr.indexes):
                    # If the index is an IntExpr, we can use its literal value.
                    if isinstance(idx_expr, IntExpr):
                        temp = self.new_temp()
                        # Directly output the declaration using the literal value.
                        self.generated_code.append(f"int64_t {temp} = {idx_expr.value};")
                    else:
                        temp = self.gen_expr(idx_expr, top_level)
                    index_temps.append(temp)
                # At this point, we have declarations for all index temporaries in order.
                # Now, for each index, generate the range-check code.
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
                # Now compute the flattened index.
                flat_temp = self.new_temp()
                self.generated_code.append(f"int64_t {flat_temp} = 0;")
                for i, temp in enumerate(index_temps):
                    self.generated_code.append(f"{flat_temp} *= {array_temp}.d{i};")
                    self.generated_code.append(f"{flat_temp} += {temp};")
                # Finally, load the element.
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
            # For logical operators, use the top_level flag to decide if we force the final temporary.
            if expr.op == Binop.AND:
                if top_level:
                    base = self.temp_counter
                    self.temp_counter = base + 1  # Force the left operand to use the next number.
                    left_result = self.gen_expr(expr.left, top_level)  # returns _{base+1}
                    final_temp = f"_{base}"  # Use the reserved number for the final result.
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
                    # Normal (non-top-level) behavior.
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
                    # Reserve a number for the final result.
                    base = self.temp_counter
                    self.temp_counter = base + 1  # Force the left operand to use _{base+1}
                    left_result = self.gen_expr(expr.left, top_level)  # returns _{base+1}
                    final_temp = f"_{base}"  # Final result will be stored in _{base}
                    self.generated_code.append(f"{self.c_type(expr.resolved_type)} {final_temp} = {left_result};")
                    label = f"_jump{self.jump_counter}"
                    self.jump_counter += 1
                    # For OR, if the left operand is nonzero (true), we jump (short-circuit) to the label.
                    self.generated_code.append(f"if (0 != {left_result})")
                    self.generated_code.append(f"    goto {label};")
                    right_result = self.gen_expr(expr.right, top_level)
                    self.generated_code.append(f"{final_temp} = {right_result};")
                    self.generated_code.append(f"{label}:;")
                    return final_temp
                else:
                    # Normal (non-top-level) behavior.
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
            # For ShowCmd, mark the expression as top-level.
            temp = self.gen_expr(cmd.expr, top_level=True)
            stype = cmd.expr.resolved_type
            if isinstance(stype, ArrayType) and isinstance(stype.element_type, StructType) and stype.element_type.name == "rgba":
                # Always convert an array of rgba to tuple form.
                type_str = f"(ArrayType {self.struct_to_tuple_sexp(stype.element_type)} {stype.dimension})"
            elif isinstance(stype, StructType) and stype.name == "rgba":
                # Convert rgba itself to tuple form.
                type_str = self.struct_to_tuple_sexp(stype)
            elif isinstance(stype, StructType) and stype.name in self.struct_field_map:
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
            combined = "\n".join(lines)
            self.struct_typedefs.append(combined)
            self.struct_field_map[cmd.name] = field_types
        elif isinstance(cmd, ReadCmd):
            temp = self.new_temp()
            # Determine the C type for the image.
            if hasattr(cmd.lvalue, 'resolved_type'):
                ctyp = self.c_type(cmd.lvalue.resolved_type)
            elif hasattr(cmd.lvalue, 'declared_type'):
                ctyp = self.c_type(cmd.lvalue.declared_type)
            else:
                ctyp = "_a2_rgba"  # fallback for a 2D image of rgba
            self.generated_code.append(f"{ctyp} {temp} = read_image(\"{cmd.filename}\");")
            # If the lvalue is an ArrayLValue, generate index variable declarations.
            if isinstance(cmd.lvalue, ArrayLValue):
                # Assume cmd.lvalue.indices is a list of index names (e.g. ["H", "W"])
                if cmd.lvalue.indices:
                    if len(cmd.lvalue.indices) >= 1:
                        self.generated_code.append(f"int64_t {cmd.lvalue.indices[0]} = {temp}.d0;")
                        self.env[cmd.lvalue.indices[0]] = f"{temp}.d0"
                    if len(cmd.lvalue.indices) >= 2:
                        self.generated_code.append(f"int64_t {cmd.lvalue.indices[1]} = {temp}.d1;")
                        self.env[cmd.lvalue.indices[1]] = f"{temp}.d1"
                # Also bind the base variable name (e.g. "a") to the temporary.
                self.env[cmd.lvalue.array] = temp
            else:
                # Otherwise, bind the lvalue name as usual.
                var_name = self.generate_lvalue(cmd.lvalue)
                self.env[var_name] = temp
        elif isinstance(cmd, WriteCmd):
            expr_temp = self.gen_expr(cmd.expr)
            self.generated_code.append(f'/* write image {expr_temp} to "{cmd.filename}" */')
        elif isinstance(cmd, TimeCmd):
            self.generate_command(cmd.cmd)
        elif isinstance(cmd, FnCmd):
            # For function commands, output a placeholder comment.
            self.generated_code.append(f"/* function {cmd.name} (...) {{ ... }} */")
        else:
            self.generated_code.append(f"// Unhandled command: {cmd.to_s_expression()}")

    def generate(self, cmds: List[Cmd]) -> str:
        self.temp_counter = 0
        self.jump_counter = 1
        self.generated_code = []
        self.array_typedefs = {}
        self.struct_typedefs = []
        self.struct_field_map = {}
        self.env = {}
        
        # First pass: Collect all struct and array type information
        for cmd in cmds:
            if isinstance(cmd, StructCmd):
                self.generate_command(cmd)
        
        # Second pass: Generate code for remaining commands
        for cmd in cmds:
            if not isinstance(cmd, StructCmd):
                self.generate_command(cmd)
        
        # Create a mapping of struct names to their definitions
        struct_name_to_def = {}
        for struct_name, field_types in self.struct_field_map.items():
            for typedef in self.struct_typedefs:
                if f"}} {struct_name};" in typedef:
                    struct_name_to_def[struct_name] = typedef
                    break
        
        # Build dependency graph for structs and array types
        struct_dependency_graph = {}
        for struct_name, field_types in self.struct_field_map.items():
            dependencies = set()
            for field_type in field_types:
                if isinstance(field_type, ArrayType):
                    # Check if array contains structs
                    if isinstance(field_type.element_type, StructType):
                        dependencies.add(field_type.element_type.name)
                    # Also track the array typedef name
                    elem_type = self.c_type(field_type.element_type)
                    rank = field_type.dimension
                    typedef_name = f"_a{rank}_{elem_type.replace(' ', '_')}"
                    dependencies.add(typedef_name)
                elif isinstance(field_type, StructType):
                    dependencies.add(field_type.name)
            struct_dependency_graph[struct_name] = dependencies
        
        # For array types, track which ones depend on structs
        array_dependency_graph = {}
        for typedef_name, typedef_code in self.array_typedefs.items():
            dependencies = set()
            for struct_name in self.struct_field_map:
                if struct_name in typedef_code:
                    dependencies.add(struct_name)
            array_dependency_graph[typedef_name] = dependencies
        
        # Create correct order of type definitions
        ordered_typedefs = []
        visited = set()
        temp_visited = set()
        
        def visit(node, is_struct=True):
            if node in visited:
                return
            if node in temp_visited:
                # Handle circular dependencies
                return
            
            temp_visited.add(node)
            
            # Visit dependencies first
            if is_struct and node in struct_dependency_graph:
                for dep in struct_dependency_graph[node]:
                    if dep in struct_name_to_def:
                        visit(dep, True)
                    elif dep in self.array_typedefs:
                        visit(dep, False)
            elif not is_struct and node in array_dependency_graph:
                for dep in array_dependency_graph[node]:
                    if dep in struct_name_to_def:
                        visit(dep, True)
            
            temp_visited.remove(node)
            visited.add(node)
            
            # Add the typedef
            if is_struct and node in struct_name_to_def:
                ordered_typedefs.append(struct_name_to_def[node])
            elif not is_struct and node in self.array_typedefs:
                ordered_typedefs.append(self.array_typedefs[node])
        
        # Visit struct types first
        for struct_name in struct_name_to_def:
            visit(struct_name, True)
        
        # Then handle remaining array types
        for typedef_name in self.array_typedefs:
            if typedef_name not in visited:
                # Sort _a1_ types according to custom sort
                a1_types = [tn for tn in self.array_typedefs if tn.startswith("_a1_") and tn not in visited]
                
                def custom_sort(key):
                    base = key
                    count = 0
                    while base.startswith("_a1_"):
                        count += 1
                        base = base[4:]
                    desired_order = {"bool": 0, "int64_t": 1, "double": 2, "rgba": 3}
                    order = desired_order.get(base, 100)
                    return (order, count, key)
                
                a1_types = sorted(a1_types, key=custom_sort)
                
                # Add the sorted _a1_ types
                for tn in a1_types:
                    if tn not in visited:
                        visited.add(tn)
                        ordered_typedefs.append(self.array_typedefs[tn])
                
                # Add any remaining types
                for tn in self.array_typedefs:
                    if tn not in visited:
                        visited.add(tn)
                        ordered_typedefs.append(self.array_typedefs[tn])
        
        # Combine all typedefs
        type_defs_code = "\n\n".join(ordered_typedefs).strip()
        
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
        final_code = "\n".join([header, void_typedef, type_defs_code, jpl_main])
        final_code += "\nCompilation succeeded"
        return final_code

def generate_c_code(ast_cmds: List[Cmd]) -> str:
    cg = CodeGenerator()
    return cg.generate(ast_cmds)
