"""Run the small subset of IEC 61131-3 Structured Text that the templates are written in.

The templates have never driven a real drive. The next best check is to run their own
text, not a Python copy of it, against a simulated one. This is not a compiler: it
parses only the declarations and statements the templates use, and raises StError on
anything else, so an edit that leaves the subset fails the tests instead of being
misread.

The subset: TYPE enums and STRUCTs; FUNCTION_BLOCK with VAR_INPUT, VAR_OUTPUT,
VAR_IN_OUT, VAR and VAR CONSTANT; assignment, IF, CASE with label lists and ELSE, the
empty statement, and calls of TON and R_TRIG; expressions with NOT, unary minus,
* / MOD + -, comparisons, AND, XOR, OR and ABS. As in IEC 61131-3, the logical
operators take BOOL and the bit operators take integers, never a mix; an enum compares
only with its own type; an integer wraps to its declared width when it is stored. TIME
is whole milliseconds. Pragmas other than {attribute ...} are refused, since the code
they guard may not be meant to run.

What it does not check, so that a compiler still has to: identifiers are case-sensitive
here (ST is not); integers of different types mix freely, so a narrowing or mixed-sign
assignment passes; intermediate results have no width limit, only stored values wrap.
"""
import re


class StError(Exception):
    """Text outside the subset, or an operation the IEC types do not allow."""


# --- Values -------------------------------------------------------------------------

class Time:
    __slots__ = ('ms',)

    def __init__(self, ms):
        self.ms = ms

    def __eq__(self, other):
        return isinstance(other, Time) and other.ms == self.ms

    def __repr__(self):
        return f'T#{self.ms}MS'


class EnumValue:
    __slots__ = ('type', 'name', 'value')

    def __init__(self, type_, name, value):
        self.type, self.name, self.value = type_, name, value

    def __repr__(self):
        return f'{self.type}.{self.name}'


class Struct:
    """A STRUCT instance. Item assignment checks the member's type, as a store does."""

    def __init__(self, program, type_name):
        self._program = program
        self._type = type_name
        self._members = program.structs[type_name]
        self._values = {name: program.initial(t, init)
                        for name, (t, init) in self._members.items()}

    def __getitem__(self, name):
        if name not in self._values:
            raise StError(f'{self._type} has no member {name}')
        return self._values[name]

    def __setitem__(self, name, value):
        if name not in self._members:
            raise StError(f'{self._type} has no member {name}')
        self._values[name] = self._program.coerce(self._members[name][0], value,
                                                  f'{self._type}.{name}')


class Ton:
    """IEC TON. ET counts from the call on which IN rose; Q once ET reaches PT."""
    inputs = {'IN': 'BOOL', 'PT': 'TIME'}

    def __init__(self):
        self.IN, self.PT, self.Q, self.ET = False, Time(0), False, Time(0)
        self._start = None

    def run(self, now):
        if not self.IN:
            self._start = None
            self.Q, self.ET = False, Time(0)
            return
        if self._start is None:
            self._start = now
        elapsed = min(now - self._start, self.PT.ms)
        self.ET, self.Q = Time(elapsed), elapsed >= self.PT.ms


class RTrig:
    inputs = {'CLK': 'BOOL'}

    def __init__(self):
        self.CLK, self.Q, self._m = False, False, False

    def run(self, now):
        self.Q = self.CLK and not self._m
        self._m = self.CLK


STANDARD_FBS = {'TON': Ton, 'R_TRIG': RTrig}

INTEGERS = {
    'SINT': (8, True), 'INT': (16, True), 'DINT': (32, True), 'LINT': (64, True),
    'USINT': (8, False), 'UINT': (16, False), 'UDINT': (32, False), 'ULINT': (64, False),
    'BYTE': (8, False), 'WORD': (16, False), 'DWORD': (32, False), 'LWORD': (64, False),
}


