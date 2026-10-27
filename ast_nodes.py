from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ASTNode:
    line: int
    column: int


@dataclass
class ExprNode(ASTNode):
    pass


@dataclass
class IntegerLiteralNode(ExprNode):
    value: str


@dataclass
class BooleanLiteralNode(ExprNode):
    value: bool


@dataclass
class IdentifierNode(ExprNode):
    name: str


@dataclass
class UnaryExprNode(ExprNode):
    operator: str
    operand: ExprNode


@dataclass
class BinaryExprNode(ExprNode):
    operator: str
    left: ExprNode
    right: ExprNode


@dataclass
class StmtNode(ASTNode):
    pass


@dataclass
class DeclarationNode(StmtNode):
    name: str
    type_name: str
    mutable: bool
    value: ExprNode


@dataclass
class AssignmentNode(StmtNode):
    name: str
    value: ExprNode


@dataclass
class BlockNode(ASTNode):
    statements: List[StmtNode]


@dataclass
class IfNode(StmtNode):
    condition: ExprNode
    then_block: BlockNode
    else_block: Optional[BlockNode]


@dataclass
class ProgramNode(ASTNode):
    statements: List[StmtNode]
    result: ExprNode


def dump_ast(node: ASTNode) -> str:
    lines: List[str] = []

    def emit(depth: int, text: str) -> None:
        lines.append("  " * depth + text)

    def visit(current: ASTNode, depth: int) -> None:
        pos = f"@{current.line}:{current.column}"
        if isinstance(current, ProgramNode):
            emit(depth, f"Program {pos}")
            emit(depth + 1, "statements:")
            if current.statements:
                for statement in current.statements:
                    visit(statement, depth + 2)
            else:
                emit(depth + 2, "<empty>")
            emit(depth + 1, "result:")
            visit(current.result, depth + 2)
        elif isinstance(current, DeclarationNode):
            mutable = "true" if current.mutable else "false"
            emit(depth, f"Declaration {pos} name={current.name} type={current.type_name} mutable={mutable}")
            emit(depth + 1, "value:")
            visit(current.value, depth + 2)
        elif isinstance(current, AssignmentNode):
            emit(depth, f"Assignment {pos} name={current.name}")
            emit(depth + 1, "value:")
            visit(current.value, depth + 2)
        elif isinstance(current, IfNode):
            has_else = "true" if current.else_block is not None else "false"
            emit(depth, f"If {pos} has_else={has_else}")
            emit(depth + 1, "condition:")
            visit(current.condition, depth + 2)
            emit(depth + 1, "then:")
            visit(current.then_block, depth + 2)
            if current.else_block is not None:
                emit(depth + 1, "else:")
                visit(current.else_block, depth + 2)
        elif isinstance(current, BlockNode):
            emit(depth, f"Block {pos}")
            for statement in current.statements:
                visit(statement, depth + 1)
        elif isinstance(current, BinaryExprNode):
            emit(depth, f"BinaryExpr {pos} operator={current.operator}")
            emit(depth + 1, "left:")
            visit(current.left, depth + 2)
            emit(depth + 1, "right:")
            visit(current.right, depth + 2)
        elif isinstance(current, UnaryExprNode):
            emit(depth, f"UnaryExpr {pos} operator={current.operator}")
            emit(depth + 1, "operand:")
            visit(current.operand, depth + 2)
        elif isinstance(current, IntegerLiteralNode):
            emit(depth, f"IntegerLiteral {pos} value={current.value}")
        elif isinstance(current, BooleanLiteralNode):
            value = "true" if current.value else "false"
            emit(depth, f"BooleanLiteral {pos} value={value}")
        elif isinstance(current, IdentifierNode):
            emit(depth, f"Identifier {pos} name={current.name}")
        else:
            raise TypeError(f"unsupported AST node: {type(current).__name__}")

    visit(node, 0)
    return "\n".join(lines)
