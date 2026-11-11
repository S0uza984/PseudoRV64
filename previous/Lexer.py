from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Iterator


class TokenKind(enum.Enum):
    """Classe já implementada: nomes e números não devem ser alterados."""

    EOF = -1

    IDENTIFIER = 1
    INT_LITERAL = 2
    STRING_LITERAL = 3

    KW_INT = 10
    KW_BOOL = 11
    KW_VOID = 12
    KW_TRUE = 13
    KW_FALSE = 14
    KW_IF = 15
    KW_ELSE = 16
    KW_WHILE = 17
    KW_RETURN = 18
    KW_PRINT = 19

    PLUS = 20
    MINUS = 21
    STAR = 22
    SLASH = 23
    PERCENT = 24
    LESS = 25
    LESS_EQUAL = 26
    GREATER = 27
    GREATER_EQUAL = 28
    EQUAL_EQUAL = 29
    NOT_EQUAL = 30
    LOGICAL_AND = 31
    LOGICAL_OR = 32
    LOGICAL_NOT = 33
    ASSIGN = 34

    LEFT_PAREN = 40
    RIGHT_PAREN = 41
    LEFT_BRACE = 42
    RIGHT_BRACE = 43
    COMMA = 44
    SEMICOLON = 45


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    value: int | str | bool | None
    line: int
    column: int

    def __str__(self) -> str:
        return (
            f"<{self.kind.value}, {self.kind.name}, {self.lexeme!r}, "
            f"{self.value!r}, {self.line}, {self.column}>"
        )


class LexerError(Exception):
    def __init__(self, message: str, line: int, column: int):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column

    def __str__(self) -> str:
        return f"erro léxico em {self.line}:{self.column}: {self.message}"


class Lexer:
    """Converte texto-fonte MicroC em uma sequência de tokens."""
    
# Dicionario com as palavras reservadas para conseguir identificar cada um dos tipos, incluindo diferenciação com IDENTIFIER
    _palavrasChave = {
        "int": TokenKind.KW_INT,
        "bool": TokenKind.KW_BOOL,
        "void": TokenKind.KW_VOID,
        "true": TokenKind.KW_TRUE,
        "false": TokenKind.KW_FALSE,
        "if": TokenKind.KW_IF,
        "else": TokenKind.KW_ELSE,
        "while": TokenKind.KW_WHILE,
        "return": TokenKind.KW_RETURN,
        "print": TokenKind.KW_PRINT,
    }

    _caracterUnico = {
        "+": TokenKind.PLUS,
        "-": TokenKind.MINUS,
        "*": TokenKind.STAR,
        "/": TokenKind.SLASH,
        "%": TokenKind.PERCENT,
        "<": TokenKind.LESS,
        ">": TokenKind.GREATER,
        "!": TokenKind.LOGICAL_NOT,
        "=": TokenKind.ASSIGN,
        "(": TokenKind.LEFT_PAREN,
        ")": TokenKind.RIGHT_PAREN,
        "{": TokenKind.LEFT_BRACE,
        "}": TokenKind.RIGHT_BRACE,
        ",": TokenKind.COMMA,
        ";": TokenKind.SEMICOLON,
    }
    
    _caracterDuplo = {
        "<=": TokenKind.LESS_EQUAL,
        ">=": TokenKind.GREATER_EQUAL,
        "==": TokenKind.EQUAL_EQUAL,
        "!=": TokenKind.NOT_EQUAL,
        "&&": TokenKind.LOGICAL_AND,
        "||": TokenKind.LOGICAL_OR,
    }
    
    _escapes = {
        "n": "\n",
        "t": "\t",
        '"': '"',
        "\\": "\\",
    }

# Inicio na posicao zero, linha 1, coluna 1
    def __init__(self, source: str):
        self.source = source
        self._posicao = 0
        self._linha = 1
        self._coluna = 1

# Verifica se chegou no fim do arquivo
    def _fim(self) -> bool:
        return self._posicao >= len(self.source)

# Posição atual
    def _atual(self) -> str:
        return self.source[self._posicao]

# Verifica qual o proximo caractere, principalmente para os casos de caracteres duplos e.g. <=
    def _espiarProximo(self, offset: int = 1) -> str:
        index = self._posicao + offset
        return self.source[index] if index < len(self.source) else ""

# Continua a leitura para a proxima posição, se for final de linha ele pula para a proxima linha
    def _avancar(self) -> str:
        caractere = self._atual()
        self._posicao += 1
        
        if caractere == "\n":
            self._linha += 1
            self._coluna = 1
        else:
            self._coluna += 1
        
        return caractere

# Retorna aonde exatamente está o erro, com mensagem, linha e coluna
    def _erro(self, message: str, line: int | None = None, column: int | None = None):
        raise LexerError(
            message,
            self._linha if line is None else line,
            self._coluna if column is None else column,
        )

# Criação dos tokens
    def _criarToken(self, kind: TokenKind, lexeme: str, value: int | str | bool | None, line: int, column: int,) -> Token:
        return Token(kind, lexeme, value, line, column)

