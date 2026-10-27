"""Positioned type checking and name resolution, independent of LLVM."""
from dataclasses import dataclass, field
from ast_nodes import *


class SemanticError(Exception):
    def __init__(self, node, message):
        self.line, self.column, self.message = node.line, node.column, message
        super().__init__(message)


def fail(node, message):
    raise SemanticError(node, message)


@dataclass(eq=False)
class Variable:
    name: str
    type_name: str
    mutable: bool
    index: int = -1
    owner: object = None


@dataclass(eq=False)
class Serve:
    node: FunctionNode
    owner: object = None
    mutating: bool = False
    dependencies: set = field(default_factory=set)


@dataclass(eq=False)
class Card:
    node: CardNode
    fields: dict = field(default_factory=dict)
    members: dict = field(default_factory=dict)


class Analyzer:
    def __init__(self):
        self.cards, self.functions = {}, {}
        self.scopes = []
        self.current = None
        self.member_calls = []

    def valid_type(self, name, node):
        if name not in ('i32', 'i64', 'flag', 'string') and name not in self.cards:
            fail(node, f"unknown type '{name}'")

    def analyze(self, tree):
        for node in tree.cards:
            if node.name in self.cards:
                fail(node, f"duplicate card '{node.name}'")
            self.cards[node.name] = Card(node)
        for card in self.cards.values():
            for index, node in enumerate(card.node.fields):
                self.valid_type(node.type_name, node)
                if node.name in card.fields:
                    fail(node, f"duplicate field '{node.name}'")
                symbol = Variable(node.name, node.type_name, node.mutable, index, card)
                card.fields[node.name] = node.symbol = symbol
            for node in card.node.members:
                self.add_serve(node, card.members, card)
        # Value structs cannot contain themselves, even indirectly.
        def check_layout(card, path):
            if card in path:
                fail(card.node, 'recursive card layout')
            for variable in card.fields.values():
                if variable.type_name in self.cards:
                    check_layout(self.cards[variable.type_name], path | {card})
        for card in self.cards.values():
            check_layout(card, set())
        for node in tree.functions:
            self.add_serve(node, self.functions)
        serves = list(self.functions.values())
        serves += [s for c in self.cards.values() for s in c.members.values()]
        for serve in serves:
            self.current = serve
            self.scopes = [{}]
            for parameter in serve.node.parameters:
                parameter.symbol = self.declare(parameter, parameter.type_name, False)
            self.block(serve.node.body, nested=False)
        self.current = None
        self.scopes = [{}]
        for statement in tree.statements:
            self.statement(statement)
        self.expression(tree.result)
        changed = True
        while changed:
            changed = False
            for serve in serves:
                if not serve.mutating and any(s.mutating for s in serve.dependencies):
                    serve.mutating = changed = True
        for node, serve, mutable in self.member_calls:
            if serve.mutating and not mutable:
                fail(node, 'mutating member call through constant object or field')
        return self

    def add_serve(self, node, table, owner=None):
        if node.name in table or owner and node.name in owner.fields:
            fail(node, f"duplicate serve '{node.name}'")
        self.valid_type(node.result_type, node)
        for parameter in node.parameters:
            self.valid_type(parameter.type_name, parameter)
        table[node.name] = node.symbol = Serve(node, owner)

    def declare(self, node, type_name, mutable):
        if node.name in self.scopes[-1]:
            fail(node, f"duplicate declaration '{node.name}'")
        variable = Variable(node.name, type_name, mutable)
        self.scopes[-1][node.name] = variable
        return variable

    def lookup(self, node):
        for scope in reversed(self.scopes):
            if node.name in scope:
                return scope[node.name]
        if self.current and self.current.owner and node.name in self.current.owner.fields:
            return self.current.owner.fields[node.name]
        fail(node, f"undeclared name '{node.name}'")

    def compatible(self, actual, expected, node):
        if actual != expected and (actual, expected) != ('i32', 'i64'):
            fail(node, f"expected {expected}, got {actual}")

    def block(self, node, nested=True):
        if nested:
            self.scopes.append({})
        for statement in node.statements:
            self.statement(statement)
        if nested:
            self.scopes.pop()

    def statement(self, node):
        if isinstance(node, DeclarationNode):
            self.valid_type(node.type_name, node)
            self.compatible(self.expression(node.value, node.type_name), node.type_name, node.value)
            node.symbol = self.declare(node, node.type_name, node.mutable)
        elif isinstance(node, AssignmentNode):
            target = IdentifierNode(node.line, node.column, node.name) if isinstance(node.name, str) else node.name
            node.target = target
            expected = self.expression(target)
            if not target.path_mutable:
                fail(target, 'assignment through constant binding or field')
            if self.current and target.self_path:
                self.current.mutating = True
            self.compatible(self.expression(node.value, expected), expected, node.value)
        elif isinstance(node, IfNode):
            self.compatible(self.expression(node.condition), 'flag', node.condition)
            self.block(node.then_block)
            if node.else_block:
                self.block(node.else_block)
        elif isinstance(node, EngraveNode):
            self.expression(node.value)
        elif isinstance(node, ReturnNode):
            self.compatible(self.expression(node.value, self.current.node.result_type),
                            self.current.node.result_type, node.value)

    def expression(self, node, expected=None):
        node.path_mutable, node.self_path = False, False
        node.constant = None
        if isinstance(node, IntegerLiteralNode):
            # Compare text first: Python's integer digit limit must not leak out.
            digits = node.value.lstrip('0') or '0'
            if len(digits) > 19 or len(digits) == 19 and digits > '9223372036854775807':
                fail(node, 'integer literal overflows i64')
            value = int(digits)
            result = 'i32' if value <= 2147483647 else 'i64'
            node.constant = value
        elif isinstance(node, BooleanLiteralNode):
            result = 'flag'
            node.constant = node.value
        elif isinstance(node, StringLiteralNode):
            result = 'string'
        elif isinstance(node, IdentifierNode):
            node.symbol = self.lookup(node)
            result = node.symbol.type_name
            node.path_mutable = node.symbol.mutable
            node.self_path = node.symbol.owner is not None
        elif isinstance(node, FieldAccessNode):
            base = self.expression(node.base)
            card = self.cards.get(base)
            if card is None or node.name not in card.fields:
                fail(node, f"unknown field '{node.name}' on {base}")
            node.symbol = card.fields[node.name]
            result = node.symbol.type_name
            node.path_mutable = node.base.path_mutable and node.symbol.mutable
            node.self_path = node.base.self_path
        elif isinstance(node, ObjectInitializerNode):
            if expected not in self.cards:
                fail(node, 'object initializer requires a card type')
            node.card = self.cards[expected]
            fields = list(node.card.fields.values())
            if len(fields) != len(node.values):
                fail(node, f'expected {len(fields)} field values, got {len(node.values)}')
            for value, variable in zip(node.values, fields):
                self.compatible(self.expression(value, variable.type_name), variable.type_name, value)
            result = expected
        elif isinstance(node, CallNode):
            if node.name == 'draw' and node.receiver is None:
                result = 'i32'
                node.type_name = result
                return result
            receiver_mutable, self_path = True, False
            if node.receiver:
                receiver_type = self.expression(node.receiver)
                card = self.cards.get(receiver_type)
                serve = card.members.get(node.name) if card else None
                receiver_mutable, self_path = node.receiver.path_mutable, node.receiver.self_path
            else:
                owner = self.current.owner if self.current else None
                serve = owner.members.get(node.name) if owner else None
                if serve:
                    self_path = True
                else:
                    serve = self.functions.get(node.name)
            if serve is None:
                fail(node, f"unknown serve '{node.name}'")
            node.symbol = serve
            if len(node.arguments) != len(serve.node.parameters):
                fail(node, f"expected {len(serve.node.parameters)} arguments, got {len(node.arguments)}")
            for argument, parameter in zip(node.arguments, serve.node.parameters):
                self.compatible(self.expression(argument, parameter.type_name), parameter.type_name, argument)
            if serve.owner:
                self.member_calls.append((node, serve, receiver_mutable))
                if self.current and self_path:
                    self.current.dependencies.add(serve)
            result = serve.node.result_type
        elif isinstance(node, UnaryExprNode):
            self.compatible(self.expression(node.operand), 'flag', node.operand)
            result = 'flag'
            if node.operand.constant is not None:
                node.constant = not node.operand.constant
        elif isinstance(node, BinaryExprNode):
            left, right = self.expression(node.left), self.expression(node.right)
            integers = left in ('i32', 'i64') and right in ('i32', 'i64')
            if node.operator in ('==', '!='):
                if not integers and (left, right) != ('flag', 'flag'):
                    fail(node, 'comparison requires integers or two flags')
                result = 'flag'
            else:
                if not integers:
                    fail(node, 'arithmetic requires integers')
                result = 'i64' if 'i64' in (left, right) else 'i32'
                if node.left.constant is not None and node.right.constant is not None:
                    a, b = node.left.constant, node.right.constant
                    value = {'+': lambda: a+b, '-': lambda: a-b, '*': lambda: a*b}[node.operator]()
                    bits = 32 if result == 'i32' else 64
                    if not -(1 << (bits-1)) <= value < 1 << (bits-1):
                        fail(node, f'arithmetic overflow in {result}')
                    node.constant = value
        else:
            raise TypeError(type(node).__name__)
        node.type_name = result
        return result
