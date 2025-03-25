from typing import List, Tuple

class Stack:
    def __init__(self):
        self.contents: List[Tuple[str, int, int]] = []
        self.offset: int = 0

    def push(self, value: str, size: int) -> List[str]:
        alignment = 8
        padded_size = ((size + alignment - 1) // alignment) * alignment
        pad = padded_size - size
        instructions = []
        if padded_size == 8:
            instructions.append(f"push {value}  ; 实际 {size} 字节")
        else:
            instructions.append(f"sub rsp, {padded_size}   ; 预留 {padded_size} 字节（含 {pad} 字节填充）")
            instructions.append(f"mov [rsp + {pad}], {value}   ; 将 {value} 存入偏移 {pad} 处")
        self.contents.append((value, size, pad))
        self.offset += padded_size
        return instructions

    def pop(self, reg: str, size: int) -> List[str]:

        alignment = 8
        padded_size = ((size + alignment - 1) // alignment) * alignment
        pad = padded_size - size
        instructions = []
        if padded_size == 8:
            instructions.append(f"pop {reg}  ; 实际 {size} 字节")
        else:
            instructions.append(f"mov {reg}, [rsp + {pad}]   ; 从偏移 {pad} 处加载数据")
            instructions.append(f"add rsp, {padded_size}   ; 恢复 {padded_size} 字节（包含 {pad} 字节填充）")
        if self.contents:
            self.contents.pop()
        self.offset -= padded_size
        return instructions

    def is_aligned(self) -> bool:
        return (self.offset % 16) == 0

    def __str__(self) -> str:
        lines = [f"Stack offset: {self.offset} bytes"]
        for i, (val, size, pad) in enumerate(self.contents):
            lines.append(f"  [{i}]: value={val}, size={size}, pad={pad}")
        return "\n".join(lines)

    def push_reg(self, reg: str, size: int, comment: str = "") -> List[str]:
        alignment = 8
        padded_size = ((size + alignment - 1) // alignment) * alignment
        pad = padded_size - size
        self.contents.append((reg, size, pad))
        self.offset += padded_size
        if comment:
            return [f"push {reg} ; {comment}"]
        else:
            return [f"push {reg}"]

    def pop_reg(self, reg: str, size: int, comment: str = "") -> List[str]:
        alignment = 8
        padded_size = ((size + alignment - 1) // alignment) * alignment
        pad = padded_size - size
        if self.contents:
            self.contents.pop()
        self.offset -= padded_size
        if comment:
            return [f"pop {reg} ; {comment}"]
        else:
            return [f"pop {reg}"]