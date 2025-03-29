from typing import Dict, List
from parser import *
from typechecker import typecheck_program
from stack import Stack  
from callingConvention import *
from dataclasses import asdict
def generate_asm_code(ast_cmds: List[Cmd]) -> str:
    stack = Stack()
    var_offsets: Dict[str,int] = {}
    next_local_offset = 16
    num_counter = 0
    const_table = {}
    type_const_table = {}
    data_lines = []   
    prologue_lines = []
    epilogue_lines = []
    functions = []
    jump_counter = 1
    fail_const = None
    fail_const_mod = None
    literal_flags: Dict[str, bool] = {}
    
    def cg_expr(expr) -> List[str]:
        lines = []
        if expr.__class__.__name__ == "IntExpr":
            lab = get_const(expr.value, "int")
            lines.append(f"mov rax, [rel {lab}] ; {expr.value}")
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            
            
        elif expr.__class__.__name__ == "FloatExpr":
            lab = get_const(expr.value, "float")
            lines.append(f"mov rax, [rel {lab}] ; {expr.value}")
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
        elif expr.__class__.__name__ == "TrueExpr":
            lab = get_const(1, "int")
            lines.append(f"mov rax, [rel {lab}] ; true")
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
        elif expr.__class__.__name__ == "FalseExpr":
            lab = get_const(0, "int")
            lines.append(f"mov rax, [rel {lab}] ; false")
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
        elif expr.__class__.__name__ == "VarExpr":
            lines.append("; VarExpr => local or global")
            lines.extend(sub_rsp(get_size(expr.resolved_type)))
            offset = get_size(expr.resolved_type) - 8
            if expr.name in var_offsets:
                now_place = var_offsets[expr.name]
                while offset >= 0:
                    start = f"rbp - {now_place}"
                    lines.append(f"mov r10, [{start} + {offset}]")
                    lines.append(f"mov [rsp+ {offset}], r10")
                    offset -= 8
                    now_place -= 8
            else:
                start = "start"

            

                

        elif expr.__class__.__name__ == "CallExpr":
            

            # 计算 total_stack 与 return_value_space

            # 1) 计算 total_stack：每个参数占用的空间之和
            total_stack = sum(get_size(arg.resolved_type) for arg in expr.arguments)
            if total_stack == 0:
                total_stack = 8  # 至少分配 8 字节

            # 2) 计算返回值空间（简单类型返回值不用额外空间）
            if isinstance(expr.resolved_type, (ArrayType, StructType)):
                return_value_space = get_size(expr.resolved_type)
            else:
                return_value_space = 0
            space_needed = total_stack - return_value_space
            lines.append(f"; Start of CallExpr with space {space_needed}")
            # 调用 stack.align 并用 extend 添加生成的指令
            lines.extend(stack.align_current())
            # 生成实参代码（从右到左）
            for arg in reversed(expr.arguments):
                lines.extend(cg_expr(arg))

            # 调用函数
            func_name = expr.function.name  # 假设 function 是 VarExpr
            lines.append(f"call _{func_name}")

            # # 还原对齐：同样用 extend
            lines.extend(stack.unalign())

            # 将返回值 (rax) 压栈
            if isinstance(expr.resolved_type, FloatType):
                # Instead of pushing into rax, load the float from the stack directly into xmm0:
                lines.append(f"sub rsp, {get_size(expr.resolved_type)}")
                lines.append("movsd [rsp], xmm0")
            else:
                lines.extend(stack.push("rax", get_size(expr.resolved_type)))

            lines.append("; End of CallExpr")
            

        elif expr.__class__.__name__ == "UnopExpr":
            if expr.op.value == '-':
                if isinstance(expr.operand.resolved_type, FloatType):
                    lines.extend(cg_expr(expr.operand))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, "Remove alignment"))
                    lines.append("pxor xmm0, xmm0")
                    lines.append("subsd xmm0, xmm1")
                    lines.extend(sub_rsp(8, "Add alignment"))
                    lines.append("movsd [rsp], xmm0")
                else:
                    lines.extend(cg_expr(expr.operand))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.append("neg rax")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            elif expr.op.value == '!':
                lines.extend(cg_expr(expr.operand))
                lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                lines.append("xor rax, 1")
                lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            else:
                lines.append("/* unhandled unary operator */")
        elif expr.__class__.__name__ == "BinopExpr":
            if expr.left.resolved_type.to_s_expression() == "(FloatType)":
                if expr.op.value == '%':
                    lines.extend(stack.align_current())
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("call _fmod")
                    lines.extend(unalign_stack())
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpeqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpneqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("addsd xmm0, xmm1")
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("subsd xmm0, xmm1")
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("mulsd xmm0, xmm1")
                elif expr.op.value == '/':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("divsd xmm0, xmm1")
                    
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpltsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpltsd xmm1, xmm0")
                    lines.append("movq rax, xmm1")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmplesd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmplesd xmm1, xmm0")
                    lines.append("movq rax, xmm1")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                else:
                    lines.append("/* unhandled float binary operator */")
                if expr.op.value in ('+', '-', '*', '/', '%'):
                    lines.extend(sub_rsp(8, ""))
                    lines.append("movsd [rsp], xmm0 ; xxx")
            else:
                if expr_equal(expr.right , expr.left):
                    stack.push("", 8)
                    stack.offset-=8
                
                if expr.op.value == '/':
                    nonlocal jump_counter
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp r10, 0")
                    label_div = f".jump{jump_counter}"
                    jump_counter += 1
                    lines.append(f"jne {label_div}")
                    fail_label = get_fail_const()

                    lines.extend(stack.align_current())
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'divide by zero'")
                    lines.append("call _fail_assertion")
                    lines.extend(unalign_stack()) 
                    lines.append(f"{label_div}:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '%':
                    lines.append(";;;Start mod")
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp r10, 0")
                    label_mod = f".jump{jump_counter}"
                    jump_counter += 1
                    lines.append(f"jne {label_mod}")
                    fail_label = get_fail_const_mod()
                    lines.extend(stack.align_current())
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'mod by zero'")
                    lines.append("call _fail_assertion")
                    lines.extend(unalign_stack())
                    lines.append(f"{label_mod}:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.append("mov rax, rdx")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("sete al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    # lines.append(f"{stack}")
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setne al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("add rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("sub rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("imul rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setl al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setg al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setle al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setge al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                else:
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.extend(stack.pop("r10", 8))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.append("/* unhandled binary operator */")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))

        elif expr.__class__.__name__ == "ArrayLiteralExpr":
            n = len(expr.elements)
            if isinstance(expr.resolved_type.element_type, (IntType, FloatType, BoolType)):
                items_per_elem = 1
            else:
                items_per_elem = 2
            stack_items = n * items_per_elem
            elem_size = 8
            total_size = stack_items * elem_size

            for elem in reversed(expr.elements):
                lines.extend(cg_expr(elem))
                
            lines.append(f"mov rdi, {total_size}   ; total size to allocate")
            lines.extend(stack.align_current())
            lines.append(f"call _jpl_alloc ;")
            lines.extend(unalign_stack())

            lines.append(f"; Moving {total_size} bytes from rsp to rax")
            for i in range(stack_items):
                offset = (stack_items - 1 - i) * elem_size
                lines.append(f"    mov r10, [rsp + {offset}]")
                lines.append(f"    mov [rax + {offset}], r10")
                
            lines.extend(add_rsp(total_size, ""))
            lines.extend(stack.push_reg("rax", 8))
            lines.append(f"mov rax, {n}")
            lines.extend(stack.push_reg("rax", 8))
                
                
        else:
            lines.append("/* unhandled expression */")
            lines.append("mov rax, 0")
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
        return lines
    
    def get_const(value, kind: str) -> str:
        nonlocal num_counter
        key = (kind, value)
        if key in const_table:
            return const_table[key]
        label = f"const{num_counter}"
        num_counter += 1
        const_table[key] = label
        data_lines.append(f"{label}: dq {value}")
        return label

    def get_fail_const() -> str:
        nonlocal num_counter, fail_const
        if fail_const is not None:
            return fail_const
        label = f"const{num_counter}"
        num_counter += 1
        fail_const = label
        data_lines.append(f"{label}: db `divide by zero`, 0")
        return label

    def get_fail_const_mod() -> str:
        nonlocal num_counter, fail_const_mod
        if fail_const_mod is not None:
            return fail_const_mod
        label = f"const{num_counter}"
        num_counter += 1
        fail_const_mod = label
        data_lines.append(f"{label}: db `mod by zero`, 0")
        return label

    def get_type_const(type_str: str) -> str:
        nonlocal num_counter
        if type_str in type_const_table:
            return type_const_table[type_str]
        label = f"const{num_counter}"
        num_counter += 1
        type_const_table[type_str] = label
        data_lines.append(f'{label}: db `{type_str}`, 0')
        return label
    
    def expr_equal(e1, e2) -> bool:
        if type(e1) != type(e2):
            return False
        d1 = asdict(e1)
        d2 = asdict(e2)
        d1.pop("start_idx", None)
        d2.pop("start_idx", None)
        d1.pop("resolved_type", None)
        d2.pop("resolved_type", None)   
        return d1 == d2
    def sub_rsp(n: int, comment: str = "pop stack") -> List[str]:
        if n == 0:
            return
        stack.offset += n
        return [f"sub rsp, {n} ; {comment} ,new offset {stack.offset}"]

    def add_rsp(n: int, comment: str = "push stack") -> List[str]:
        if n == 0:
            return
        stack.offset -= n
        return [f"add rsp, {n} ; {comment} ,new offset {stack.offset}"]
    
    def get_size(type_node: TypeNode) -> int:
        if isinstance(type_node, (ArrayType)):
            return 16
        elif isinstance(type_node, (IntType, FloatType, BoolType)):
            return 8
        elif isinstance(type_node, (VoidType , StructType)):
            raise Exception(f"Unsupported type for get_size : {type(type_node).__name__}: {type_node}")
        
        else:
            return get_size(type_node.resolved_type)
        
    def unalign_stack() -> List[str]:
        
        return stack.unalign()
    
    def calculate_total_size(array_expr: ArrayLiteralExpr) -> int:
        n = len(array_expr.elements)
        if isinstance(array_expr.resolved_type.element_type, (IntType, FloatType, BoolType)):
            items_per_elem = 1
        else:
            items_per_elem = 2
        stack_items = n * items_per_elem
        elem_size = 8
        total_size = stack_items * elem_size
        return total_size
    
    def pop_float_from_stack(reg: str, type_node: TypeNode) -> List[str]:
        size = get_size(type_node)
        stack.pop(reg, size)
        return [f"movsd {reg}, [rsp]", f"add rsp, {size}"]
        
    def generate_function(cmd: FnCmd) -> str:
        func_body = []
        # 插入入口标签
        func_body.append(f"{cmd.name}:")
        func_body.append(f"_{cmd.name}:")
        
        # 根据 FnCmd 构造 CallingConvention
        cc = CallingConvention.from_fncmd(cmd, stack, var_offsets)
        
        # 前序部分
        func_body.extend(cc.generate_prologue())
        initial_offset = stack.offset
        
        # 参数分配
        if cmd.bindings:
            func_body.extend(cc.allocate_args(cmd))
        
        # 函数体（例如，生成返回语句的代码）
        for stmt in cmd.body:
            if isinstance(stmt, ReturnStmt):
                expr_lines = cg_expr(stmt.expr)
                func_body.extend(expr_lines)
                if isinstance(stmt.expr.resolved_type, FloatType):
                    func_body.extend(pop_float_from_stack("xmm0", stmt.expr.resolved_type))
                elif isinstance(stmt.expr.resolved_type, ArrayType):
                    composite_size = 16
                    func_body.append("mov rax, [rbp - 8] ; Address to write return value into")
                    func_body.append(f"; Moving {composite_size} bytes from rsp to rax")
                    # Copy the composite value from the stack into the caller's return area.
                    func_body.append("mov r10, [rsp + 8] ; get composite part (e.g., length)")
                    func_body.append("mov [rax + 8], r10")
                    func_body.append("mov r10, [rsp + 0] ; get composite part (e.g., pointer)")
                    func_body.append("mov [rax + 0], r10")
                    # Clean up the 16 bytes from the stack that held the composite value.
                else:
                    func_body.extend(stack.pop("rax", get_size(stmt.expr.resolved_type)))
                    
            else:
                func_body.extend(cg_expr(stmt))
        
        total_local = stack.offset - initial_offset
        func_body.append(f"add rsp, {total_local} ; Local variables")
        
        if isinstance(cmd.return_type, ArrayType):
            func_body.append("pop rbp")
            pass
        else:
            func_body.extend(stack.pop_reg("rbp", 8))
        func_body.append("ret")
        return "\n".join(func_body)

    prologue_lines = []
    prologue_lines.append("push rbp")
    prologue_lines.append("mov rbp, rsp")
    prologue_lines.append("push r12")
    prologue_lines.append("mov r12, rbp ; end of jpl_main prelude\n")
    stack.offset += 8
    
    epilogue_lines = []
    
    body_lines = []
    for cmd in ast_cmds:
        if isinstance(cmd, FnCmd):
            functions.append(generate_function(cmd))
            
        elif isinstance(cmd, LetCmd):
            lines = cg_expr(cmd.value,)
            var_offsets[cmd.lvalue.name] = next_local_offset
            next_local_offset += 8
            if isinstance(cmd.lvalue, ArrayLValue):
                for idx in cmd.lvalue.indices:
                    var_offsets[idx] = next_local_offset
                    next_local_offset += 8
            if isinstance(cmd.value, ArrayLiteralExpr):
                literal_flags[cmd.lvalue.name] = True
                next_local_offset += 8  
            else:
                literal_flags[cmd.lvalue.name] = False
            body_lines.extend(lines)
            body_lines.append(";End LetCmd Line\n")
            
        elif isinstance(cmd, ShowCmd):
            body_lines.append(f"\n    ;Start ShowCmd {cmd.expr} as {cmd.expr.resolved_type} ,NEED {get_size(cmd.expr)}")
            body_lines.extend(stack.align(get_size(cmd.expr)))
            
            literal_flag = False
            if isinstance(cmd.expr, VarExpr):
                literal_flag = literal_flags.get(cmd.expr.name)
                
            if isinstance(cmd.expr, CallExpr) and isinstance(cmd.expr.resolved_type, ArrayType):
                body_lines.extend(sub_rsp(8))
                body_lines.extend(sub_rsp(16))
                body_lines.append("lea rdi, [rsp]")
                body_lines.extend(cg_expr(cmd.expr))

            else:
                body_lines.extend(cg_expr(cmd.expr))
            
            type_lab = get_type_const(cmd.expr.resolved_type.to_s_expression())
            body_lines += [
                f"lea rdi, [rel {type_lab}]",
                "lea rsi, [rsp]",
                "call _show"
            ]
            body_lines.extend(add_rsp(get_size(cmd.expr.resolved_type)))
            body_lines.extend(stack.unalign())
            body_lines.append(f";End of ShowCmd \n")
    

            
    total_local = stack.offset  - 8
    if total_local > 0:
        epilogue_lines.extend(add_rsp(total_local ,"Local variables"))
    epilogue_lines.append("pop r12")
    epilogue_lines.append("pop rbp")
    epilogue_lines.append("ret")
    functions_code = "\n\n".join(functions)
    
    header_lines = [
        "global jpl_main",
        "global _jpl_main",
        "extern _fail_assertion",
        "extern _jpl_alloc",
        "extern _get_time",
        "extern _show",
        "extern _print",
        "extern _print_time",
        "extern _read_image",
        "extern _write_image",
        "extern _fmod",
        "extern _sqrt",
        "extern _exp",
        "extern _sin",
        "extern _cos",
        "extern _tan",
        "extern _asin",
        "extern _acos",
        "extern _atan",
        "extern _log",
        "extern _pow",
        "extern _atan2",
        "extern _to_int",
        "extern _to_float",
        ""
    ]
    data_section = ["section .data"] + ["  " + line for line in data_lines] + [""]
    text_section = [
        "section .text"
    ]

    # Insert function definitions:
    text_section.append(functions_code)
    text_section.append("")
    text_section += [
        "jpl_main:",
        "_jpl_main:"
    ]
    for line in prologue_lines:
        text_section.append("    " + line)
    for line in body_lines:
        text_section.append("    " + line)
    for line in epilogue_lines:
        text_section.append("    " + line)
    final_lines = header_lines + data_section + text_section
    final_lines.append(" \nCompilation succeeded")
    return "\n".join(final_lines)
