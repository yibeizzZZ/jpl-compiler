from parser import FnCmd
from typechecker import FnType, IntType, FloatType, ArrayType, StructType, BoolType

class CallingConvention:
    def __init__(self, fn_type: FnType, stack, var_offsets: dict):
        self.fn_type = fn_type          # 函数类型（包含参数类型和返回类型）
        self.stack = stack              # 当前的栈管理对象
        self.var_offsets = var_offsets  # 用于记录变量在栈帧中的偏移

        # x86-64 System V 寄存器顺序示例
        self.int_arg_regs = ["rdi", "rsi", "rdx", "rcx", "r8", "r9"]
        self.float_arg_regs = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5", "xmm6", "xmm7"]

        # 记录已经用了多少整型寄存器、浮点寄存器
        self.int_used = 0
        self.float_used = 0

    @classmethod
    def from_fncmd(cls, fn_cmd: FnCmd, stack, var_offsets: dict) -> "CallingConvention":
        """
        从 FnCmd 中提取函数的参数和返回类型，构造一个 FnType，
        再根据这个 FnType 创建一个 CallingConvention 对象。
        """
        # 提取所有参数的类型
        param_types = [binding.type_node for binding in fn_cmd.bindings]
        # 构造一个 FnType 对象
        fn_type = FnType(param_types=param_types, return_type=fn_cmd.return_type, start_idx=fn_cmd.start_idx)
        return cls(fn_type, stack, var_offsets)

    def generate_prologue(self) -> list[str]:
        """
        幻灯片中提到的函数前序：对齐栈、保存 rbp、mov rbp, rsp、处理复合返回值等
        """
        lines = []
        # 对齐当前栈
        # lines.extend(self.stack.align_current())

        # 保存旧的 rbp
        lines.extend(self.stack.push_reg("rbp", 8, comment="Save old rbp"))
        lines.append("mov rbp, rsp")

        # 如果返回值是 Array/Struct，需要隐藏返回指针（通常在 rdi）
        if isinstance(self.fn_type.return_type, (ArrayType, StructType)):
            # 幻灯片中写着“ask caller for 1 extra int arg”
            # 这里我们假设已经在调用方把返回指针放到了 rdi，所以把它也压栈保存一下
            lines.extend(self.stack.push_reg("rdi", 8, comment="Save hidden return pointer"))
        return lines

    def allocate_args(self, fn_cmd: FnCmd) -> list[str]:
        """
        根据参数个数和寄存器顺序，将参数从寄存器或栈存入 [rbp - offset] 对应的位置。
        幻灯片提到：
          - first N int args -> int registers
          - first M float args -> float registers
          - 其余都压到栈上
        """
        lines = []
        stack_arg_offset = 0  # 用来记录已经在栈上存了多少参数

        for i, binding in enumerate(fn_cmd.bindings):
            ptype = binding.type_node
            param_offset = 16 + i * 8  # 你也可以根据需要改变此计算方式
            lines.append(f"; Place parameter {binding.lvalue.to_s_expression()} at [rbp - {param_offset}]")

            # 判断参数类型是否是 float/bool/int
            if isinstance(ptype, FloatType):
                if self.float_used < len(self.float_arg_regs):
                    reg = self.float_arg_regs[self.float_used]
                    self.float_used += 1
                    # 把寄存器的值保存到 [rbp - param_offset]
                    lines.append(f"movsd [rbp - {param_offset}], {reg} ; float param")
                    self.var_offsets[binding.lvalue.name] = param_offset
                else:
                    # 超过 8 个 float 参数，压栈
                    stack_arg_offset += 8
                    lines.append(f"; float param on stack (TODO handle offsets properly)")
                    # 这里需要你在调用方把后续参数压到栈，然后在函数内部使用 [rbp + ...] 或 [rbp - ...] 获取
                    # 不同编译器可能设计为 caller 或 callee pop
                    self.var_offsets[binding.lvalue.name] = param_offset

            elif isinstance(ptype, (IntType, BoolType)):
                # 整型或布尔类型
                if self.int_used < len(self.int_arg_regs):
                    reg = self.int_arg_regs[self.int_used]
                    self.int_used += 1
                    lines.append(f"mov [rbp - {param_offset}], {reg} ; int/bool param")
                    self.var_offsets[binding.lvalue.name] = param_offset
                else:
                    stack_arg_offset += 8
                    lines.append(f"; int param on stack (TODO handle offsets properly)")
                    self.var_offsets[binding.lvalue.name] = param_offset
            else:
                # 对于数组/结构体等，如果它们不是返回值，也要考虑
                # 如果是指针传递，也可当作 int_reg 处理
                if self.int_used < len(self.int_arg_regs):
                    reg = self.int_arg_regs[self.int_used]
                    self.int_used += 1
                    lines.append(f"mov [rbp - {param_offset}], {reg} ; struct/array pointer param?")
                    self.var_offsets[binding.lvalue.name] = param_offset
                else:
                    stack_arg_offset += 8
                    lines.append(f"; struct/array param on stack (TODO handle offsets properly)")
                    self.var_offsets[binding.lvalue.name] = param_offset

        return lines

    def generate_epilogue(self) -> list[str]:
        """
        函数尾部：恢复 rbp，ret
        如果之前保存了 hidden return pointer（array/struct），这里也可以 pop。
        """
        lines = []
        # 如果返回值是 array/struct，需要 pop rdi
        if isinstance(self.fn_type.return_type, (ArrayType, StructType)):
            lines.extend(self.stack.pop_reg("rdi", 8, comment="Restore hidden return pointer"))

        if self.stack.peek()[0] == "expr_equal":
            self.stack.pop_reg("expr_equal", 8, comment="Restore rbp")
        # 恢复 rbp 并 ret
        lines.extend(self.stack.pop_reg("rbp", 8, comment="Restore rbp"))
        lines.append("ret")
        return lines