from typing import List, Tuple

class Stack:
    def __init__(self):
        self.contents: List[Tuple[str, int, int]] = []
        self.offset: int = 0
        self.padding_stack: List[int] = []

    def align(self, type_size: int) -> List[str]:
        leftovers = (16 - ((self.offset + type_size) % 16)) % 16
        instructions = []
        self.padding_stack.append(leftovers)
        if leftovers > 0:
            instructions.append(f"sub rsp, {leftovers} ; align stack by {leftovers}, new offset {self.offset + leftovers}")
            self.offset += leftovers
        return instructions

    def unalign(self) -> List[str]:
        instructions = []
        if not self.padding_stack:
            return instructions
        padding = self.padding_stack.pop()
        if padding > 0:
            instructions.append(f"add rsp, {padding} ; remove padding of {padding}, new offset {self.offset - padding}")
            self.offset -= padding
        return instructions

    def align_current(self) -> List[str]:

        alignment_instructions = []
        leftover = (16 - (self.offset % 16)) % 16
        self.padding_stack.append(leftover)
        if leftover > 0:
            alignment_instructions.append(
                f"sub rsp, {leftover} ; align *current* stack by {leftover}, new offset {self.offset + leftover}"
            )
            self.offset += leftover
        return alignment_instructions
    
    def push(self, value: str, size: int, description: str = "") -> List[str]:
        alignment = 8
        padded_size = ((size + alignment - 1) // alignment) * alignment
        pad = padded_size - size
        new_offset = self.offset + padded_size
        instructions = []
        if padded_size == 8:
            instructions.append(f"push {value} ; {description} actually {size} bytes, new offset: {new_offset}")
        else:
            instructions.append(f"sub rsp, {padded_size} ; reserve {padded_size} bytes (with {pad} bytes padding), new offset: {new_offset}")
            instructions.append(f"mov [rsp + {pad}], {value} ; store {value} at offset {pad}")
        self.contents.append((description or value, size, pad))
        self.offset = new_offset
        return instructions

    def pop(self, reg: str, size: int, expected_desc: str = "") -> List[str]:
        alignment = 8
        padded_size = ((size + alignment - 1) // alignment) * alignment
        pad = padded_size - size
        new_offset = self.offset - padded_size
        instructions = []

        assert self.contents, "pop mismatch: stack is empty"
        actual_desc, actual_size, _ = self.contents.pop()
        assert (expected_desc == "" or expected_desc == actual_desc), f"pop mismatch: expected {expected_desc}, got {actual_desc}"

        if padded_size == 8:
            instructions.append(f"pop {reg} ; {actual_desc}, actually {size} bytes, new offset: {new_offset}")
        else:
            instructions.append(f"mov {reg}, [rsp + {pad}] ; load from offset {pad}, current offset: {self.offset}")
            instructions.append(f"add rsp, {padded_size} ; restore {padded_size} bytes (including {pad} bytes padding), new offset: {new_offset}")

        self.offset = new_offset
        return instructions

    def push_reg(self, reg: str, size: int, comment: str = "") -> List[str]:
        new_offset = self.offset + size
        self.contents.append((reg, size, 0))
        self.offset = new_offset
        comment_str = f" ; {comment}" if comment else ""
        return [f"push {reg}{comment_str}; new offset: {new_offset}"]

    def pop_reg(self, reg: str, size: int, comment: str = "") -> List[str]:
        new_offset = self.offset - size
        assert self.contents and self.contents[-1][0] == reg, f"pop_reg mismatch: expected {reg}"
        self.contents.pop()
        self.offset = new_offset
        comment_str = f" ; {comment}" if comment else ""
        return [f"pop {reg}{comment_str}; new offset: {new_offset}"]

    def is_aligned(self) -> bool:
        return (self.offset % 16) == 0

    def __str__(self) -> str:
        lines = [f"Stack offset: {self.offset} bytes"]
        for i, (val, size, pad) in enumerate(self.contents):
            lines.append(f"  [{i}]: value={val}, size={size}, pad={pad}")
        return "\n".join(lines)