# Pular entradas ignoradas
    def _pularIgnorados(self) -> None:
        while not self._fim():
            caractere = self._atual()

            if caractere in " \t\r\n":
                self._avancar()
                continue

            if caractere == "/" and self._espiarProximo() == "/":
                self._avancar()
                self._avancar()
                while not self._fim() and self._atual() != "\n":
                    foraasc = self._atual()
                    if ord(foraasc) > 127:
                        self._erro("Caractere inválido no comentário")
                    self._avancar()
                continue

            if caractere == "/" and self._espiarProximo() == "*":
                # Manter linha e coluna em caso de erro
                linha_inicial = self._linha
                coluna_inicial = self._coluna

                self._avancar()
                self._avancar()
                while not self._fim():
                    if self._atual() == "*" and self._espiarProximo() == "/":
                        self._avancar()
                        self._avancar()
                        break
                    foraasc = self._atual()
                    if ord(foraasc) > 127:
                        self._erro("Caractere inválido no comentário")
                    self._avancar()
                else:
                    self._erro("Comentário de bloco não encerrado", linha_inicial, coluna_inicial)
                continue

            break

# Identificar IDENTIFIER ou palavra chave
    def _identificarIDENTIFIERouPALAVRACHAVE(self) -> Token:
        # Manter linha, coluna para token e posição inicial para o lexema
        linha_inicial = self._linha
        coluna_inicial = self._coluna
        inicio = self._posicao

        while not self._fim():
            caractere = self._atual()
            if ("a" <= caractere <= "z") or ("A" <= caractere <= "Z") or caractere.isdigit() or caractere == "_":
                self._avancar()
            else:
                break

        lexema = self.source[inicio:self._posicao]

        kind = self._palavrasChave.get(lexema)

        if kind is None:
            return self._criarToken(TokenKind.IDENTIFIER, lexema, lexema, linha_inicial, coluna_inicial)

        if kind is TokenKind.KW_TRUE:
            value = True
        elif kind is TokenKind.KW_FALSE:
            value = False
        else:
            value = None

        return self._criarToken(kind, lexema, value, linha_inicial, coluna_inicial)

# Identificar inteiros
    def _identificarINTEIROS(self) -> Token:
        # Manter linha, coluna para token e posição inicial para o lexema
        linha_inicial = self._linha
        coluna_inicial = self._coluna
        inicio = self._posicao

        while not self._fim() and self._atual().isdigit():
            self._avancar()

        lexema = self.source[inicio:self._posicao]
        
        return self._criarToken(TokenKind.INT_LITERAL, lexema, int(lexema), linha_inicial, coluna_inicial)

# Identificar strings
    def _identificarSTRINGS(self) -> Token:
        # Manter linha, coluna para token e posição inicial para o lexema
        linha_inicial = self._linha
        coluna_inicial = self._coluna
        inicio = self._posicao

        #Avançar para começar a String
        self._avancar()

        lista: list[str] = []

        while not self._fim():
            caractere = self._atual()

            if caractere == '"':
                self._avancar()
                lexema = self.source[inicio:self._posicao]
                return self._criarToken(TokenKind.STRING_LITERAL, lexema, "".join(lista), linha_inicial, coluna_inicial)

            if caractere == "\n":
                self._erro("quebra de linha dentro string", self._linha, self._coluna)

            if caractere == "\r":
                self._erro("retorno de carro dentro string", self._linha, self._coluna)

            if caractere == "\\":
                linha_escape = self._linha
                coluna_escape = self._coluna
                self._avancar()
                if self._fim():
                    self._erro("String não terminado", linha_inicial, coluna_inicial)

                escaped = self._atual()
                if escaped not in self._escapes:
                    self._erro(f"escape inválido: \\{escaped}", linha_escape, coluna_escape)
                lista.append(self._escapes[escaped])
                self._avancar()
                continue

            if ord(caractere) > 127:
                self._erro("Caractere inválido em string")

            lista.append(caractere)
            self._avancar()

        self._erro("String não encerrada", linha_inicial, coluna_inicial)

    def tokens(self) -> Iterator[Token]:
        """Produza todos os tokens significativos e um único EOF ao final."""
        while True:
            self._pularIgnorados()

            if self._fim():
                yield self._criarToken(TokenKind.EOF, "", None, self._linha, self._coluna)
                return

            caractere = self._atual()

            if ("a" <= caractere <= "z") or ("A" <= caractere <= "Z") or caractere == "_":
                yield self._identificarIDENTIFIERouPALAVRACHAVE()
                continue

            if caractere.isdigit():
                yield self._identificarINTEIROS()
                continue

            if caractere == '"':
                yield self._identificarSTRINGS()
                continue

            linha_inicial = self._linha
            coluna_inicial = self._coluna
            par = caractere + self._espiarProximo()

            if par in self._caracterDuplo:
                self._avancar()
                self._avancar()
                yield self._criarToken(self._caracterDuplo[par], par, None, linha_inicial, coluna_inicial)
                continue

            if caractere in self._caracterUnico:
                self._avancar()
                yield self._criarToken(self._caracterUnico[caractere], caractere, None, linha_inicial, coluna_inicial)
                continue

            if caractere == "&":
                self._erro("Esperado caractere '&' após outro '&'")
            if caractere == "|":
                self._erro("Esperado caractere '|' após outro '|'")

            self._erro(f"Caractere inválido: {caractere!r}")


    def scan(self) -> list[Token]:
        return list(self.tokens())

