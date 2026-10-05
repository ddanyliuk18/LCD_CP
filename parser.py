from typing import List, Optional, Tuple

from ast_nodes import (
    AssignmentNode,
    BinaryExprNode,
    BlockNode,
    BooleanLiteralNode,
    DeclarationNode,
    ExprNode,
    IdentifierNode,
    IfNode,
    IntegerLiteralNode,
    ProgramNode,
    StmtNode,
    UnaryExprNode,
)
from lexer import Token, TokenKind


class ParseError(Exception):
    def __init__(self, token: Token, message: str) -> None:
        super().__init__(message)
        self.line = token.line
        self.column = token.column
        self.message = message


TOKEN_NAMES = {
    TokenKind.KEEP: "'keep'",
    TokenKind.CHANGE: "'change'",
    TokenKind.I32: "'i32'",
    TokenKind.I64: "'i64'",
    TokenKind.FLAG: "'flag'",
    TokenKind.WHEN: "'when'",
    TokenKind.OTHERWISE: "'otherwise'",
    TokenKind.IDENTIFIER: "identifier",
    TokenKind.INTEGER: "integer literal",
    TokenKind.TRUE: "true literal",
    TokenKind.FALSE: "false literal",
    TokenKind.NOT: "'ಠ_ಠ'",
    TokenKind.FINISH: "'(⊙_⊙;)'",
    TokenKind.COLON: "':'",
    TokenKind.DECLARE_EQUAL: "'='",
    TokenKind.EQUAL: "'=='",
    TokenKind.NOT_EQUAL: "'!='",
    TokenKind.ASSIGN: "'<-'",
    TokenKind.PLUS: "'+'",
    TokenKind.MINUS: "'-'",
    TokenKind.STAR: "'*'",
    TokenKind.LBRACE: "'{'",
    TokenKind.RBRACE: "'}'",
    TokenKind.NL: "newline",
    TokenKind.EOF: "end of input",
}