def wrap(value, type_name):
    bits, signed = INTEGERS[type_name]
    value &= (1 << bits) - 1
    if signed and value >= 1 << (bits - 1):
        value -= 1 << bits
    return value


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_time(text):
    body = text.split('#', 1)[1].replace('_', '').upper()
    parts = re.findall(r'(\d+)(MS|D|H|M|S)', body)
    if not parts or ''.join(n + u for n, u in parts) != body:
        raise StError(f'TIME literal outside the subset: {text}')
    scale = {'MS': 1, 'S': 1000, 'M': 60000, 'H': 3600000, 'D': 86400000}
    return Time(sum(int(n) * scale[u] for n, u in parts))


# --- Tokens -------------------------------------------------------------------------

TOKEN = re.compile(r'''
      (?P<space>\s+)
    | (?P<comment>//[^\n]*|\(\*.*?\*\))
    | (?P<pragma>\{[^}]*\})
    | (?P<time>(?:T|TIME)\#[0-9A-Z_]+)
    | (?P<number>16\#[0-9A-F_]+|8\#[0-7_]+|2\#[01_]+|[0-9][0-9_]*)
    | (?P<ident>[A-Z_][A-Z0-9_]*)
    | (?P<op>:=|<>|<=|>=|[-+*/=<>(),;:.])
''', re.X | re.S | re.I)

KEYWORDS = {
    'TYPE', 'END_TYPE', 'STRUCT', 'END_STRUCT', 'FUNCTION_BLOCK', 'END_FUNCTION_BLOCK',
    'VAR_INPUT', 'VAR_OUTPUT', 'VAR_IN_OUT', 'VAR', 'CONSTANT', 'END_VAR',
    'IF', 'THEN', 'ELSIF', 'ELSE', 'END_IF', 'CASE', 'OF', 'END_CASE',
    'AND', 'OR', 'XOR', 'NOT', 'MOD', 'TRUE', 'FALSE',
}


def tokenize(text):
    tokens, pos = [], 0
    while pos < len(text):
        m = TOKEN.match(text, pos)
        if not m:
            line = text.count('\n', 0, pos) + 1
            raise StError(f'line {line}: cannot read {text[pos:pos + 20]!r}')
        kind, value = m.lastgroup, m.group()
        pos = m.end()
        if kind == 'pragma' and not value[1:].lstrip().startswith('attribute'):
            line = text.count('\n', 0, m.start()) + 1
            raise StError(f'line {line}: pragma outside the subset: {value}')
        if kind in ('space', 'comment', 'pragma'):
            continue
        if kind == 'ident' and value.upper() in KEYWORDS:
            kind, value = 'kw', value.upper()
        elif kind == 'number':
            digits = value.replace('_', '')
            base = 10
            if '#' in digits:
                base_text, digits = digits.split('#')
                base = int(base_text)
            value = int(digits, base)
        elif kind == 'time':
            value = parse_time(value)
        tokens.append((kind, value, text.count('\n', 0, m.start()) + 1))
    tokens.append(('end', None, text.count('\n') + 1))
    return tokens


# --- Parser -------------------------------------------------------------------------

# Binding strength of the binary operators, IEC 61131-3 order: OR binds weakest.
BINARY = {'OR': 1, 'XOR': 2, 'AND': 3, '=': 4, '<>': 4, '<': 5, '>': 5, '<=': 5, '>=': 5,
          '+': 6, '-': 6, '*': 7, '/': 7, 'MOD': 7}
STOP = {'ELSIF', 'ELSE', 'END_IF', 'END_CASE', 'END_FUNCTION_BLOCK'}


