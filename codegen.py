"""LLVM construction: all instructions and constants use llvmlite.ir."""
from llvmlite import ir
from ast_nodes import *


class Generator:
    def __init__(self, analysis):
        self.analysis = analysis
        self.module = ir.Module(name='FaceCard', context=ir.Context())
        self.i32, self.i64, self.i8 = ir.IntType(32), ir.IntType(64), ir.IntType(8)
        self.types = {'i32': self.i32, 'i64': self.i64, 'flag': ir.IntType(1),
                      'string': self.i8.as_pointer()}
        for name in analysis.cards:
            self.types[name] = self.module.context.get_identified_type('fc.card.' + name)
        for name, card in analysis.cards.items():
            self.types[name].set_body(*(self.types[f.type_name] for f in card.fields.values()))
        ctype = ir.FunctionType(self.i32, [self.i8.as_pointer()], var_arg=True)
        self.printf = ir.Function(self.module, ctype, 'printf')
        self.scanf = ir.Function(self.module, ctype, 'scanf')
        self.abort = ir.Function(self.module, ir.FunctionType(ir.VoidType(), []), 'abort')
        self.strings, self.functions, self.slots = {}, {}, {}
        self.builder = None
        self.self_pointer = None

    def string(self, value):
        if value not in self.strings:
            data = value.encode('utf-8') + b'\0'
            array_type = ir.ArrayType(self.i8, len(data))
            glob = ir.GlobalVariable(self.module, array_type, '.str.' + str(len(self.strings)))
            glob.linkage = 'internal'
            glob.global_constant = True
            glob.initializer = ir.Constant(array_type, bytearray(data))
            self.strings[value] = glob
        return self.strings[value].gep([ir.Constant(self.i32, 0), ir.Constant(self.i32, 0)])

    def cast(self, value, target):
        target_type = self.types[target]
        if value.type != target_type:
            return self.builder.sext(value, target_type)
        return value

    def generate(self, tree):
        serves = list(self.analysis.functions.values())
        serves += [s for c in self.analysis.cards.values() for s in c.members.values()]
        for serve in serves:
            arguments = [self.types[p.type_name] for p in serve.node.parameters]
            if serve.owner:
                arguments.insert(0, self.types[serve.owner.node.name].as_pointer())
            name = ('fc.member.' + serve.owner.node.name + '.' if serve.owner else 'fc.serve.') + serve.node.name
            self.functions[serve] = ir.Function(self.module,
                ir.FunctionType(self.types[serve.node.result_type], arguments), name)
        for serve in serves:
            function = self.functions[serve]
            self.builder = ir.IRBuilder(function.append_basic_block('entry'))
            self.slots = {}
            self.self_pointer = function.args[0] if serve.owner else None
            arguments = function.args[1:] if serve.owner else function.args
            for parameter, value in zip(serve.node.parameters, arguments):
                self.bind(parameter.symbol, value)
            self.block(serve.node.body)
        main = ir.Function(self.module, ir.FunctionType(self.i32, []), 'main')
        self.builder = ir.IRBuilder(main.append_basic_block('entry'))
        self.self_pointer, self.slots = None, {}
        for statement in tree.statements:
            self.statement(statement)
        self.expression(tree.result)
        self.builder.ret(ir.Constant(self.i32, 0))
        return str(self.module)

    def bind(self, symbol, value):
        slot = self.builder.alloca(self.types[symbol.type_name], name=symbol.name)
        self.builder.store(self.cast(value, symbol.type_name), slot)
        self.slots[symbol] = slot
        return slot

    def gep(self, pointer, symbol):
        return self.builder.gep(pointer, [ir.Constant(self.i32, 0), ir.Constant(self.i32, symbol.index)])

    def address(self, node):
        if isinstance(node, IdentifierNode):
            if node.symbol.owner:
                return self.gep(self.self_pointer, node.symbol)
            return self.slots[node.symbol]
        if isinstance(node, FieldAccessNode):
            return self.gep(self.address(node.base), node.symbol)
        # Card values returned by serves are materialized for field operations.
        value = self.expression(node)
        slot = self.builder.alloca(value.type)
        self.builder.store(value, slot)
        return slot

    def guard(self, valid):
        function = self.builder.function
        good, bad = function.append_basic_block('checked'), function.append_basic_block('runtime.error')
        self.builder.cbranch(valid, good, bad)
        self.builder.position_at_end(bad)
        self.builder.call(self.abort, [])
        self.builder.unreachable()
        self.builder.position_at_end(good)

    def expression(self, node):
        b = self.builder
        if isinstance(node, IntegerLiteralNode):
            return ir.Constant(self.types[node.type_name], int(node.value.lstrip('0') or '0'))
        if isinstance(node, BooleanLiteralNode):
            return ir.Constant(self.types['flag'], int(node.value))
        if isinstance(node, StringLiteralNode):
            return self.string(node.value)
        if isinstance(node, (IdentifierNode, FieldAccessNode)):
            return b.load(self.address(node))
        if isinstance(node, ObjectInitializerNode):
            slot = b.alloca(self.types[node.type_name])
            for field, value in zip(node.card.fields.values(), node.values):
                b.store(self.cast(self.expression(value), field.type_name), self.gep(slot, field))
            return b.load(slot)
        if isinstance(node, CallNode):
            if node.name == 'draw' and node.receiver is None:
                slot = b.alloca(self.i64)
                b.store(ir.Constant(self.i64, 0), slot)
                count = b.call(self.scanf, [self.string('%lld'), slot])
                self.guard(b.icmp_signed('==', count, ir.Constant(self.i32, 1)))
                value = b.load(slot)
                lower = b.icmp_signed('>=', value, ir.Constant(self.i64, -2147483648))
                upper = b.icmp_signed('<=', value, ir.Constant(self.i64, 2147483647))
                self.guard(b.and_(lower, upper))
                return b.trunc(value, self.i32)
            serve = node.symbol
            arguments = []
            if serve.owner:
                arguments.append(self.address(node.receiver) if node.receiver else self.self_pointer)
            for argument, parameter in zip(node.arguments, serve.node.parameters):
                arguments.append(self.cast(self.expression(argument), parameter.type_name))
            return b.call(self.functions[serve], arguments)
        if isinstance(node, UnaryExprNode):
            return b.not_(self.expression(node.operand))
        if isinstance(node, BinaryExprNode):
            left, right = self.expression(node.left), self.expression(node.right)
            common = 'i64' if 'i64' in (node.left.type_name, node.right.type_name) else node.left.type_name
            left, right = self.cast(left, common), self.cast(right, common)
            if node.operator in ('==', '!='):
                return b.icmp_signed(node.operator, left, right)
            checked = {'+': b.sadd_with_overflow, '-': b.ssub_with_overflow,
                       '*': b.smul_with_overflow}[node.operator](left, right)
            result = b.extract_value(checked, 0)
            self.guard(b.not_(b.extract_value(checked, 1)))
            return result
        raise TypeError(type(node).__name__)

    def block(self, node):
        for statement in node.statements:
            self.statement(statement)

    def statement(self, node):
        b = self.builder
        if isinstance(node, DeclarationNode):
            self.bind(node.symbol, self.expression(node.value))
        elif isinstance(node, AssignmentNode):
            b.store(self.cast(self.expression(node.value), node.target.type_name), self.address(node.target))
        elif isinstance(node, ReturnNode):
            b.ret(self.cast(self.expression(node.value), self.analysis_type_result()))
        elif isinstance(node, EngraveNode):
            value = self.expression(node.value)
            self.print_value(value, node.value.type_name)
            b.call(self.printf, [self.string('\n')])
        elif isinstance(node, IfNode):
            condition = self.expression(node.condition)
            function = b.function
            yes, no, end = [function.append_basic_block(n) for n in ('when', 'otherwise', 'continue')]
            b.cbranch(condition, yes, no)
            b.position_at_end(yes)
            self.block(node.then_block)
            b.branch(end)
            b.position_at_end(no)
            if node.else_block:
                self.block(node.else_block)
            b.branch(end)
            b.position_at_end(end)

    def analysis_type_result(self):
        for serve, function in self.functions.items():
            if function is self.builder.function:
                return serve.node.result_type
        raise RuntimeError('return outside serve')

    def print_value(self, value, type_name):
        b = self.builder
        if type_name in self.analysis.cards:
            card = self.analysis.cards[type_name]
            slot = b.alloca(value.type)
            b.store(value, slot)
            b.call(self.printf, [self.string('%s'), self.string(type_name + '{')])
            for index, field in enumerate(card.fields.values()):
                text = (', ' if index else '') + field.name + '='
                b.call(self.printf, [self.string('%s'), self.string(text)])
                self.print_value(b.load(self.gep(slot, field)), field.type_name)
            b.call(self.printf, [self.string('}')])
        elif type_name == 'flag':
            text = b.select(value, self.string('true'), self.string('false'))
            b.call(self.printf, [self.string('%s'), text])
        else:
            fmt = {'i32': '%d', 'i64': '%lld', 'string': '%s'}[type_name]
            b.call(self.printf, [self.string(fmt), value])
