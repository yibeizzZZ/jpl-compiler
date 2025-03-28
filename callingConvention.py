from parser import *
from typechecker import FnType

class CallingConvention:
    def __init__(self, fn_type: FnType, stack, var_offsets: dict):
        self.fn_type = fn_type          # 函数类型（包含参数类型和返回类型）
        self.stack = stack              # 当前的栈管理对象
        self.var_offsets = var_offsets  # 用于记录变量在栈帧中的偏移
        # 预定义参数传递寄存器列表（如 x86-64 System V 调用约定）
        self.arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]

    @classmethod
    def from_fncmd(cls, fn_cmd: FnCmd, stack, var_offsets: dict) -> "CallingConvention":
        """
        从 FnCmd 中提取函数的参数和返回类型，构造一个 FnType，
        再根据这个 FnType 创建一个 CallingConvention 对象。
        """
        # 提取所有参数的类型
        param_types = [binding.type_node for binding in fn_cmd.bindings]
        # 构造一个 FnType 对象（注意：这里 start_idx 可用 fn_cmd.start_idx）
        fn_type = FnType(param_types=param_types, return_type=fn_cmd.return_type, start_idx=fn_cmd.start_idx)
        return cls(fn_type, stack, var_offsets)

    def generate_prologue(self) -> List[str]:
        # 此处省略具体实现，前面示例已有
        lines = []
        lines.extend(self.stack.align_current())
        lines.extend(self.stack.push_reg("rbp", 8, comment="Save old rbp"))
        lines.append("mov rbp, rsp")

        if isinstance(self.fn_type.return_type, ArrayType) or isinstance(self.fn_type.return_type, StructType):
        #     # 这里我们假设隐藏返回地址总是存放在 rdi
            lines.extend(self.stack.push_reg("rdi",8))
        return lines

    def allocate_args(self, cmd: FnCmd) -> List[str]:
        # 根据参数个数和寄存器顺序，将参数从寄存器存入栈上对应的位置
        lines = []
        for i, binding in enumerate(cmd.bindings):
            param_offset = 16 + i * 8  # 第一个参数放在 [rbp - 16]，第二个 [rbp - 24]，依此类推
            lines.append(f"; Place parameter {binding.lvalue.to_s_expression()} at rbp - {param_offset}")
            if i < len(self.arg_regs):
                reg = self.arg_regs[i]
                lines.append(f"mov [rbp - {param_offset}], {reg} ; save {binding.lvalue.to_s_expression()}")
                self.var_offsets[binding.lvalue.name] = param_offset
            else:
                lines.append("; Error: Too many parameters!")
        return lines

    def generate_epilogue(self) -> List[str]:
        lines = []
        lines.extend(self.stack.pop_reg("rbp", 8, comment="Restore rbp"))
        lines.append("ret")
        return lines