class Parser:

    def __init__(self, text):
        self.tokens = tokenize(text)
        self.i = 0

    def peek(self, offset=0):
        return self.tokens[min(self.i + offset, len(self.tokens) - 1)]

    def at(self, value, offset=0):
        kind, v, _ = self.peek(offset)
        return kind in ('kw', 'op') and v == value

    def take(self, value=None, kind=None):
        tok = self.peek()
        if (value is not None and not self.at(value)) or (kind and tok[0] != kind):
            raise StError(f'line {tok[2]}: expected {value or kind}, found {tok[1]!r}')
        self.i += 1
        return tok[1]

    def skip_semicolon(self):
        if self.at(';'):
            self.i += 1

    # declarations

    def program(self):
        enums, structs, fbs = {}, {}, {}
        while self.peek()[0] != 'end':
            if self.at('TYPE'):
                self.take('TYPE')
                name = self.take(kind='ident')
                self.take(':')
                if self.at('('):
                    enums[name] = self.enum()
                elif self.at('STRUCT'):
                    structs[name] = self.struct()
                else:
                    raise StError(f'TYPE {name}: only enums and STRUCTs are in the subset')
                self.take('END_TYPE')
            elif self.at('FUNCTION_BLOCK'):
                fb = self.function_block()
                fbs[fb['name']] = fb
            else:
                tok = self.peek()
                raise StError(f'line {tok[2]}: expected TYPE or FUNCTION_BLOCK, '
                              f'found {tok[1]!r}')
        return enums, structs, fbs

    def enum(self):
        self.take('(')
        values, nxt = {}, 0
        while True:
            name = self.take(kind='ident')
            if self.at(':='):
                self.take(':=')
                nxt = self.take(kind='number')
            values[name] = nxt
            nxt += 1
            if self.at(')'):
                break
            self.take(',')
        self.take(')')
        if self.peek()[0] == 'ident':
            base = self.take(kind='ident')
            if base not in INTEGERS:
                raise StError(f'enum base type {base} is not an integer type')
        self.take(';')
        return values

    def struct(self):
        self.take('STRUCT')
        members = {}
        while not self.at('END_STRUCT'):
            for name, type_name, init in self.declaration():
                if name in members:
                    raise StError(f'member {name} declared twice')
                members[name] = (type_name, init)
        self.take('END_STRUCT')
        self.skip_semicolon()
        return members

    def declaration(self):
        names = [self.take(kind='ident')]
        while self.at(','):
            self.take(',')
            names.append(self.take(kind='ident'))
        self.take(':')
        type_name = self.take(kind='ident')
        init = None
        if self.at(':='):
            self.take(':=')
            init = self.expression()
        self.take(';')
        return [(n, type_name, init) for n in names]

    def function_block(self):
        self.take('FUNCTION_BLOCK')
        fb = {'name': self.take(kind='ident'), 'vars': {}}
        sections = {'VAR_INPUT': 'input', 'VAR_OUTPUT': 'output', 'VAR_IN_OUT': 'in_out',
                    'VAR': 'local'}
        while self.peek()[0] == 'kw' and self.peek()[1] in sections:
            section = sections[self.take()]
            if self.at('CONSTANT'):
                self.take('CONSTANT')
                section = 'constant'
            while not self.at('END_VAR'):
                for name, type_name, init in self.declaration():
                    if name in fb['vars']:
                        raise StError(f'{fb["name"]}.{name} declared twice')
                    fb['vars'][name] = (section, type_name, init)
            self.take('END_VAR')
        fb['body'] = self.statements()
        self.take('END_FUNCTION_BLOCK')
        return fb

    # statements

    def is_case_label(self):
        """A statement inside a CASE that starts with a constant followed by ',' or ':'
        begins the next label. ':=' is a token of its own, so ':' alone is a label."""
        if self.peek()[0] == 'number':
            return True
        offset = 0
        while self.peek(offset)[0] == 'ident':
            if not self.at('.', offset + 1):
                return self.at(':', offset + 1) or self.at(',', offset + 1)
            offset += 2
        return False

    def statements(self, in_case=False):
        body = []
        while True:
            kind, value, line = self.peek()
            if kind == 'end' or (kind == 'kw' and value in STOP):
                return body
            if in_case and self.is_case_label():
                return body
            body.append(self.statement())

    def statement(self):
        kind, value, line = self.peek()
        if self.at(';'):
            self.take(';')
            return ('nop',)
        if self.at('IF'):
            return self.if_statement()
        if self.at('CASE'):
            return self.case_statement()
        if kind != 'ident':
            raise StError(f'line {line}: statement outside the subset at {value!r}')
        path = self.path()
        if self.at('('):
            if len(path) != 1:
                raise StError(f'line {line}: only plain FB instances can be called')
            self.take('(')
            args = []
            while not self.at(')'):
                param = self.take(kind='ident')
                self.take(':=')
                args.append((param, self.expression()))
                if not self.at(')'):
                    self.take(',')
            self.take(')')
            self.take(';')
            return ('call', path[0], args, line)
        self.take(':=')
        expr = self.expression()
        self.take(';')
        return ('assign', path, expr, line)

    def if_statement(self):
        branches = []
        self.take('IF')
        cond = self.expression()
        self.take('THEN')
        branches.append((cond, self.statements()))
        while self.at('ELSIF'):
            self.take('ELSIF')
            cond = self.expression()
            self.take('THEN')
            branches.append((cond, self.statements()))
        other = []
        if self.at('ELSE'):
            self.take('ELSE')
            other = self.statements()
        self.take('END_IF')
        self.skip_semicolon()
        return ('if', branches, other)

    def case_statement(self):
        self.take('CASE')
        selector = self.expression()
        self.take('OF')
        arms, other = [], []
        while not self.at('END_CASE'):
            if self.at('ELSE'):
                self.take('ELSE')
                other = self.statements()
                continue
            labels = [self.expression()]
            while self.at(','):
                self.take(',')
                labels.append(self.expression())
            self.take(':')
            arms.append((labels, self.statements(in_case=True)))
        self.take('END_CASE')
        self.skip_semicolon()
        return ('case', selector, arms, other)

    # expressions

    def path(self):
        parts = [self.take(kind='ident')]
        while self.at('.'):
            self.take('.')
            parts.append(self.take(kind='ident'))
        return parts

    def expression(self, strength=1):
        left = self.unary()
        while True:
            kind, value, _ = self.peek()
            op = value if kind in ('kw', 'op') else None
            if op not in BINARY or BINARY[op] < strength:
                return left
            self.i += 1
            left = ('binary', op, left, self.expression(BINARY[op] + 1))

    def unary(self):
        if self.at('NOT'):
            self.take('NOT')
            return ('not', self.unary())
        if self.at('-'):
            self.take('-')
            return ('negate', self.unary())
        return self.primary()

    def primary(self):
        kind, value, line = self.peek()
        if kind in ('number', 'time'):
            self.i += 1
            return ('const', value)
        if self.at('TRUE') or self.at('FALSE'):
            self.i += 1
            return ('const', value == 'TRUE')
        if self.at('('):
            self.take('(')
            inner = self.expression()
            self.take(')')
            return inner
        if kind == 'ident':
            path = self.path()
            if self.at('('):
                if path != ['ABS']:
                    raise StError(f'line {line}: function {".".join(path)} is outside '
                                  f'the subset')
                self.take('(')
                arg = self.expression()
                self.take(')')
                return ('abs', arg)
            return ('name', path, line)
        raise StError(f'line {line}: expression outside the subset at {value!r}')