class Parser:
    def __init__(self, tokens: List[Token]) -> None:
        self.tokens = tokens
        self.index = 0

    def peek(self, offset: int = 0) -> Token:
        target = self.index + offset
        if target >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[target]

    def eat(self, kind: TokenKind) -> Token:
        token = self.peek()
        if token.kind is not kind:
            expected = TOKEN_NAMES[kind]
            actual = TOKEN_NAMES[token.kind]
            raise ParseError(token, f"expected {expected}, got {actual}")
        self.index += 1
        return token

    def parse_program(self) -> ProgramNode:
        statements: List[StmtNode] = []
        while self.peek().kind is not TokenKind.FINISH:
            if self.peek().kind is TokenKind.NL:
                self.eat(TokenKind.NL)
            elif self._starts_statement():
                statements.append(self.parse_statement())
            else:
                token = self.peek()
                raise ParseError(token, "expected statement or '(⊙_⊙;)' completion")
        finish_token, result = self.parse_finish()
        self.eat(TokenKind.EOF)
        first = statements[0] if statements else finish_token
        return ProgramNode(first.line, first.column, statements, result)

    def parse_statement(self) -> StmtNode:
        kind = self.peek().kind
        if kind is TokenKind.KEEP or kind is TokenKind.CHANGE:
            node = self.parse_declaration()
            self.eat(TokenKind.NL)
            return node
        if kind is TokenKind.IDENTIFIER:
            node = self.parse_assignment()
            self.eat(TokenKind.NL)
            return node
        if kind is TokenKind.WHEN:
            return self.parse_if_statement()
        raise ParseError(self.peek(), "expected statement")

    def parse_declaration(self) -> DeclarationNode:
        mutability, start = self.parse_mutability()
        name = self.parse_identifier()
        self.eat(TokenKind.COLON)
        type_name = self.parse_type()
        self.eat(TokenKind.DECLARE_EQUAL)
        value = self.parse_expression()
        return DeclarationNode(
            start.line, start.column, name.name, type_name, mutability == "change", value
        )

    def parse_mutability(self) -> Tuple[str, Token]:
        token = self.peek()
        if token.kind is TokenKind.KEEP:
            self.eat(TokenKind.KEEP)
            return "keep", token
        if token.kind is TokenKind.CHANGE:
            self.eat(TokenKind.CHANGE)
            return "change", token
        raise ParseError(token, "expected 'keep' or 'change'")

    def parse_type(self) -> str:
        token = self.peek()
        if token.kind is TokenKind.I32:
            return self.eat(TokenKind.I32).text
        if token.kind is TokenKind.I64:
            return self.eat(TokenKind.I64).text
        if token.kind is TokenKind.FLAG:
            return self.eat(TokenKind.FLAG).text
        raise ParseError(token, "expected type 'i32', 'i64', or 'flag'")

    def parse_assignment(self) -> AssignmentNode:
        name = self.parse_identifier()
        self.eat(TokenKind.ASSIGN)
        value = self.parse_expression()
        return AssignmentNode(name.line, name.column, name.name, value)

    def parse_if_statement(self) -> IfNode:
        start = self.eat(TokenKind.WHEN)
        condition = self.parse_expression()
        self.eat(TokenKind.NL)
        then_block = self.parse_block()
        else_block: Optional[BlockNode] = None
        if self.peek().kind is TokenKind.OTHERWISE:
            self.eat(TokenKind.OTHERWISE)
            self.eat(TokenKind.NL)
            else_block = self.parse_block()
        return IfNode(start.line, start.column, condition, then_block, else_block)

    def parse_block(self) -> BlockNode:
        start = self.eat(TokenKind.LBRACE)
        self.eat(TokenKind.NL)
        while self.peek().kind is TokenKind.NL:
            self.eat(TokenKind.NL)
        if not self._starts_statement():
            raise ParseError(self.peek(), "block must contain at least one statement")
        statements = [self.parse_statement()]
        while True:
            while self.peek().kind is TokenKind.NL:
                self.eat(TokenKind.NL)
            if not self._starts_statement():
                break
            statements.append(self.parse_statement())
        self.eat(TokenKind.RBRACE)
        self.eat(TokenKind.NL)
        return BlockNode(start.line, start.column, statements)

    def parse_finish(self) -> Tuple[Token, ExprNode]:
        token = self.eat(TokenKind.FINISH)
        result = self.parse_expression()
        if self.peek().kind is TokenKind.NL:
            self.eat(TokenKind.NL)
        return token, result

    def parse_expression(self) -> ExprNode:
        return self.parse_comparison()

    def parse_comparison(self) -> ExprNode:
        left = self.parse_additive()
        if self.peek().kind in (TokenKind.EQUAL, TokenKind.NOT_EQUAL):
            operator = self.peek()
            self.index += 1
            right = self.parse_additive()
            return BinaryExprNode(operator.line, operator.column, operator.text, left, right)
        return left

    def parse_additive(self) -> ExprNode:
        left = self.parse_multiplicative()
        while self.peek().kind in (TokenKind.PLUS, TokenKind.MINUS):
            operator = self.peek()
            self.index += 1
            right = self.parse_multiplicative()
            left = BinaryExprNode(operator.line, operator.column, operator.text, left, right)
        return left

    def parse_multiplicative(self) -> ExprNode:
        left = self.parse_unary()
        while self.peek().kind is TokenKind.STAR:
            operator = self.eat(TokenKind.STAR)
            right = self.parse_unary()
            left = BinaryExprNode(operator.line, operator.column, operator.text, left, right)
        return left

    def parse_unary(self) -> ExprNode:
        if self.peek().kind is TokenKind.NOT:
            operator = self.eat(TokenKind.NOT)
            operand = self.parse_unary()
            return UnaryExprNode(operator.line, operator.column, operator.text, operand)
        return self.parse_primary()

    def parse_primary(self) -> ExprNode:
        kind = self.peek().kind
        if kind is TokenKind.INTEGER:
            return self.parse_integer_literal()
        if kind is TokenKind.TRUE or kind is TokenKind.FALSE:
            return self.parse_boolean_literal()
        if kind is TokenKind.IDENTIFIER:
            return self.parse_identifier()
        raise ParseError(self.peek(), "expected integer, boolean, or identifier")

    def parse_boolean_literal(self) -> BooleanLiteralNode:
        token = self.peek()
        if token.kind is TokenKind.TRUE:
            self.eat(TokenKind.TRUE)
            return BooleanLiteralNode(token.line, token.column, True)
        if token.kind is TokenKind.FALSE:
            self.eat(TokenKind.FALSE)
            return BooleanLiteralNode(token.line, token.column, False)
        raise ParseError(token, "expected boolean literal")

    def parse_integer_literal(self) -> IntegerLiteralNode:
        token = self.eat(TokenKind.INTEGER)
        return IntegerLiteralNode(token.line, token.column, token.text)

    def parse_identifier(self) -> IdentifierNode:
        token = self.eat(TokenKind.IDENTIFIER)
        return IdentifierNode(token.line, token.column, token.text)

    def _starts_statement(self) -> bool:
        return self.peek().kind in (
            TokenKind.KEEP,
            TokenKind.CHANGE,
            TokenKind.IDENTIFIER,
            TokenKind.WHEN,
        )
