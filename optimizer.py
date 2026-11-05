"""Tree optimizer behind --optimize: unused variables, unused functions, inlining.

Every pass works on a checked tree and leaves a tree that the analyzer can check
again, so symbols are always rebuilt from the program as it now stands.
"""
from dataclasses import fields

from ast_nodes import *
from semantics import Analyzer, Serve, Variable

ARITHMETIC = ('+', '-', '*')
RANGES = {'i32': 1 << 31, 'i64': 1 << 63}


def children(node):
    """Yield the direct child nodes of a tree node."""
    for item in fields(node):
        value = getattr(node, item.name)
        if isinstance(value, ASTNode):
            yield value
        elif isinstance(value, list):
            yield from (child for child in value if isinstance(child, ASTNode))
    callee = getattr(node, 'callee', None)
    if isinstance(node, CallNode) and callee is not None and node.receiver is None:
        yield callee


def walk(node):
    """Yield the node and everything below it, parents first."""
    yield node
    for child in children(node):
        yield from walk(child)


def rewrite(node, replace):
    """Rebuild the tree bottom-up, letting `replace` swap each expression."""
    for item in fields(node):
        value = getattr(node, item.name)
        if isinstance(value, ASTNode):
            setattr(node, item.name, rewrite(value, replace))
        elif isinstance(value, list):
            value[:] = [rewrite(child, replace) if isinstance(child, ASTNode) else child for child in value]
    return replace(node)


def statement_lists(tree):
    """Yield every list of statements in the program."""
    for node in walk(tree):
        if isinstance(node, (ProgramNode, BlockNode, InlinedCallNode)):
            yield node.statements


def root_of(target):
    while isinstance(target, FieldAccessNode):
        target = target.base
    return target


def target_of(node):
    """The assigned place; the analyzer stores it for a plain variable too."""
    return node.target if isinstance(node.name, str) else node.name


def expression_nodes(node):
    """Walk what evaluating an expression runs: a lambda's body waits for a call."""
    yield node
    if not isinstance(node, LambdaNode):
        for child in children(node):
            yield from expression_nodes(child)


