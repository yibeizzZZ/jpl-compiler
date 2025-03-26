from typing import Dict, List
from parser import *
from typechecker import typecheck_program
from stack import Stack  # 从独立模块导入Stack类

def generate_asm_code(ast_cmds: List[Cmd]) -> str:
    # 创建 Stack 实例，用于追踪栈操作（注意：Stack.push/pop返回的指令文本与原来一致）
    stack = Stack()
    var_offsets: Dict[str,int] = {}
    next_local_offset = 16
    num_counter = 0
    const_table = {}
    type_const_table = {}
    data_lines = []   
    prologue_lines = []
    epilogue_lines = []
    jump_counter = 1
    fail_const = None
    fail_const_mod = None

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

    def sub_rsp(n: int, comment: str = "Add alignment") -> List[str]:
        stack.offset += n
        return [f"sub rsp, {n} ; {comment} ,new offset {stack.offset}"]

    def add_rsp(n: int, comment: str = "Remove alignment") -> List[str]:
        stack.offset -= n
        return [f"add rsp, {n} ; {comment} ,new offset {stack.offset}"]

    def get_size(type_node: TypeNode) -> int:
        if isinstance(type_node, (IntType, FloatType, BoolType)):
            return 8
        elif isinstance(type_node, VoidType):
            return 0
        elif isinstance(type_node, (StructType, ArrayType)):
            return 8
        else:
            raise Exception("Unsupported type for get_size")

    def align_stack(type_node: TypeNode) -> List[str]:
        size = get_size(type_node)
        return stack.align(size)

    def unalign_stack() -> List[str]:
        return stack.unalign()
    
    def cg_expr(expr, nested: bool = False , with_align: bool=False) -> List[str]:
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
            offset = var_offsets[expr.name]
            lines.append(";This Is From VarExpr-------")
            # lines.extend(stack.align_current())
            lines.extend(sub_rsp(8))
            lines.append(f"    mov r10, [rbp - {offset}]")
            lines.append("    mov [rsp], r10")
        elif expr.__class__.__name__ == "UnopExpr":
            if expr.op.value == '-':
                if isinstance(expr.operand.resolved_type, FloatType):
                    lines.extend(cg_expr(expr.operand, nested))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, "Remove alignment"))
                    lines.append("pxor xmm0, xmm0")
                    lines.append("subsd xmm0, xmm1")
                    lines.extend(sub_rsp(8, "Add alignment"))
                    lines.append("movsd [rsp], xmm0")
                else:
                    lines.extend(cg_expr(expr.operand, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.append("neg rax")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            elif expr.op.value == '!':
                lines.extend(cg_expr(expr.operand, nested))
                lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                lines.append("xor rax, 1")
                lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            else:
                lines.append("/* unhandled unary operator */")
        elif expr.__class__.__name__ == "BinopExpr":
            if expr.left.resolved_type.to_s_expression() == "(FloatType)":
                if expr.op.value == '%':
                    lines.extend(align_stack(expr.resolved_type))
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("call _fmod")
                    lines.extend(unalign_stack())
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpeqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpneqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("addsd xmm0, xmm1")
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("subsd xmm0, xmm1")
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("mulsd xmm0, xmm1")
                elif expr.op.value == '/':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("divsd xmm0, xmm1")
                    
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpltsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpltsd xmm1, xmm0")
                    lines.append("movq rax, xmm1")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmplesd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
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
                if expr.op.value == '/':
                    nonlocal jump_counter
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp r10, 0")
                    label_div = f".jump{jump_counter}"
                    jump_counter += 1
                    lines.append(f"jne {label_div}")
                    fail_label = get_fail_const()
                    lines.extend(align_stack(expr.resolved_type))
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'divide by zero'")
                    lines.append("call _fail_assertion")
                    lines.extend(unalign_stack()) 
                    lines.append(f"{label_div}:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '%':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp r10, 0")
                    label_mod = f".jump{jump_counter}"
                    jump_counter += 1
                    lines.append(f"jne {label_mod}")
                    fail_label = get_fail_const_mod()
                    lines.extend(align_stack(expr.resolved_type))
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'mod by zero'")
                    lines.append("call _fail_assertion")
                    lines.extend(unalign_stack())
                    lines.append(f"{label_mod}:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.append("mov rax, rdx")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("sete al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setne al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("add rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("sub rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("imul rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setl al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setg al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setle al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setge al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                else:
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
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
            if not nested and with_align:
                lines.append(";If Wrong Align In Array")
                lines.extend(align_stack(expr.resolved_type))
            for elem in reversed(expr.elements):
                lines.extend(cg_expr(elem, nested=True))
                
            lines.append(f"mov rdi, {total_size}   ; total size to allocate")
            lines.extend(align_stack(expr.resolved_type))
            lines.append(f"call _jpl_alloc ;")
            lines.extend(unalign_stack())

            lines.append(f"; Moving {total_size} bytes from rsp to rax")
            for i in range(stack_items):
                offset = (stack_items - 1 - i) * elem_size
                lines.append(f"    mov r10, [rsp + {offset}]")
                lines.append(f"    mov [rax + {offset}], r10")
            lines.extend(add_rsp(total_size, ""))
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            lines.append(f"mov rax, {n}")
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                
                
        else:
            lines.append("/* unhandled expression */")
            lines.append("mov rax, 0")
            lines.extend(stack.push("rax", get_size(expr.resolved_type)))
        return lines



    prologue_lines = []
    prologue_lines.extend(stack.push_reg("rbp", 8))
    prologue_lines.append("mov rbp, rsp")
    prologue_lines.extend(stack.push_reg("r12", 8))
    prologue_lines.append("mov r12, rbp ; end of jpl_main prelude")
    
    epilogue_lines = []
    
    body_lines = []
    for cmd in ast_cmds:
        if isinstance(cmd, LetCmd):
            lines = cg_expr(cmd.value, nested=False , with_align=False)
            var_offsets[cmd.lvalue.name] = next_local_offset
            next_local_offset += 8
            body_lines.extend(lines)
            body_lines.append(";End LetCmd Line")
            
        elif isinstance(cmd, ShowCmd):
            body_lines.extend(stack.align_current())
            if isinstance(cmd.expr, ArrayLiteralExpr):
                body_lines.extend(cg_expr(cmd.expr, nested=False, with_align=True))
            elif isinstance(cmd.expr.resolved_type, ArrayType):
                body_lines.append("; [ShowCmd] array-var path")
                body_lines.extend(sub_rsp(8))
                body_lines.extend(sub_rsp(16))
                body_lines.append("; Moving 16 bytes from rbp - 24 to rsp")
                body_lines.append("     mov r10, [rbp - 24 + 8]")
                body_lines.append("     mov [rsp + 8], r10")
                body_lines.append("     mov r10, [rbp - 24 + 0]")
                body_lines.append("     mov [rsp + 0], r10")
                
            else:
                body_lines.extend(cg_expr(cmd.expr, nested=False, with_align=False))
                
            type_lab = get_type_const(cmd.expr.resolved_type.to_s_expression())
            body_lines += [
                f"lea rdi, [rel {type_lab}]",
                "lea rsi, [rsp]",
                "call _show"
            ]
            if isinstance(cmd.expr, ArrayLiteralExpr):
                body_lines.extend(add_rsp(16, "Restore array literal result (16 bytes)"))
            body_lines.extend(add_rsp(8, "Restore result (8 bytes) "))
    

            
    total_local = next_local_offset - 16
    if total_local > 0:
        epilogue_lines.extend(stack.unalign())
        epilogue_lines.extend(add_rsp(total_local ,"Local variables"))
    epilogue_lines.extend(stack.pop("r12", 8))
    epilogue_lines.extend(stack.pop("rbp", 8))
    epilogue_lines.append("ret")
    
    
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
        "section .text",
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