# --- Program and instances ----------------------------------------------------------

class Program:
    """The types and function blocks of one source text."""

    def __init__(self, text):
        self.enums, self.structs, self.fbs = Parser(text).program()

    def is_type(self, name):
        return (name in ('BOOL', 'TIME') or name in INTEGERS or name in self.enums
                or name in self.structs or name in STANDARD_FBS)

    def initial(self, type_name, init_expr):
        if init_expr is not None:
            return self.coerce(type_name, Evaluator(self, {}).eval(init_expr),
                               'an initial value')
        if type_name == 'BOOL':
            return False
        if type_name == 'TIME':
            return Time(0)
        if type_name in INTEGERS:
            return 0
        if type_name in self.enums:
            first = next(iter(self.enums[type_name].items()))
            return EnumValue(type_name, *first)
        if type_name in self.structs:
            return Struct(self, type_name)
        if type_name in STANDARD_FBS:
            return STANDARD_FBS[type_name]()
        raise StError(f'type {type_name} is outside the subset')

    def coerce(self, type_name, value, where):
        """The value as stored in a variable of type_name, or StError."""
        if type_name == 'BOOL':
            ok = isinstance(value, bool)
        elif type_name in INTEGERS:
            if is_int(value):
                return wrap(value, type_name)
            ok = False
        elif type_name == 'TIME':
            ok = isinstance(value, Time)
        elif type_name in self.enums:
            ok = isinstance(value, EnumValue) and value.type == type_name
        else:
            ok = isinstance(value, Struct) and value._type == type_name
        if not ok:
            raise StError(f'{where}: cannot store {value!r} in a {type_name}')
        return value

    def instance(self, fb_name):
        return Instance(self, self.fbs[fb_name])


