
from typing import List, Tuple, Union
from dataclasses import dataclass

@dataclass
class StackArg:

    size: int
    offset: int
    arg_type: str

class CallingConvention:


    int_registers: List[str] = ['rdi', 'rsi', 'rdx', 'rcx', 'r8', 'r9']
    float_registers: List[str] = ['xmm0', 'xmm1', 'xmm2', 'xmm3', 'xmm4', 'xmm5', 'xmm6', 'xmm7', 'xmm8']

    def __init__(self):

        self.stack_args: List[StackArg] = []
        self.current_stack_offset: int = 0
        # 用于记录已分配的寄存器个数，分别针对整数和浮点参数
        self.int_reg_index: int = 0
        self.float_reg_index: int = 0

    def assign_argument(self, arg_size: int, arg_type: str) -> Union[str, Tuple[str, int]]:
        """
        为一个参数分配传递位置。参数由其大小（字节数）和类型（"int"、"float"或"array"）决定。
        优先规则：
        - 如果参数类型为 "float" 且浮点寄存器还有空闲，则返回相应的寄存器名；
        - 对于 "int" 类型参数，如果整数寄存器未用完，则返回相应的寄存器名；
        - 对于 "array" 类型参数，总是走栈（并占用16字节）；
        - 否则，将参数放入栈中，并返回一个元组 ("stack", offset)，其中 offset 为栈上起始位置。
        """
        
        if arg_type == "float":
            if self.float_reg_index < len(self.float_registers):
                reg = self.float_registers[self.float_reg_index]
                self.float_reg_index += 1
                return reg

        
        if arg_type == "int":
            if self.int_reg_index < len(self.int_registers):
                reg = self.int_registers[self.int_reg_index]
                self.int_reg_index += 1
                return reg

        
        if arg_type == "array":
            offset = self.current_stack_offset
            self.stack_args.append(StackArg(size=16, offset=offset, arg_type=arg_type))
            self.current_stack_offset += 16
            return ("stack", offset)
        
        offset = self.current_stack_offset
        self.stack_args.append(StackArg(size=arg_size, offset=offset, arg_type=arg_type))
        self.current_stack_offset += arg_size  
        return ("stack", offset)

    def compute_total_stack_size(self, return_space: int = 0) -> int:
        """
        计算所有通过栈传递的参数所需的总栈空间，以及额外预留的返回值区域（针对数组返回）。
        """
        return self.current_stack_offset + return_space

    def get_argument_assignments(self, args: List[Tuple[int, str]]) -> List[Union[str, Tuple[str, int]]]:
        """
        根据给定的参数列表（每个参数以 (size, type) 表示）返回每个参数的传递位置。
        保证参数顺序不变。
        """
        assignments = []
        for arg_size, arg_type in args:
            assignment = self.assign_argument(arg_size, arg_type)
            assignments.append(assignment)
        return assignments

    def get_return_location(self, ret_type: str) -> str:
        
        if ret_type == "int":
            return "rax"
        elif ret_type == "float":
            return "xmm0"
        elif ret_type == "array":
            return "stack"
        else:
            raise ValueError(f"Unknown return type: {ret_type}")

