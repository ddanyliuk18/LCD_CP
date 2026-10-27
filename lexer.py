from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenKind(Enum):
    CARD = auto()
    SERVE = auto()
    RETROCEDE = auto()
    DRAW = auto()
    ENGRAVE = auto()
    STRING = auto()
    STRING_LITERAL = auto()
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    DOT = auto()
    ARROW = auto()
    KEEP = auto()
    CHANGE = auto()
    I32 = auto()
    I64 = auto()
    FLAG = auto()
    WHEN = auto()
    OTHERWISE = auto()
    IDENTIFIER = auto()
    INTEGER = auto()
    TRUE = auto()
    FALSE = auto()
    NOT = auto()
    FINISH = auto()
    COLON = auto()
    DECLARE_EQUAL = auto()
    EQUAL = auto()
    NOT_EQUAL = auto()
    ASSIGN = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    LBRACE = auto()
    RBRACE = auto()
    NL = auto()
    EOF = auto()


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    column: int


class LexError(Exception):
    def __init__(self, line: int, column: int, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.column = column
        self.message = message


KEYWORDS = {
    b"card": TokenKind.CARD,
    b"serve": TokenKind.SERVE,
    b"retrocede": TokenKind.RETROCEDE,
    b"draw": TokenKind.DRAW,
    b"Engrave": TokenKind.ENGRAVE,
    b"string": TokenKind.STRING,
    b"keep": TokenKind.KEEP,
    b"change": TokenKind.CHANGE,
    b"i32": TokenKind.I32,
    b"i64": TokenKind.I64,
    b"flag": TokenKind.FLAG,
    b"when": TokenKind.WHEN,
    b"otherwise": TokenKind.OTHERWISE,
}

SPECIALS = (
    (b"->", TokenKind.ARROW),
    ("(✿◠‿◠)".encode("utf-8"), TokenKind.TRUE),
    ("(╥﹏╥)".encode("utf-8"), TokenKind.FALSE),
    ("(⊙_⊙;)".encode("utf-8"), TokenKind.FINISH),
    ("ಠ_ಠ".encode("utf-8"), TokenKind.NOT),
    (b"==", TokenKind.EQUAL),
    (b"!=", TokenKind.NOT_EQUAL),
    (b"<-", TokenKind.ASSIGN),
)

SINGLE = {
    ord("("): TokenKind.LPAREN,
    ord(")"): TokenKind.RPAREN,
    ord(","): TokenKind.COMMA,
    ord("."): TokenKind.DOT,
    ord(":"): TokenKind.COLON,
    ord("="): TokenKind.DECLARE_EQUAL,
    ord("+"): TokenKind.PLUS,
    ord("-"): TokenKind.MINUS,
    ord("*"): TokenKind.STAR,
    ord("{"): TokenKind.LBRACE,
    ord("}"): TokenKind.RBRACE,
}


def _is_letter(byte: int) -> bool:
    return ord("A") <= byte <= ord("Z") or ord("a") <= byte <= ord("z")


def _is_digit(byte: int) -> bool:
    return ord("0") <= byte <= ord("9")


class Lexer:
    def __init__(self, source: bytes) -> None:
        self.source = source
        self.index = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def scan(self) -> List[Token]:
        while self.index < len(self.source):
            byte = self.source[self.index]
            if byte == ord(" ") or byte == ord("\t"):
                self._advance(1)
            elif byte == ord("\n"):
                self._newline(1)
            elif byte == ord("\r"):
                if self._starts_with(b"\r\n"):
                    self._newline(2)
                else:
                    raise LexError(self.line, self.column, "bare carriage return is not allowed")
            elif _is_letter(byte):
                self._scan_word()
            elif _is_digit(byte):
                self._scan_integer()
            elif byte == ord('"'):
                self._scan_string()
            elif self._scan_special():
                pass
            elif byte in SINGLE:
                self._emit(SINGLE[byte], 1)
            else:
                self._unexpected_byte()
        self.tokens.append(Token(TokenKind.EOF, "", self.line, self.column))
        return self.tokens

    def _scan_string(self) -> None:
        line, column = self.line, self.column
        self._advance(1)
        value = bytearray()
        positions = []
        escapes = {ord('n'): b'\n', ord('t'): b'\t', ord('"'): b'"', ord('\\'): b'\\'}
        while self.index < len(self.source):
            byte = self.source[self.index]
            if byte == ord('"'):
                self._advance(1)
                try:
                    decoded = value.decode('utf-8')
                except UnicodeDecodeError as error:
                    raise LexError(line, positions[error.start], 'invalid UTF-8 in string')
                self.tokens.append(Token(TokenKind.STRING_LITERAL, decoded, line, column))
                return
            if byte in (10, 13, 0):
                raise LexError(self.line, self.column, 'newline or NUL in string')
            if byte == ord('\\'):
                self._advance(1)
                if self.index >= len(self.source) or self.source[self.index] not in escapes:
                    raise LexError(self.line, self.column, 'unsupported string escape')
                value.extend(escapes[self.source[self.index]])
                positions.append(self.column)
            else:
                value.append(byte)
                positions.append(self.column)
            self._advance(1)
        raise LexError(line, column, 'unterminated string literal')

    def _scan_word(self) -> None:
        start = self.index
        column = self.column
        while self.index < len(self.source):
            byte = self.source[self.index]
            if not (_is_letter(byte) or _is_digit(byte) or byte == ord("_")):
                break
            self._advance(1)
        raw = self.source[start:self.index]
        kind = KEYWORDS.get(raw, TokenKind.IDENTIFIER)
        self.tokens.append(Token(kind, raw.decode("ascii"), self.line, column))

    def _scan_integer(self) -> None:
        start = self.index
        column = self.column
        while self.index < len(self.source) and _is_digit(self.source[self.index]):
            self._advance(1)
        raw = self.source[start:self.index]
        self.tokens.append(Token(TokenKind.INTEGER, raw.decode("ascii"), self.line, column))

    def _scan_special(self) -> bool:
        for raw, kind in SPECIALS:
            if self._starts_with(raw):
                self._emit(kind, len(raw))
                return True
        return False

    def _starts_with(self, raw: bytes) -> bool:
        return self.source.startswith(raw, self.index)

    def _emit(self, kind: TokenKind, size: int) -> None:
        raw = self.source[self.index:self.index + size]
        self.tokens.append(Token(kind, raw.decode("utf-8"), self.line, self.column))
        self._advance(size)

    def _advance(self, size: int) -> None:
        self.index += size
        self.column += size

    def _newline(self, size: int) -> None:
        self.tokens.append(Token(TokenKind.NL, "\n", self.line, self.column))
        self.index += size
        self.line += 1
        self.column = 1

    def _unexpected_byte(self) -> None:
        byte = self.source[self.index]
        if byte < 128:
            shown = chr(byte)
            raise LexError(self.line, self.column, f"unexpected character {shown!r}")
        try:
            remaining = self.source[self.index:]
            character = remaining.decode("utf-8")[0]
            raise LexError(self.line, self.column, f"unexpected character {character!r}")
        except UnicodeDecodeError:
            raise LexError(self.line, self.column, "invalid UTF-8 byte sequence")
