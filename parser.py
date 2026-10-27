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
from ast_nodes import (CardNode, FieldNode, ParameterNode, FunctionNode, ReturnNode,
                       EngraveNode, StringLiteralNode, FieldAccessNode, CallNode,
                       ObjectInitializerNode)


class ParseError(Exception):
    def __init__(self, token: Token, message: str) -> None:
        super().__init__(message)
        self.line = token.line
        self.column = token.column
        self.message = message


TOKEN_NAMES = {
    TokenKind.CARD: "'card'",
    TokenKind.SERVE: "'serve'",
    TokenKind.RETROCEDE: "'retrocede'",
    TokenKind.DRAW: "'draw'",
    TokenKind.ENGRAVE: "'Engrave'",
    TokenKind.STRING: "'string'",
    TokenKind.STRING_LITERAL: 'string literal',
    TokenKind.LPAREN: "'('",
    TokenKind.RPAREN: "')'",
    TokenKind.COMMA: "','",
    TokenKind.DOT: "'.'",
    TokenKind.ARROW: "'->'",
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
for _kind in TokenKind:
    TOKEN_NAMES.setdefault(_kind, repr(_kind.name.lower()))


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
        self.skip_newlines()
        cards, functions = [], []
        while self.peek().kind is TokenKind.CARD:
            cards.append(self.parse_card_decl())
            self.skip_newlines()
        while self.peek().kind is TokenKind.SERVE:
            functions.append(self.parse_function_decl())
            self.skip_newlines()
        while self.peek().kind is not TokenKind.FINISH:
            if self.peek().kind is TokenKind.NL:
                self.eat(TokenKind.NL)
            elif self._starts_statement():
                statements.append(self.parse_statement())
            else:
                token = self.peek()
                raise ParseError(token, "expected statement or '(⊙_⊙;)' completion")
        finish_token, result = self.parse_finish()
        self.skip_newlines()
        self.eat(TokenKind.EOF)
        first = statements[0] if statements else finish_token
        return ProgramNode(first.line, first.column, statements, result, cards, functions)

    def skip_newlines(self):
        while self.peek().kind is TokenKind.NL:
            self.eat(TokenKind.NL)

    def parse_card_decl(self):
        start = self.eat(TokenKind.CARD)
        name = self.parse_identifier().name
        self.eat(TokenKind.NL)
        self.eat(TokenKind.LBRACE)
        self.eat(TokenKind.NL)
        self.skip_newlines()
        fields = [self.parse_field_decl()]
        self.skip_newlines()
        while self.peek().kind in (TokenKind.KEEP, TokenKind.CHANGE):
            fields.append(self.parse_field_decl())
            self.skip_newlines()
        members = []
        while self.peek().kind is TokenKind.SERVE:
            members.append(self.parse_function_decl())
            self.skip_newlines()
        self.eat(TokenKind.RBRACE)
        self.eat(TokenKind.NL)
        return CardNode(start.line, start.column, name, fields, members)

    def parse_field_decl(self):
        mutability, start = self.parse_mutability()
        name = self.parse_identifier().name
        self.eat(TokenKind.COLON)
        type_name = self.parse_type()
        self.eat(TokenKind.NL)
        return FieldNode(start.line, start.column, name, type_name, mutability == 'change')

    def parse_parameter(self):
        name = self.parse_identifier()
        self.eat(TokenKind.COLON)
        return ParameterNode(name.line, name.column, name.name, self.parse_type())

    def parse_parameter_list(self):
        parameters = [self.parse_parameter()]
        while self.peek().kind is TokenKind.COMMA:
            self.eat(TokenKind.COMMA)
            parameters.append(self.parse_parameter())
        return parameters

    def parse_function_decl(self):
        start = self.eat(TokenKind.SERVE)
        name = self.parse_identifier().name
        self.eat(TokenKind.LPAREN)
        parameters = [] if self.peek().kind is TokenKind.RPAREN else self.parse_parameter_list()
        self.eat(TokenKind.RPAREN)
        self.eat(TokenKind.ARROW)
        result = self.parse_type()
        self.eat(TokenKind.NL)
        return FunctionNode(start.line, start.column, name, parameters, result, self.parse_function_block())

    def parse_function_block(self):
        start = self.eat(TokenKind.LBRACE)
        self.eat(TokenKind.NL)
        self.skip_newlines()
        statements = []
        while self._starts_statement():
            statements.append(self.parse_statement())
            self.skip_newlines()
        statements.append(self.parse_retrocede_statement())
        self.eat(TokenKind.NL)
        self.skip_newlines()
        self.eat(TokenKind.RBRACE)
        self.eat(TokenKind.NL)
        return BlockNode(start.line, start.column, statements)

    def parse_retrocede_statement(self):
        start = self.eat(TokenKind.RETROCEDE)
        return ReturnNode(start.line, start.column, self.parse_expression())

    def parse_engrave_statement(self):
        start = self.eat(TokenKind.ENGRAVE)
        self.eat(TokenKind.LPAREN)
        value = self.parse_expression()
        self.eat(TokenKind.RPAREN)
        return EngraveNode(start.line, start.column, value)

    def parse_statement(self) -> StmtNode:
        kind = self.peek().kind
        if kind is TokenKind.ENGRAVE:
            node = self.parse_engrave_statement()
            self.eat(TokenKind.NL)
            return node
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
        value = self.parse_initializer()
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
        if token.kind in (TokenKind.STRING, TokenKind.IDENTIFIER):
            self.index += 1
            return token.text
        if token.kind is TokenKind.I32:
            return self.eat(TokenKind.I32).text
        if token.kind is TokenKind.I64:
            return self.eat(TokenKind.I64).text
        if token.kind is TokenKind.FLAG:
            return self.eat(TokenKind.FLAG).text
        raise ParseError(token, "expected type 'i32', 'i64', or 'flag'")

    def parse_assignment(self) -> AssignmentNode:
        name = self.parse_lvalue()
        self.eat(TokenKind.ASSIGN)
        value = self.parse_expression()
        target = name.name if isinstance(name, IdentifierNode) else name
        return AssignmentNode(name.line, name.column, target, value)

    def parse_lvalue(self):
        value = self.parse_identifier()
        while self.peek().kind is TokenKind.DOT:
            self.eat(TokenKind.DOT)
            name = self.parse_identifier()
            value = FieldAccessNode(name.line, name.column, value, name.name)
        return value

    def parse_initializer(self):
        if self.peek().kind is TokenKind.LBRACE:
            return self.parse_object_initializer()
        return self.parse_expression()

    def parse_object_initializer(self):
        start = self.eat(TokenKind.LBRACE)
        values = self.parse_argument_list()
        self.eat(TokenKind.RBRACE)
        return ObjectInitializerNode(start.line, start.column, values)

    def parse_argument_list(self):
        values = [self.parse_expression()]
        while self.peek().kind is TokenKind.COMMA:
            self.eat(TokenKind.COMMA)
            values.append(self.parse_expression())
        return values

    def parse_postfix_expression(self):
        value = self.parse_lvalue()
        if self.peek().kind is TokenKind.LPAREN:
            self.eat(TokenKind.LPAREN)
            arguments = [] if self.peek().kind is TokenKind.RPAREN else self.parse_argument_list()
            self.eat(TokenKind.RPAREN)
            receiver = value.base if isinstance(value, FieldAccessNode) else None
            value = CallNode(value.line, value.column, value.name, arguments, receiver)
        return value

    def parse_draw_call(self):
        start = self.eat(TokenKind.DRAW)
        self.eat(TokenKind.LPAREN)
        self.eat(TokenKind.RPAREN)
        return CallNode(start.line, start.column, 'draw', [])

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
        if kind is TokenKind.STRING_LITERAL:
            return self.parse_string_literal()
        if kind is TokenKind.DRAW:
            return self.parse_draw_call()
        if kind is TokenKind.INTEGER:
            return self.parse_integer_literal()
        if kind is TokenKind.TRUE or kind is TokenKind.FALSE:
            return self.parse_boolean_literal()
        if kind is TokenKind.IDENTIFIER:
            return self.parse_postfix_expression()
        raise ParseError(self.peek(), "expected integer, boolean, or identifier")

    def parse_string_literal(self):
        token = self.eat(TokenKind.STRING_LITERAL)
        return StringLiteralNode(token.line, token.column, token.text)

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
            TokenKind.ENGRAVE,
        )