class Optimizer:
    def __init__(self, tree):
        self.tree = tree
        self.analysis = None
        self.inlined = 0

    def run(self):
        changed = True
        while changed:
            self.check()
            changed = self.remove_unused_variables()
            self.check()
            changed = self.remove_unused_functions() or changed
            self.check()
            changed = self.inline_one_call() or changed
        return self.check()

    def check(self):
        self.analysis = Analyzer().analyze(self.tree)
        return self.analysis

    # Unused variables ---------------------------------------------------

    def constants(self):
        """Values of the `keep` variables that are known at compile time."""
        known = {}
        for node in walk(self.tree):
            if isinstance(node, DeclarationNode) and not node.mutable:
                value = self.constant_value(node.value, known)
                if value is not None:
                    known[node.symbol] = value
        return known

    def constant_value(self, node, known):
        """Fold an integer expression, or None when it is unknown or would overflow."""
        if isinstance(node, IntegerLiteralNode):
            return int(node.value.lstrip('0') or '0')
        if isinstance(node, IdentifierNode):
            return known.get(node.symbol)
        if isinstance(node, BinaryExprNode) and node.operator in ARITHMETIC:
            left = self.constant_value(node.left, known)
            right = self.constant_value(node.right, known)
            if left is None or right is None:
                return None
            value = {'+': left + right, '-': left - right, '*': left * right}[node.operator]
            limit = RANGES[node.type_name]
            return value if -limit <= value < limit else None
        return None

    def has_effects(self, node, known):
        """A call, read() or arithmetic that may abort on overflow must still run."""
        for part in expression_nodes(node):
            if isinstance(part, (CallNode, ApplyNode, InlinedCallNode)):
                return True
            if isinstance(part, BinaryExprNode) and part.operator in ARITHMETIC:
                if self.constant_value(part, known) is None:
                    return True
        return False

    def read_variables(self, known):
        """Variables whose value somebody reads; `x <- x` alone does not count."""
        reads = set()

        def visit(node):
            if isinstance(node, AssignmentNode):
                target = target_of(node)
                root = root_of(target).symbol
                value_reads = {p.symbol for p in walk(node.value) if isinstance(p, IdentifierNode)}
                if root not in value_reads or self.has_effects(node.value, known):
                    reads.update(value_reads)
                else:
                    reads.update(value_reads - {root})
                return
            if isinstance(node, IdentifierNode):
                reads.add(node.symbol)
            for child in children(node):
                visit(child)

        visit(self.tree)
        return reads

    def remove_unused_variables(self):
        known = self.constants()
        reads = self.read_variables(known)
        changed = False

        def unread(symbol):
            return isinstance(symbol, Variable) and symbol.owner is None and symbol not in reads

        for statements in list(statement_lists(self.tree)):
            kept = []
            for node in statements:
                value = None
                if isinstance(node, DeclarationNode) and unread(node.symbol):
                    value = node.value
                elif isinstance(node, AssignmentNode) and unread(root_of(target_of(node)).symbol):
                    value = node.value
                elif isinstance(node, ExpressionStatementNode) and not self.has_effects(node.value, known):
                    value = node.value
                elif isinstance(node, IfNode) and self.is_empty(node) and not self.has_effects(node.condition, known):
                    changed = True
                    continue
                if value is None:
                    kept.append(node)
                    continue
                changed = True
                # An initializer has no type of its own: only its parts can stay.
                parts = value.values if isinstance(value, ObjectInitializerNode) else [value]
                kept += [ExpressionStatementNode(part.line, part.column, part) for part in parts
                         if self.has_effects(part, known)]
            statements[:] = kept
        return changed

    @staticmethod
    def is_empty(node):
        return not node.then_block.statements and not (node.else_block and node.else_block.statements)

    # Unused functions ---------------------------------------------------

    def used_serves(self, roots):
        """Every serve reachable from the given nodes, by call or by value."""
        used, pending = set(), list(roots)
        while pending:
            for node in walk(pending.pop()):
                serve = getattr(node, 'symbol', None)
                if isinstance(node, (CallNode, IdentifierNode)) and isinstance(serve, Serve) and serve not in used:
                    used.add(serve)
                    pending.append(serve.node)
        return used

    def remove_unused_functions(self):
        used = self.used_serves(self.tree.statements + [self.tree.result])
        before = len(self.tree.functions) + sum(len(card.members) for card in self.tree.cards)
        self.tree.functions[:] = [node for node in self.tree.functions if node.symbol in used]
        for card in self.tree.cards:
            card.members[:] = [node for node in card.members if node.symbol in used]
        return before != len(self.tree.functions) + sum(len(card.members) for card in self.tree.cards)

    # Inlining -----------------------------------------------------------

    def inline_one_call(self):
        calls, values = {}, set()
        for node in walk(self.tree):
            serve = getattr(node, 'symbol', None)
            if isinstance(serve, Serve):
                if isinstance(node, CallNode):
                    calls.setdefault(serve, []).append(node)
                elif isinstance(node, IdentifierNode):
                    values.add(serve)
        for function in self.tree.functions:
            serve = function.symbol
            if len(calls.get(serve, ())) == 1 and serve not in values and not self.is_recursive(serve):
                self.inline(function, calls[serve][0])
                return True
        return False

    def is_recursive(self, serve):
        return serve in self.used_serves([serve.node])

    def inline(self, function, call):
        self.inlined += 1
        self.rename_locals(function)
        statements = [DeclarationNode(p.line, p.column, p.name, p.type_name, False, argument)
                      for p, argument in zip(function.parameters, call.arguments)]
        statements += function.body.statements[:-1]
        result = function.body.statements[-1].value
        replacement = InlinedCallNode(call.line, call.column, function.name, function.result_type,
                                      statements, result)
        self.tree.functions[:] = [node for node in self.tree.functions if node is not function]
        rewrite(self.tree, lambda node: replacement if node is call else node)

    def rename_locals(self, function):
        """Give the moved body names that source code cannot spell."""
        names = {}
        for node in walk(function):
            if isinstance(node, (DeclarationNode, ParameterNode)):
                names[node.symbol] = f'{function.name}.{self.inlined}.{node.name}'
                node.name = names[node.symbol]
        for node in walk(function):
            symbol = getattr(node, 'symbol', None)
            if isinstance(node, AssignmentNode) and isinstance(node.name, str):
                node.name = names.get(node.target.symbol, node.name)
            elif isinstance(node, IdentifierNode) and symbol in names:
                node.name = names[symbol]
            elif isinstance(node, CallNode) and node.callee is not None and node.receiver is None:
                node.name = names.get(node.callee.symbol, node.name)
            elif isinstance(node, (CallNode, IdentifierNode)) and isinstance(symbol, Serve):
                # Names at the call site must not capture what the body meant.
                node.global_only = symbol.owner is None


def optimize(tree):
    """Run all passes to a fixed point and return the analysis of the result."""
    return Optimizer(tree).run()
