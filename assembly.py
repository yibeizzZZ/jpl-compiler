from typing import List
from parser import lex, Parser, Cmd, ShowCmd, IntType, FloatType, BoolType
from typechecker import typecheck_program

def generate_asm_code(ast_cmds: List[Cmd]) -> str:
    num_counter = 0
    const_table = {}
    type_const_table = {}
    data_lines = []   
    prologue_lines = []
    epilogue_lines = []
    fail_const = None
    fail_const_mod = None
    jump_counter = 1
    
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

    # 参数 nested 用于控制是否在内部递归中插入对齐指令（仅在最外层添加一次）
    def cg_expr(expr, nested: bool = False) -> List[str]:
        lines = []
        if expr.__class__.__name__ == "IntExpr":
            lab = get_const(expr.value, "int")
            lines.append(f"mov rax, [rel {lab}] ; {expr.value}")
            lines.append("push rax")
        elif expr.__class__.__name__ == "FloatExpr":
            lab = get_const(expr.value, "float")
            lines.append(f"mov rax, [rel {lab}] ; {expr.value}")
            lines.append("push rax")
        elif expr.__class__.__name__ == "TrueExpr":
            lab = get_const(1, "int")
            lines.append(f"mov rax, [rel {lab}] ; true")
            lines.append("push rax")
        elif expr.__class__.__name__ == "FalseExpr":
            lab = get_const(0, "int")
            lines.append(f"mov rax, [rel {lab}] ; false")
            lines.append("push rax")
        elif expr.__class__.__name__ == "UnopExpr":
            if expr.op.value == '-':
                if isinstance(expr.operand.resolved_type, FloatType):
                    lines.extend(cg_expr(expr.operand, nested))
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("pxor xmm0, xmm0")
                    lines.append("subsd xmm0, xmm1")
                    lines.append("sub rsp, 8")
                    lines.append("movsd [rsp], xmm0")
                else:
                    lines.extend(cg_expr(expr.operand, nested))
                    lines.append("pop rax")
                    lines.append("neg rax")
                    lines.append("push rax")
            elif expr.op.value == '!':
                lines.extend(cg_expr(expr.operand, nested))
                lines.append("pop rax")
                lines.append("xor rax, 1")
                lines.append("push rax")
            else:
                lines.append("/* unhandled unary operator */")
        elif expr.__class__.__name__ == "BinopExpr":
            if expr.left.resolved_type.to_s_expression() == "(FloatType)":
                if expr.op.value == '%':
                    lines.append("sub rsp, 8 ; Add alignment")
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("call _fmod")
                    lines.append("add rsp, 8 ; Remove alignment")
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmpeqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmpneqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("addsd xmm0, xmm1")
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("subsd xmm0, xmm1")
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("mulsd xmm0, xmm1")
                elif expr.op.value == '/':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("divsd xmm0, xmm1")
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmpltsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmpltsd xmm1, xmm0")
                    lines.append("movq rax, xmm1")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmplesd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmplesd xmm1, xmm0")
                    lines.append("movq rax, xmm1")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                else:
                    lines.append("/* unhandled float binary operator */")
                if expr.op.value in ('+', '-', '*', '/', '%'):
                    lines.append("sub rsp, 8")
                    lines.append("movsd [rsp], xmm0")
            else:
                if expr.op.value == '/':
                    nonlocal jump_counter
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp r10, 0")
                    label_div = f".jump{jump_counter}"
                    jump_counter += 1
                    lines.append(f"jne {label_div}")
                    fail_label = get_fail_const()
                    lines.append("sub rsp, 8 ; Add alignment mod")
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'divide by zero'")
                    lines.append("call _fail_assertion")
                    lines.append("add rsp, 8")
                    lines.append(f"{label_div}:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.append("push rax")
                elif expr.op.value == '%':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp r10, 0")
                    label_mod = f".jump{jump_counter}"
                    jump_counter += 1
                    lines.append(f"jne {label_mod}")
                    fail_label = get_fail_const_mod()
                    lines.append("sub rsp, 8 ; Add alignment mod")
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'mod by zero'")
                    lines.append("call _fail_assertion")
                    lines.append("add rsp, 8 ; Remove alignment")
                    lines.append(f"{label_mod}:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.append("mov rax, rdx")
                    lines.append("push rax")
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("sete al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setne al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("add rax, r10")
                    lines.append("push rax")
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("sub rax, r10")
                    lines.append("push rax")
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("imul rax, r10")
                    lines.append("push rax")
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setl al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setg al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setle al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setge al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                else:
                    lines.extend(cg_expr(expr.right, nested))
                    lines.extend(cg_expr(expr.left, nested))
                    lines.append("pop r10")
                    lines.append("pop rax")
                    lines.append("/* unhandled binary operator */")
                    lines.append("push rax")
                    
                    
                        
        elif expr.__class__.__name__ == "ArrayLiteralExpr":
            n = len(expr.elements)
            if isinstance(expr.resolved_type.element_type, (IntType, FloatType, BoolType)):
                items_per_elem = 1
            else:
                items_per_elem = 2
            stack_items = n * items_per_elem
            elem_size = 8
            total_size = stack_items * elem_size
            if not nested:
                lines.append("sub rsp, 8 ; Add alignment")
            for elem in reversed(expr.elements):
                lines.extend(cg_expr(elem, nested=True))
                
            lines.append(f"mov rdi, {total_size}")
            if (items_per_elem == 1 and n == 1) or (n > 1 and n %2 == 1 and items_per_elem == 1):
                lines.append(f"sub rsp, 8 ; Add alignment")
            lines.append(f"call _jpl_alloc ;{items_per_elem} , {n} , {n%2}")
            if (items_per_elem == 1 and n == 1) or (n > 1 and n %2 == 1 and items_per_elem == 1):
                lines.append("add rsp, 8 ; Remove alignment")
                            
            lines.append(f"; Moving {total_size} bytes from rsp to rax")
            for i in range(stack_items):
                offset = (stack_items - 1 - i) * elem_size
                lines.append(f"    mov r10, [rsp + {offset}]")
                lines.append(f"    mov [rax + {offset}], r10")
            lines.append(f"add rsp, {total_size}")
            lines.append("push rax")
            # 将逻辑长度 n 压入栈中（而非 stack_items）
            lines.append(f"mov rax, {n}")
            lines.append("push rax")

                        
                
        else:
            lines.append("/* unhandled expression */")
            lines.append("mov rax, 0")
            lines.append("push rax")
        return lines

    show_cmds = [cmd for cmd in ast_cmds if isinstance(cmd, ShowCmd)]
    if not show_cmds:
        raise Exception("No show commands found.")

    prologue_lines = [
        "push rbp",
        "mov rbp, rsp",
        "push r12",
        "mov r12, rbp ; end of jpl_main prelude"
    ]
    
    epilogue_lines = []
    
    body_lines = []
    for cmd in show_cmds:
        lines = cg_expr(cmd.expr, nested=False)
        body_lines.extend(lines)

        type_str = cmd.expr.resolved_type.to_s_expression()
        type_lab = get_type_const(type_str)

        if cmd.expr.__class__.__name__ == "ArrayLiteralExpr":
            extra_restore = "add rsp, 16    ; Restore array literal result (16 bytes)"
        else:
            extra_restore = ""
        
        body_lines.extend([
            f"lea rdi, [rel {type_lab}] ; '{type_str}'",
            "lea rsi, [rsp]",
            "call _show",
            extra_restore,
            "add rsp, 8     ; Restore alignment (8 bytes)"
        ])

    
    
    epilogue_lines.append("pop r12 ; begin jpl_main postlude")
    epilogue_lines.append("pop rbp")
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
    text_section.append("    pop r12 ; begin jpl_main postlude")
    text_section.append("    pop rbp")
    text_section.append("    ret")
    final_lines = header_lines + data_section + text_section
    final_lines.append(" \nCompilation succeeded")
    return "\n".join(final_lines)
