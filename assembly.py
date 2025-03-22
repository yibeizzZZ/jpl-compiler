from typing import List
from parser import lex, Parser, Cmd, ShowCmd
from typechecker import typecheck_program, FloatType

def generate_asm_code(ast_cmds: List[Cmd]) -> str:
    num_counter = 0
    type_counter = 1
    const_table = {}
    type_const_table = {}
    num_data_lines = []
    type_data_lines = []
    prologue_lines = []
    expr_lines = []
    epilogue_lines = []
    
    def get_const(value, kind: str) -> str:
        nonlocal num_counter
        key = (kind, value)
        if key in const_table:
            return const_table[key]
        label = f"const{num_counter}"
        num_counter += 1
        const_table[key] = label
        num_data_lines.append(f"{label}: dq {value}")
        return label

    def get_fail_const() -> str:
        nonlocal num_counter
        label = f"const{num_counter}"
        num_counter += 1
        num_data_lines.append(f"{label}: db `divide by zero`, 0")
        return label

    def get_fail_const_mod() -> str:
        nonlocal num_counter
        label = f"const{num_counter}"
        num_counter += 1
        num_data_lines.append(f"{label}: db `mod by zero`, 0")
        return label

    def get_type_const(type_str: str) -> str:
        nonlocal type_counter
        if type_str in type_const_table:
            return type_const_table[type_str]
        label = f"const{type_counter}"
        type_counter += 1
        type_const_table[type_str] = label
        type_data_lines.append(f'{label}: db `{type_str}`, 0')
        return label

    def cg_expr(expr) -> List[str]:
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
                    lines.extend(cg_expr(expr.operand))
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("pxor xmm0, xmm0")
                    lines.append("subsd xmm0, xmm1")
                    lines.append("sub rsp, 8")
                    lines.append("movsd [rsp], xmm0")
                else:
                    lines.extend(cg_expr(expr.operand))
                    lines.append("pop rax")
                    lines.append("neg rax")
                    lines.append("push rax")
            elif expr.op.value == '!':
                lines.extend(cg_expr(expr.operand))
                lines.append("pop rax")
                lines.append("xor rax, 1")
                lines.append("push rax")
            else:
                lines.append("/* unhandled unary operator */")
        elif expr.__class__.__name__ == "BinopExpr":
            if expr.left.resolved_type.to_s_expression() == "(FloatType)":
                if expr.op.value == '%':
                    lines.append("sub rsp, 8 ; Add alignment")
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("call _fmod")
                    lines.append("add rsp, 8 ; Remove alignment")
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmpeqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmpneqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("addsd xmm0, xmm1")
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("subsd xmm0, xmm1")
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("mulsd xmm0, xmm1")
                elif expr.op.value == '/':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("divsd xmm0, xmm1")
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmplesd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmplesd xmm1, xmm0")
                    lines.append("movq rax, xmm1")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("movsd xmm0, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("movsd xmm1, [rsp]")
                    lines.append("add rsp, 8")
                    lines.append("cmplesd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
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
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp r10, 0")
                    lines.append("jne .jump1")
                    fail_label = get_fail_const()
                    lines.append("sub rsp, 8")
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'divide by zero'")
                    lines.append("call _fail_assertion")
                    lines.append("add rsp, 8")
                    lines.append(".jump1:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.append("push rax")
                elif expr.op.value == '%':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp r10, 0")
                    lines.append("jne .jump1")
                    fail_label = get_fail_const_mod()
                    lines.append("sub rsp, 8 ; Add alignment")
                    lines.append(f"lea rdi, [rel {fail_label}] ; 'mod by zero'")
                    lines.append("call _fail_assertion")
                    lines.append("add rsp, 8 ; Remove alignment")
                    lines.append(".jump1:")
                    lines.append("cqo")
                    lines.append("idiv r10")
                    lines.append("mov rax, rdx")
                    lines.append("push rax")
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("sete al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setne al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("add rax, r10")
                    lines.append("push rax")
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("sub rax, r10")
                    lines.append("push rax")
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("imul rax, r10")
                    lines.append("push rax")
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setl al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setg al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setle al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop rax")
                    lines.append("pop r10")
                    lines.append("cmp rax, r10")
                    lines.append("setge al")
                    lines.append("and rax, 1")
                    lines.append("push rax")
                else:
                    lines.extend(cg_expr(expr.right))
                    lines.extend(cg_expr(expr.left))
                    lines.append("pop r10")
                    lines.append("pop rax")
                    lines.append("/* unhandled binary operator */")
                    lines.append("push rax")
        elif expr.__class__.__name__ == "ArrayLiteralExpr":
            lines.append("/* array literal not implemented */")
            lines.append("mov rax, 0")
            lines.append("push rax")
        else:
            lines.append("/* unhandled expression */")
            lines.append("mov rax, 0")
            lines.append("push rax")
        return lines

    for cmd in ast_cmds:
        if isinstance(cmd, ShowCmd):
            show_cmd = cmd
            break
    if show_cmd is None:
        raise Exception("Only show commands are supported in this assignment subset.")

    prologue_lines.append("push rbp")
    prologue_lines.append("mov rbp, rsp")
    prologue_lines.append("push r12")
    prologue_lines.append("mov r12, rbp ; end of jpl_main prelude")
    expr_lines.extend(cg_expr(show_cmd.expr))
    if num_counter > type_counter:
        type_counter = num_counter
    type_str = show_cmd.expr.resolved_type.to_s_expression()
    type_lab = get_type_const(type_str)
    epilogue_lines.append(f"lea rdi, [rel {type_lab}] ; '{type_str}'")
    epilogue_lines.append("lea rsi, [rsp]")
    epilogue_lines.append("call _show")
    epilogue_lines.append("add rsp, 8")
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
    data_section = ["section .data"] + num_data_lines + type_data_lines + [""]
    text_section = [
        "section .text",
        "jpl_main:",
        "_jpl_main:"
    ]
    for line in prologue_lines:
        text_section.append("    " + line)
    for line in expr_lines:
        text_section.append("    " + line)
    for line in epilogue_lines:
        text_section.append("    " + line)
    final_lines = header_lines + data_section + text_section
    final_lines.append(" \nCompilation succeeded")
    return "\n".join(final_lines)
