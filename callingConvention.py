from typing import Dict, List
from parser import FnCmd
from typechecker import FnType, IntType, FloatType, ArrayType, StructType, BoolType, VoidType
# 假设 get_size 已经定义在本模块或其他地方
def get_size(type_node) -> int:
    if isinstance(type_node, ArrayType):
        return 16
    elif isinstance(type_node, (IntType, FloatType, BoolType)):
        return 8
    elif isinstance(type_node, (VoidType, StructType)):
        raise Exception(f"Unsupported type for get_size : {type(type_node).__name__}: {type_node}")
    else:
        # 如果存在 resolved_type
        return get_size(type_node.resolved_type)
    


class CallingConvention:
    def __init__(self, fn_type: FnType, stack, var_offsets: Dict[str, int]):
        self.fn_type = fn_type          
        self.stack = stack              
        self.var_offsets = var_offsets 

        self.int_arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
        self.float_arg_regs = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]

        self.int_used = 0
        self.float_used = 0

    @classmethod
    def recieve_args(cls, cmd: FnCmd, stack, var_offsets: Dict[str, int]) -> List[str]:
        lines: List[str] = []

        param_registers = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
        reg_index = 0

        for binding in cmd.bindings:
            # 这里假设 binding 中有 lvalue 和 type_node 两个属性
            # 如果类型简单且寄存器空闲，则参数来自寄存器：
            if reg_index < len(param_registers) and isinstance(binding.type_node, (IntType, FloatType, BoolType)):
                reg = param_registers[reg_index]
                reg_index += 1
                lines.append(f"; Receiving parameter {binding.lvalue.to_s_expression()} from register {reg}")
                # 用 stack.push_reg() 将寄存器中的值压入栈中
                lines.extend(stack.push_reg(reg, get_size(binding.type_node), comment="Receive arg from reg"))
                # 记录该参数在本地栈中的偏移（这里统一使用 lvalue 的 to_s_expression() 作为键）
                var_offsets[binding.lvalue.to_s_expression()] = stack.offset
            else:
                # 否则，参数在调用者栈中
                # 计算参数在调用者栈中的偏移：
                # offset = total_stack - binding.arg_offset + 16
                arg_offset = binding.arg_offset if hasattr(binding, "arg_offset") else 0
                total_stack = cmd.total_arg_stack if hasattr(cmd, "total_arg_stack") else 0
                offset = total_stack - arg_offset + 16
                lines.append(f"; Receiving parameter {binding.lvalue.to_s_expression()} from caller's stack offset {offset}")
                # 生成汇编：将 [rbp - offset] 处的值搬运到局部栈中
                lines.append(f"mov rax, [rbp - {offset}]")
                lines.extend(stack.push("rax", get_size(binding.type_node)))
                var_offsets[binding.lvalue.to_s_expression()] = stack.offset
        return lines


    def allocate_args(self, fn_cmd: FnCmd) -> List[str]:
        """
        根据参数个数和寄存器顺序，将参数从寄存器或栈存入 [rbp - offset] 对应的位置。
        幻灯片提到：
          - first N int args -> int registers
          - first M float args -> float registers
          - 其余都压到栈上
        """
        lines: List[str] = []
        stack_arg_offset = 0  # 记录已经在栈上存了多少参数

        for i, binding in enumerate(fn_cmd.bindings):
            ptype = binding.type_node
            # 这里采用简单计算：参数在 [rbp - (16 + i*8)] 处存放
            param_offset = 16 + i * 8  
            lines.append(f"; Place parameter {binding.lvalue.to_s_expression()} at [rbp - {param_offset}]")
            if isinstance(ptype, FloatType):
                if self.float_used < len(self.float_arg_regs):
                    reg = self.float_arg_regs[self.float_used]
                    self.float_used += 1
                    lines.append(f"movsd [rbp - {param_offset}], {reg} ; float param")
                    self.var_offsets[binding.lvalue.name] = param_offset
                else:
                    stack_arg_offset += 8
                    lines.append(f"; float param on stack (TODO: handle offsets properly)")
                    self.var_offsets[binding.lvalue.name] = param_offset
            elif isinstance(ptype, (IntType, BoolType)):
                if self.int_used < len(self.int_arg_regs):
                    reg = self.int_arg_regs[self.int_used]
                    self.int_used += 1
                    lines.append(f"mov [rbp - {param_offset}], {reg} ; int/bool param")
                    self.var_offsets[binding.lvalue.name] = param_offset
                else:
                    stack_arg_offset += 8
                    lines.append(f"; int param on stack (TODO: handle offsets properly)")
                    self.var_offsets[binding.lvalue.name] = param_offset
            else:
                # 对于数组/结构体类型（假设传递的是指针）
                if self.int_used < len(self.int_arg_regs):
                    reg = self.int_arg_regs[self.int_used]
                    self.int_used += 1
                    lines.append(f"mov [rbp - {param_offset}], {reg} ; struct/array pointer param")
                    self.var_offsets[binding.lvalue.name] = param_offset
                else:
                    stack_arg_offset += 8
                    lines.append(f"; struct/array param on stack (TODO: handle offsets properly)")
                    self.var_offsets[binding.lvalue.name] = param_offset

        return lines

    def generate_epilogue(self) -> List[str]:
        """
        函数尾部：恢复保存的寄存器并 ret
        如果之前保存了 hidden return pointer（针对 Array/Struct 返回），这里需要 pop 出来。
        """
        lines: List[str] = []
        if isinstance(self.fn_type.return_type, (ArrayType, StructType)):
            lines.extend(self.stack.pop_reg("rdi", 8, comment="Restore hidden return pointer"))
        if self.stack.peek()[0] == "expr_equal":
            lines.extend(self.stack.pop_reg("expr_equal", 8, comment="Restore expr_equal"))
        lines.extend(self.stack.pop_reg("rbp", 8, comment="Restore rbp"))
        lines.append("ret")
        return lines