class Evaluator:
    """Expressions, over the variables in scope (a name -> value mapping)."""

    def __init__(self, program, scope):
        self.program = program
        self.scope = scope

    def lookup(self, path, line):
        head = path[0]
        if head in self.program.enums:
            if len(path) != 2 or path[1] not in self.program.enums[head]:
                raise StError(f'line {line}: {".".join(path)} is not a value of {head}')
            return EnumValue(head, path[1], self.program.enums[head][path[1]])
        if head not in self.scope:
            raise StError(f'line {line}: unknown name {head}')
        value = self.scope[head]
        for part in path[1:]:
            if isinstance(value, Struct):
                value = value[part]
            elif type(value) in STANDARD_FBS.values() and part in ('Q', 'ET'):
                value = getattr(value, part)
            else:
                raise StError(f'line {line}: {".".join(path)} is outside the subset')
        return value

    def eval(self, node):
        kind = node[0]
        if kind == 'const':
            return node[1]
        if kind == 'name':
            return self.lookup(node[1], node[2])
        if kind == 'not':
            v = self.eval(node[1])
            if not isinstance(v, bool):
                raise StError(f'NOT of {v!r}: the subset applies NOT to BOOL only')
            return not v
        if kind == 'negate':
            v = self.eval(node[1])
            if not is_int(v):
                raise StError(f'minus of {v!r}')
            return -v
        if kind == 'abs':
            v = self.eval(node[1])
            if not is_int(v):
                raise StError(f'ABS of {v!r}')
            return abs(v)
        return self.binary(node[1], self.eval(node[2]), self.eval(node[3]))

    @staticmethod
    def binary(op, a, b):
        if op in ('AND', 'OR', 'XOR'):
            if isinstance(a, bool) and isinstance(b, bool):
                return {'AND': a and b, 'OR': a or b, 'XOR': a != b}[op]
            if is_int(a) and is_int(b):
                return {'AND': a & b, 'OR': a | b, 'XOR': a ^ b}[op]
        elif op in ('=', '<>'):
            if isinstance(a, EnumValue) and isinstance(b, EnumValue) and a.type == b.type:
                same = a.value == b.value
            elif type(a) is type(b) and not isinstance(a, (EnumValue, Struct)):
                same = a == b
            else:
                raise StError(f'{a!r} {op} {b!r}: different types')
            return same if op == '=' else not same
        elif is_int(a) and is_int(b):
            if op == '/':
                if b == 0:
                    raise StError('division by zero')
                return abs(a) // abs(b) * (1 if (a < 0) == (b < 0) else -1)
            if op == 'MOD':
                if b == 0:
                    raise StError('MOD by zero')
                return a - b * Evaluator.binary('/', a, b)
            return {'+': a + b, '-': a - b, '*': a * b, '<': a < b, '>': a > b,
                    '<=': a <= b, '>=': a >= b}[op]
        elif isinstance(a, Time) and isinstance(b, Time) and op in ('<', '>', '<=', '>='):
            return Evaluator.binary(op, a.ms, b.ms)
        raise StError(f'{a!r} {op} {b!r}: not allowed on these types')


