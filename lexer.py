from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenKind(Enum):
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
    b"keep": TokenKind.KEEP,
    b"change": TokenKind.CHANGE,
    b"i32": TokenKind.I32,
    b"i64": TokenKind.I64,
    b"flag": TokenKind.FLAG,
    b"when": TokenKind.WHEN,
    b"otherwise": TokenKind.OTHERWISE,
}

SPECIALS = (
    ("(✿◠‿◠)".encode("utf-8"), TokenKind.TRUE),
    ("(╥﹏╥)".encode("utf-8"), TokenKind.FALSE),
    ("(⊙_⊙;)".encode("utf-8"), TokenKind.FINISH),
    ("ಠ_ಠ".encode("utf-8"), TokenKind.NOT),
    (b"==", TokenKind.EQUAL),
    (b"!=", TokenKind.NOT_EQUAL),
    (b"<-", TokenKind.ASSIGN),
)

SINGLE = {
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
            elif self._scan_special():
                pass
            elif byte in SINGLE:
                self._emit(SINGLE[byte], 1)
            else:
                self._unexpected_byte()
        self.tokens.append(Token(TokenKind.EOF, "", self.line, self.column))
        return self.tokens

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
