from typing import Dict, List
from parser import *
from typechecker import *
from stack import Stack  
from callingConvention import *
from dataclasses import asdict
def generate_asm_code(ast_cmds: List[Cmd]) -> str:
    stack = Stack()
    var_offsets: Dict[str,int] = {}
    next_global_offset = 16
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
 
    
    def cg_expr(expr , inFunc : bool = False) -> List[str]:
        isIn = inFunc
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
            lines.append(f"; VarExpr => local or global for {expr.name}")
            lines.extend(sub_rsp(get_size(expr.resolved_type)))
            if expr.name not in var_offsets:
                lines.append("; WARNING: variable not found!")
            else:
                value = var_offsets[expr.name]
                if isinstance(value, tuple) or not inFunc:
                    lines.append("; ;;;;;;;;;;;;;;LOCAL!!!!!!")
                    if isinstance(value, tuple):
                        stored_offset = value[0]
                        for i in range(0, get_size(expr.resolved_type), 8):
                            if i == 0:
                                effective = stored_offset - 8
                            else:
                                effective = stored_offset
                            target_offset = get_size(expr.resolved_type) - 8 - i
                            lines.append(f"mov r10, [rbp - {effective}]")
                            lines.append(f"mov [rsp+ {target_offset}], r10")
                    else:
                        stored_offset = value
                        offset = get_size(expr.resolved_type) - 8
                        while offset >= 0:
                            start = f"rbp - {var_offsets[expr.name]+ get_size(expr.resolved_type) - 8}"
                            lines.append(f"mov r10, [{start} + {offset}]")
                            lines.append(f"mov [rsp+ {offset}], r10")
                            offset -= 8

                    # stack.push(value[0] , get_size(expr.resolved_type))
                else:
                    lines.append(f"; ;;;;;;;;;;;;;;GLOBAL!!!!!! from {inFunc}")
                    offset = get_size(expr.resolved_type) - 8
                    while offset >= 0:
                        start = f"r12 - {var_offsets[expr.name]+ get_size(expr.resolved_type) - 8}"
                        lines.append(f"mov r10, [{start} + {offset}]")
                        lines.append(f"mov [rsp+ {offset}], r10")
                        offset -= 8
                    
            lines.append(f";;; now we have {var_offsets}")
   

        elif expr.__class__.__name__ == "CallExpr":
            # lines.append(f"`````````````````````{stack} ")

            
            #make a CallingConvention from f's type
            fn_type = expr.function.resolved_type
            cc = CallingConvention()
            args_info = []
            for param in fn_type.param_types:
                arg_type = type_to_str(param)  
                args_info.append((8, arg_type))
            assignments = cc.get_argument_assignments(args_info)
            
            space_needed = stack.offset - get_size(expr.resolved_type)
            lines.append(f"; Start of CallExpr with space {space_needed}")
            
            #prepare stack
            if not isinstance(expr.resolved_type, (ArrayType)):
                lines.extend(stack.align(space_needed))
            else:
                lines.extend(stack.align_current())
            
            if(isinstance(expr.resolved_type,ArrayType)) :
                lines.extend(sub_rsp(16))
                
            #generate code for args,

            for rev_idx, arg in enumerate(reversed(expr.arguments)):
                lines.extend(cg_expr(arg, inFunc))


            for param_idx, assign in enumerate(assignments):
                if isinstance(assign, tuple) and assign[0] == "array":
                    lines.append(f"; argument {param_idx} passed on stack at offset {assign[1]}")
                else:
                    reg = assign  
                    param_type = fn_type.param_types[param_idx]
                    if type_to_str(param_type) == "float":
                        lines.append(f"movsd {reg}, [rsp] ; spill float parameter to stack")
                        lines.extend(add_rsp(8, "Reserve space for float parameter"))
                    else:
                        lines.extend(stack.pop(reg, 8))
                        

            #do call
            func_name = expr.function.name  
            if(isinstance(expr.resolved_type,ArrayType)) :
                retOffset = stack.offset - 32 + stack.padding_stack[-1]
                lines.append(f"lea rdi, [rsp + {retOffset}]")
            lines.append(f"call _{func_name}")
            lines.append(f";We have assignments of {assignments}")
            for assign in assignments:
                if isinstance(assign, tuple) and assign[0] == "stack":
                    lines.extend(add_rsp(8, "free stack argument"))
                elif isinstance(assign, tuple) and assign[0] == "array":
                    lines.extend(add_rsp(16, "free stack argument"))
            
            lines.extend(stack.unalign())
            
            if not isinstance(expr.resolved_type, ArrayType):
                if isinstance(expr.resolved_type, FloatType):
                    lines.extend(sub_rsp(8))
                    lines.append("movsd [rsp], xmm0")
                else:
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                
            lines.append("; End of CallExpr")
            

        elif expr.__class__.__name__ == "UnopExpr":
            if expr.op.value == '-':
                if isinstance(expr.operand.resolved_type, FloatType):
                    lines.extend(cg_expr(expr.operand , isIn))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, "Remove alignment"))
                    lines.append("pxor xmm0, xmm0")
                    lines.append("subsd xmm0, xmm1")
                    lines.extend(sub_rsp(8, "Add alignment"))
                    lines.append("movsd [rsp], xmm0")
                else:
                    lines.extend(cg_expr(expr.operand, isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.append("neg rax")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            elif expr.op.value == '!':
                lines.extend(cg_expr(expr.operand, isIn))
                lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                lines.append("xor rax, 1")
                lines.extend(stack.push("rax", get_size(expr.resolved_type)))
            else:
                lines.append("/* unhandled unary operator */")
        elif expr.__class__.__name__ == "BinopExpr":
            if expr.left.resolved_type.to_s_expression() == "(FloatType)":
                if expr.op.value == '%':
                    lines.extend(stack.align_current())
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("call _fmod")
                    lines.extend(unalign_stack())
                elif expr.op.value == '==':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpeqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpneqsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("addsd xmm0, xmm1")
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("subsd xmm0, xmm1")
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("mulsd xmm0, xmm1")
                elif expr.op.value == '/':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("divsd xmm0, xmm1")
                    
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpltsd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmpltsd xmm1, xmm0")
                    lines.append("movq rax, xmm1")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.append("movsd xmm0, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("movsd xmm1, [rsp]")
                    lines.extend(add_rsp(8, ""))
                    lines.append("cmplesd xmm0, xmm1")
                    lines.append("movq rax, xmm0")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
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
                if expr_equal(expr.right , expr.left) and isinstance(expr.left, VarExpr) :
                    stack.push("expr_equal", 8)
                    stack.offset-=8
                
                if expr.op.value == '/':
                    nonlocal jump_counter
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
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
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
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
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("sete al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '!=':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setne al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '+':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("add rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '-':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("sub rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '*':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("imul rax, r10")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setl al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setg al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '<=':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setle al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                elif expr.op.value == '>=':
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
                    lines.extend(stack.pop("rax", get_size(expr.resolved_type)))
                    lines.extend(stack.pop("r10", 8))
                    lines.append("cmp rax, r10")
                    lines.append("setge al")
                    lines.append("and rax, 1")
                    lines.extend(stack.push("rax", get_size(expr.resolved_type)))
                else:
                    lines.extend(cg_expr(expr.right , isIn))
                    lines.extend(cg_expr(expr.left , isIn))
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

            total_size = get_size(expr.resolved_type.element_type) * n
            for elem in reversed(expr.elements):
                lines.extend(cg_expr(elem, isIn))
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
    
    def type_to_str(type_node):
        if isinstance(type_node, (IntType, BoolType)):
            return "int"
        elif isinstance(type_node, FloatType):
            return "float"
        elif isinstance(type_node, ArrayType):
            return "array"
        elif isinstance(type_node, StructType):
            return "int"
        elif isinstance(type_node, VoidType):
            return "void"
        else:
            raise Exception(f"Unsupported type: {type(type_node).__name__}")
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
    

    def pop_float_from_stack(reg: str, type_node: TypeNode) -> List[str]:
        size = get_size(type_node)
        stack.pop(reg, size)
        return [f"movsd {reg}, [rsp]", f"add rsp, {size}"]
    
    def generate_composite_return(composite_type: TypeNode) -> List[str]:
        base_size = get_size(composite_type)
        total_size = base_size
        pointer_offset = 0
        length_offset = base_size - 8
        
        instructions = []
        instructions.append("mov rax, [rbp - 8] ; Address to write return value into")
        instructions.append(f"; Moving {total_size} bytes from rsp to the return area")
        instructions.append(f"mov r10, [rsp + {length_offset}] ; get composite part (e.g., length)")
        instructions.append(f"mov [rax + {length_offset}], r10")
        instructions.append(f"mov r10, [rsp + {pointer_offset}] ; get composite part (e.g., pointer)")
        instructions.append(f"mov [rax + {pointer_offset}], r10")

        return instructions
    
    def generate_function(cmd: FnCmd) -> str:

        func_body = []
        local_offset = 16
        func_body.append(f"{cmd.name}:")
        func_body.append(f"_{cmd.name}:")
        initial_offset = stack.offset
        stack.offset = 8
        func_body.extend(stack.push_reg("rbp", 8, comment="Save old rbp"))
        func_body.append("mov rbp, rsp")
        retOffset = stack.offset
        # func_body.append(f";;;;;NEEDING PUSH RDI{isinstance(cmd.return_type,(ArrayType)) or len(cmd.bindings) > 0}")
 
        stack.push_reg("rdi" , 0)
        stack.push_reg("rdi" , 0)
 
        stack.push_reg("rdi" , 0)
        stack.push_reg("rdi" , 0) 
        stack.push_reg("rdi" , 0)
        stack.push_reg("rdi" , 0)
        func_body.append(f";;;;;;;;;;;;;Return offset set to {retOffset}")

        cc = CallingConvention()

        args_info = []
        if not isinstance(cmd.return_type,VoidType) and isinstance(cmd.return_type,(ArrayType)):
            # func_body.append(f";;;;;NEEDING PUSH RDI")
            retOffset = stack.offset
            var_offsets["$return"] = stack.offset
            func_body.extend(stack.push_reg("rdi" , 8 ))
            local_offset = stack.offset
            args_info.append((8, '$return'))
        
        for binding in cmd.bindings:
            arg_type = type_to_str(binding.type_node)  
            args_info.append((get_size(binding.type_node), arg_type))  # 假设参数大小为8字节
        assignments = cc.get_argument_assignments(args_info)


        func_body.append(f";`12`;;;;;;;;;;;;;;;;;;;{assignments}")
            
        for i, binding in enumerate(cmd.bindings):
            # 为每个参数分配一个栈地址（统一存放在 var_offsets 中）
            if isinstance(binding.type_node, ArrayType):
                arg_offset = assignments[i][1]  # assignments[i][1] 作为传递参数的偏移
                var_addr = -(stack.offset + arg_offset - 8 ) 
                if hasattr(binding.lvalue, "indices"):
                    for idx in binding.lvalue.indices:
                        var_offsets[idx] = (var_addr, "local")
            else:
                var_addr = local_offset
                local_offset += get_size(binding.type_node)
            
            assign = assignments[i]
            
            func_body.append(f";;;;;;;;;;;;;we have {assignments} , i = {i} , offset = {stack.offset}")
            if type_to_str(binding.type_node) == "array":
                stack.push_reg(assign, 0)
                func_body.append(f";;---------------------------------{binding.lvalue} ")
                
            elif isinstance(assign, tuple) and assign[0] == "stack":
                func_body.append(f"; parameter {binding.lvalue.name} passed on stack at offset {assign[1]}")
            elif type_to_str(binding.type_node) == "float":
                func_body.extend(sub_rsp(8, "Reserve space for float parameter"))
                func_body.append(f"movsd [rsp], {assign} ; spill float parameter from {assign} to stack")
                stack.push_reg(assign, 0)

            else:
                func_body.extend(stack.push_reg(assign, 8))
            
            var_offsets[binding.lvalue.name] = (var_addr, "local")
            func_body.append(f";;;;;;;;;;we have {var_offsets} in var_offsets")
            

        
        total_stack_size = cc.compute_total_stack_size()
        func_body.append(f"; Total stack space for args: {total_stack_size} bytes")

        for stmt in cmd.body:
            if isinstance(stmt, ReturnStmt):
                func_body.append(";;;This is from ReturnStmt")
                expr_lines = cg_expr(stmt.expr, inFunc=True)
                func_body.extend(expr_lines)
                if isinstance(stmt.expr.resolved_type, FloatType):
                    
                    func_body.extend(pop_float_from_stack("xmm0", stmt.expr.resolved_type))
                elif isinstance(stmt.expr.resolved_type, ArrayType):
                    func_body.extend(generate_composite_return(stmt.expr.resolved_type))
                else:
                    func_body.extend(stack.pop("rax", get_size(stmt.expr.resolved_type)))
            elif isinstance(stmt, LetStmt):
                let_lines = []
                let_lines.append(f"; Begin LetStmt for variable {stmt}")
                let_lines.extend(cg_expr(stmt.expr, inFunc=True))
                var_offsets[stmt.lvalue.name] = (local_offset, "local")
                local_offset += get_size(stmt.expr.resolved_type)
                let_lines.append(f"; Assign {stmt.lvalue.name} to stack offset {var_offsets[stmt.lvalue.name][0]}")
                func_body.extend(let_lines)
            else:
                func_body.extend(cg_expr(stmt, inFunc=True))
            
        total_local = stack.offset  - 16
        func_body.append(f"add rsp, {total_local} ; Local variables")

        while stack.peek()[0] != "rbp":
            func_body.append(f";;;;;; {stack.peek()[0]} got popped")
            stack.pop_reg(stack.peek()[0] , stack.peek()[1])

        stack.offset = initial_offset + 8
        func_body.extend(stack.pop_reg("rbp", 8, comment="Restore rbp"))
        func_body.append("ret")

        return "\n".join(func_body)

#--------------------------------------------------------------------------------
    prologue_lines = []
    prologue_lines.append("push rbp")
    prologue_lines.append("mov rbp, rsp")
    prologue_lines.append("push r12")
    prologue_lines.append("mov r12, rbp ; end of jpl_main prelude\n")
    stack.offset += 8

    
    epilogue_lines = []
    
    body_lines = []
    for cmd in ast_cmds:
        body_lines.append(f";                            Now Have Cmd {cmd}")
    for cmd in ast_cmds:
        if isinstance(cmd, FnCmd):
            functions.append(generate_function(cmd))
            
        elif isinstance(cmd, LetCmd):
            body_lines.append(f";Start LetCmd Line {cmd} for {cmd.value.resolved_type }")
            lines = cg_expr(cmd.value)
            var_offsets[cmd.lvalue.name] = next_global_offset
            next_global_offset += 8
            if isinstance(cmd.lvalue, ArrayLValue):
                element = 0
                for idx in cmd.lvalue.indices:
                    var_offsets[idx] = next_global_offset
                    element += 1
                next_global_offset +=  8 * element

            elif isinstance(cmd.value, ArrayLiteralExpr):
                next_global_offset += 8
            elif isinstance(cmd.value.resolved_type, ArrayType):
                next_global_offset += 8
            
            body_lines.extend(lines)
            body_lines.append(";End LetCmd Line\n")
            
        elif isinstance(cmd, ShowCmd):
            body_lines.append(f";;{stack.offset} ,-------showing {cmd.expr}")
            body_lines.append(f"\n    ;Start ShowCmd as {cmd.expr.resolved_type} ,NEED {get_size(cmd.expr)}")
            body_lines.extend(stack.align(get_size(cmd.expr)))
        
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