class Instance:
    """One instance of a FUNCTION_BLOCK. scan() runs its body once, like a PLC cycle."""

    def __init__(self, program, fb):
        self.program = program
        self.fb = fb
        self.kinds = {name: section for name, (section, _, _) in fb['vars'].items()}
        self.types = {name: t for name, (_, t, _) in fb['vars'].items()}
        for name, t in self.types.items():
            if not program.is_type(t):
                raise StError(f'{fb["name"]}.{name}: type {t} is outside the subset')
        self.vars = {name: (None if section == 'in_out' else program.initial(t, init))
                     for name, (section, t, init) in fb['vars'].items()}
        self.now = 0

    def __getitem__(self, name):
        return self.vars[name]

    def scan(self, now, **inputs):
        """Set the inputs (in-out ones as Structs), run the body once at time `now`
        (milliseconds), and return the outputs."""
        self.now = now
        for name, value in inputs.items():
            if self.kinds.get(name) in ('input', 'in_out'):
                self.vars[name] = self.program.coerce(self.types[name], value, name)
            else:
                raise StError(f'{name} is not an input of {self.fb["name"]}')
        for name, section in self.kinds.items():
            if section == 'in_out' and self.vars[name] is None:
                raise StError(f'VAR_IN_OUT {name} was never passed')
        self.run(self.fb['body'])
        return {n: v for n, v in self.vars.items() if self.kinds[n] == 'output'}

    def run(self, body):
        evaluator = Evaluator(self.program, self.vars)
        for node in body:
            kind = node[0]
            if kind == 'assign':
                self.assign(node[1], evaluator.eval(node[2]), node[3])
            elif kind == 'if':
                for cond, branch in node[1]:
                    if self.condition(evaluator.eval(cond)):
                        self.run(branch)
                        break
                else:
                    self.run(node[2])
            elif kind == 'case':
                selector = evaluator.eval(node[1])
                for labels, branch in node[2]:
                    if any(Evaluator.binary('=', selector, evaluator.eval(label))
                           for label in labels):
                        self.run(branch)
                        break
                else:
                    self.run(node[3])
            elif kind == 'call':
                self.call(node[1], node[2], node[3], evaluator)
            elif kind != 'nop':
                raise StError(f'statement {kind} outside the subset')

    @staticmethod
    def condition(value):
        if not isinstance(value, bool):
            raise StError(f'condition {value!r} is not BOOL')
        return value

    def assign(self, path, value, line):
        name = path[0]
        section = self.kinds.get(name)
        if section is None:
            raise StError(f'line {line}: unknown name {name}')
        if section in ('input', 'constant'):
            raise StError(f'line {line}: {name} is a {section} and is not written')
        if len(path) == 1:
            self.vars[name] = self.program.coerce(self.types[name], value, f'line {line}')
        elif len(path) == 2 and isinstance(self.vars[name], Struct):
            self.vars[name][path[1]] = value
        else:
            raise StError(f'line {line}: assignment to {".".join(path)} is outside the '
                          f'subset')

    def call(self, name, args, line, evaluator):
        block = self.vars.get(name)
        if type(block) not in STANDARD_FBS.values():
            raise StError(f'line {line}: {name} is not a TON or R_TRIG instance')
        for param, expr in args:
            if param not in block.inputs:
                raise StError(f'line {line}: {name} has no input {param}')
            setattr(block, param, self.program.coerce(block.inputs[param],
                                                      evaluator.eval(expr),
                                                      f'line {line}'))
        block.run(self.now)
