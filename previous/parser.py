from __future__ import annotations

from collections.abc import Sequence

from Lexer import Token, TokenKind
from ast_nodes import (
    Block,
    Expr,
    FunctionDecl,
    Node,
    Parameter,
    PrintItem,
    Program,
    SourceSpan,
    Stmt,
    StringLiteral,
    TypeName,
    UnaryOperator,
    BinaryOperator,
    VarDecl,
    Assignment,
    CallStmt,
    IfStmt,
    WhileStmt,
    ReturnStmt,
    PrintStmt,
    BinaryExpr,
    UnaryExpr,
    CallExpr,
    IdentifierExpr,
    IntLiteral,
    BoolLiteral,
)


TYPE_START = {TokenKind.KW_INT, TokenKind.KW_BOOL, TokenKind.KW_VOID}
EXPRESSION_START = {
    TokenKind.IDENTIFIER,
    TokenKind.INT_LITERAL,
    TokenKind.KW_FALSE,
    TokenKind.KW_TRUE,
    TokenKind.LEFT_PAREN,
    TokenKind.LOGICAL_NOT,
    TokenKind.MINUS,
}
STATEMENT_START = TYPE_START | {
    TokenKind.IDENTIFIER,
    TokenKind.KW_IF,
    TokenKind.KW_WHILE,
    TokenKind.KW_RETURN,
    TokenKind.KW_PRINT,
    TokenKind.LEFT_BRACE,
}


TYPE_BY_TOKEN = {
    TokenKind.KW_INT: TypeName.INT,
    TokenKind.KW_BOOL: TypeName.BOOL,
    TokenKind.KW_VOID: TypeName.VOID,
}


class ParserError(Exception):
    def __init__(self, token: Token, expected: set[TokenKind]):
        self.token = token
        self.expected = frozenset(expected)
        super().__init__()

    @property
    def line(self) -> int:
        return self.token.line

    @property
    def column(self) -> int:
        return self.token.column

    def __str__(self) -> str:
        names = ", ".join(kind.name for kind in sorted(
            self.expected,
            key=lambda kind: kind.value,
        ))
        return (
            f"erro sintático em {self.line}:{self.column}: esperado {{{names}}}, "
            f"encontrado {self.token.kind.name} ({self.token.lexeme!r})"
        )


class Parser:
    def __init__(self, tokens: Sequence[Token]):
        self.tokens = list(tokens)
        if not self.tokens:
            raise ValueError("a sequência de tokens deve terminar em EOF")
        if self.tokens[-1].kind is not TokenKind.EOF:
            raise ValueError("o último token deve ser EOF")
        if any(token.kind is TokenKind.EOF for token in self.tokens[:-1]):
            raise ValueError("EOF deve aparecer uma única vez, no final")
        self.current = 0

    def peek(self, offset: int = 0) -> Token:
        index = min(self.current + offset, len(self.tokens) - 1)
        return self.tokens[index]

    def check(self, kind: TokenKind) -> bool:
        return self.peek().kind is kind

    def advance(self) -> Token:
        token = self.peek()
        if self.current < len(self.tokens) - 1:
            self.current += 1
        return token

    def match(self, *kinds: TokenKind) -> Token | None:
        if self.peek().kind in kinds:
            return self.advance()
        return None

    def expect(self, kinds: TokenKind | set[TokenKind]) -> Token:
        expected = kinds if isinstance(kinds, set) else {kinds}
        token = self.peek()
        if token.kind not in expected:
            raise ParserError(token, set(expected))
        return self.advance()

    @staticmethod
    def _token_span(token: Token) -> SourceSpan:
        return SourceSpan(
            token.line,
            token.column,
            token.line,
            token.column + len(token.lexeme),
        )

    @staticmethod
    def _start(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.start_line, value.span.start_column
        return value.line, value.column

    @staticmethod
    def _end(value: Token | Node) -> tuple[int, int]:
        if isinstance(value, Node):
            return value.span.end_line, value.span.end_column
        return value.line, value.column + len(value.lexeme)

    @classmethod
    def _span(cls, first: Token | Node, last: Token | Node) -> SourceSpan:
        start_line, start_column = cls._start(first)
        end_line, end_column = cls._end(last)
        return SourceSpan(start_line, start_column, end_line, end_column)

    def parse(self) -> Program:
        return self.parse_program()

    # program ::= function* EOF
    def parse_program(self) -> Program:
        start = self.peek()
        functions: list[FunctionDecl] = []
        while self.peek().kind in TYPE_START:
            functions.append(self.parse_function())
        eof = self.expect(TokenKind.EOF)
        return Program(functions, span=self._span(start, eof))

    # function ::= type IDENTIFIER ... block
    def parse_function(self) -> FunctionDecl:
        start = self.peek()
        return_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)
        self.expect(TokenKind.LEFT_PAREN)
        parameters = (
            self.parse_parameter_list()
            if self.peek().kind in TYPE_START
            else []
        )
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return FunctionDecl(
            return_type,
            name.lexeme,
            parameters,
            body,
            span=self._span(start, body),
        )

    # type ::= KW_INT | KW_BOOL | KW_VOID
    def parse_type(self) -> TypeName:
        token = self.expect(TYPE_START)
        return TYPE_BY_TOKEN[token.kind]

    def parse_parameter_list(self) -> list[Parameter]:
        parameters = [self.parse_parameter()]

        while self.match(TokenKind.COMMA):
            parameters.append(self.parse_parameter())

        return parameters
       
    def parse_parameter(self) -> Parameter:
        #pega o token atual sem consumir ele
        #aqui estamos guardando onde o parâmetro começa
        #exemplo: em "int idade", pega o token "int"
        start = self.peek()

        #chama a função parse_type() para ler o tipo do parâmetro
        #exemplo: "int" vira TypeName.INT
        #depois disso, o "int" já foi consumido e o próximo token é "idade"
        parameter_type = self.parse_type()

        #exige que o próximo token seja um IDENTIFIER
        #se for, consome o token e guarda ele na variável "name"
        #exemplo: name será o Token correspondente a "idade"
        name = self.expect(TokenKind.IDENTIFIER)

        return Parameter(
        #coloca o tipo do parâmetro
        #exemplo: TypeName.INT    
        parameter_type,

        #pega o texto do token IDENTIFIER
        #name é o Token "idade"
        #name.lexeme é a string "idade"
        name.lexeme,

        #calcula a posição do parâmetro no código-fonte
        #começa no token "int" (start)
        #e termina no token "idade" (name)
        span=self._span(start, name),
        )
        

    def parse_block(self) -> Block:
        #guarda o token atual sem consumi-lo, para usar como início do span do bloco
        start = self.peek()

        #exige e consome o token '{', que inicia o bloco
        self.expect(TokenKind.LEFT_BRACE)

        #lista que vai armazenar todos os comandos (statements) do bloco
        statements = []

        #enquanto o token atual puder iniciar um statement, continua lendo statements
        while self.peek().kind in STATEMENT_START:
            #analisa um statement e adiciona o resultado à lista do bloco
            statements.append(self.parse_statement())

        #exige e consome o token '}', que encerra o bloco
        end = self.expect(TokenKind.RIGHT_BRACE)

        #cria e retorna o nó Block com os statements e o intervalo de origem do bloco.
        return Block(statements, span=self._span(start, end))

    def parse_statement(self) -> Stmt:
        if self.peek().kind in TYPE_START:
            return self.parse_declaration()

        elif self.peek().kind is TokenKind.IDENTIFIER:
            return self.parse_id_or_call_statement()

        elif self.peek().kind is TokenKind.KW_IF:
            return self.parse_if_statement()

        elif self.peek().kind is TokenKind.KW_WHILE:
            return self.parse_while_statement()

        elif self.peek().kind is TokenKind.KW_RETURN:
            return self.parse_return_statement()

        elif self.peek().kind is TokenKind.KW_PRINT:
            return self.parse_print_statement()

        elif self.peek().kind is TokenKind.LEFT_BRACE:
            return self.parse_block()

        else:
            raise ParserError(self.peek(), STATEMENT_START)
        
    def parse_id_or_call_statement(self) -> Stmt:
        start = self.expect(TokenKind.IDENTIFIER)
        branch = self.expect({TokenKind.ASSIGN, TokenKind.LEFT_PAREN})

        if branch.kind is TokenKind.ASSIGN:
            value = self.parse_expression()
            end = self.expect(TokenKind.SEMICOLON)
            target = IdentifierExpr(start.lexeme, span=self._token_span(start))
            return Assignment(target, value, span=self._span(start, end))

        arguments = self.parse_arguments()
        close = self.expect(TokenKind.RIGHT_PAREN)
        end = self.expect(TokenKind.SEMICOLON)
        call = CallExpr(start.lexeme, arguments, span=self._span(start, close))
        return CallStmt(call, span=self._span(start, end))

    def parse_declaration(self) -> Stmt:
        start = self.peek()
        declared_type = self.parse_type()
        name = self.expect(TokenKind.IDENTIFIER)

        initializer = None
        if self.match(TokenKind.ASSIGN):
            initializer = self.parse_expression()

        end = self.expect(TokenKind.SEMICOLON)
        return VarDecl(
            declared_type,
            name.lexeme,
            initializer,
            span=self._span(start, end),
        )

    def parse_if_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_IF)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        then_block = self.parse_block()

        else_block = None
        if self.match(TokenKind.KW_ELSE):
            else_block = self.parse_block()

        end = then_block if else_block is None else else_block
        return IfStmt(
            condition,
            then_block,
            else_block,
            span=self._span(start, end),
        )

    def parse_while_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_WHILE)
        self.expect(TokenKind.LEFT_PAREN)
        condition = self.parse_expression()
        self.expect(TokenKind.RIGHT_PAREN)
        body = self.parse_block()
        return WhileStmt(condition, body, span=self._span(start, body))

    def parse_return_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_RETURN)
        if self.peek().kind in EXPRESSION_START:
            retorno_exp = self.parse_expression()
        else:
            retorno_exp = None
        end = self.expect(TokenKind.SEMICOLON)
        return ReturnStmt(retorno_exp, span=self._span(start, end))    

    def parse_print_statement(self) -> Stmt:
        start = self.expect(TokenKind.KW_PRINT)
        self.expect(TokenKind.LEFT_PAREN)
        lista = [self.parse_print_item()]
        while self.match(TokenKind.COMMA):
            lista.append(self.parse_print_item())
        self.expect(TokenKind.RIGHT_PAREN)   
        end = self.expect(TokenKind.SEMICOLON) 
        return PrintStmt(lista, span=self._span(start, end))

    def parse_print_item(self) -> PrintItem:
        if self.peek().kind in EXPRESSION_START:
            return self.parse_expression()
        elif self.check(TokenKind.STRING_LITERAL):
            return self.parse_string_literals()
        else:
            raise ParserError(self.peek(), EXPRESSION_START | {TokenKind.STRING_LITERAL})

    def parse_string_literals(self) -> StringLiteral:
        start = self.expect(TokenKind.STRING_LITERAL)
        value = start.value
        end = start
        while self.check(TokenKind.STRING_LITERAL):
            end = self.advance()
            value += end.value
        return StringLiteral(value, span=self._span(start, end))

    def parse_expression(self) -> Expr:
        return self.parse_logical_or()

    def parse_logical_or(self) -> Expr:
        left = self.parse_logical_and()
        while self.match(TokenKind.LOGICAL_OR):
            right = self.parse_logical_and()
            left = BinaryExpr(BinaryOperator.LOGICAL_OR, left, right, span=self._span(left, right))
        return left

    def parse_logical_and(self) -> Expr:
        left = self.parse_equality()
        while self.match(TokenKind.LOGICAL_AND):
            right = self.parse_equality()
            left = BinaryExpr(BinaryOperator.LOGICAL_AND, left, right, span=self._span(left, right))
        return left

    def parse_equality(self) -> Expr:
        left = self.parse_relational()
        operator_token = self.match(TokenKind.EQUAL_EQUAL, TokenKind.NOT_EQUAL)
        while operator_token is not None:
            right = self.parse_relational()
            if operator_token.kind is TokenKind.EQUAL_EQUAL:
                operator = BinaryOperator.EQUAL
            else:
                operator = BinaryOperator.NOT_EQUAL
            left = BinaryExpr(operator, left, right, span=self._span(left, right))
            operator_token = self.match(TokenKind.EQUAL_EQUAL, TokenKind.NOT_EQUAL)
        return left

    def parse_relational(self) -> Expr:
        left = self.parse_additive()
        operator_token = self.match(TokenKind.LESS, TokenKind.LESS_EQUAL, TokenKind.GREATER, TokenKind.GREATER_EQUAL)
        while operator_token is not None:
            right = self.parse_additive()
            if operator_token.kind is TokenKind.LESS:
                operator = BinaryOperator.LESS
            elif operator_token.kind is TokenKind.LESS_EQUAL:
                operator = BinaryOperator.LESS_EQUAL
            elif operator_token.kind is TokenKind.GREATER:
                operator = BinaryOperator.GREATER
            else:
                operator = BinaryOperator.GREATER_EQUAL
            left = BinaryExpr(operator, left, right, span=self._span(left, right))
            operator_token = self.match(TokenKind.LESS, TokenKind.LESS_EQUAL, TokenKind.GREATER, TokenKind.GREATER_EQUAL)
        return left

    def parse_additive(self) -> Expr:
        left = self.parse_multiplicative()
        operator_token = self.match(TokenKind.PLUS, TokenKind.MINUS)
        while operator_token is not None:
            right = self.parse_multiplicative()
            if operator_token.kind is TokenKind.PLUS:
                operator = BinaryOperator.ADD
            else:
                operator = BinaryOperator.SUBTRACT
            left = BinaryExpr(operator, left, right, span=self._span(left, right))
            operator_token = self.match(TokenKind.PLUS, TokenKind.MINUS)
        return left

    def parse_multiplicative(self) -> Expr:
        left = self.parse_unary()
        operator_token = self.match(TokenKind.STAR, TokenKind.SLASH, TokenKind.PERCENT)
        while operator_token is not None:
            right = self.parse_unary()
            if operator_token.kind is TokenKind.STAR:
                operator = BinaryOperator.MULTIPLY
            elif operator_token.kind is TokenKind.SLASH:
                operator = BinaryOperator.DIVIDE
            else:
                operator = BinaryOperator.REMAINDER
            left = BinaryExpr(operator, left, right, span=self._span(left, right))
            operator_token = self.match(TokenKind.STAR, TokenKind.SLASH, TokenKind.PERCENT)
        return left
        

    def parse_unary(self) -> Expr:
        operator_token = self.match(TokenKind.LOGICAL_NOT, TokenKind.MINUS)
        if operator_token is not None:
            operand = self.parse_unary()
            if operator_token.kind is TokenKind.LOGICAL_NOT:
                return UnaryExpr(UnaryOperator.NOT, operand, span=self._span(operator_token, operand))
            else:
                return UnaryExpr(UnaryOperator.NEGATE, operand, span=self._span(operator_token, operand))
        return self.parse_primary()

    def parse_primary(self) -> Expr:
        if self.check(TokenKind.LEFT_PAREN):
            start = self.expect(TokenKind.LEFT_PAREN)
            expr = self.parse_expression()
            end = self.expect(TokenKind.RIGHT_PAREN)
            expr.span = self._span(start, end)
            return expr
        elif self.check(TokenKind.IDENTIFIER):
            start = self.advance() #consome o token IDENTIFIER
            if self.check(TokenKind.LEFT_PAREN):
                self.advance() #consome o token LEFT_PAREN
                arguments = self.parse_arguments()
                end = self.expect(TokenKind.RIGHT_PAREN)
                return CallExpr(start.lexeme, arguments, span=self._span(start, end))
            else:
                return IdentifierExpr(start.lexeme, span=self._token_span(start))
        elif self.check(TokenKind.INT_LITERAL):
            start = self.advance()
            return IntLiteral(start.value, span=self._token_span(start))
        elif self.check(TokenKind.KW_TRUE):
            start = self.advance()
            return BoolLiteral(start.value, span=self._token_span(start))
        elif self.check(TokenKind.KW_FALSE):
            start = self.advance()
            return BoolLiteral(start.value, span=self._token_span(start))
        else:
            #self.peek() token que deu problema, a segunda parte é o conjunto de tokens que eram esperados
            raise ParserError(self.peek(), {TokenKind.LEFT_PAREN, TokenKind.IDENTIFIER, TokenKind.INT_LITERAL, TokenKind.KW_TRUE, TokenKind.KW_FALSE}) 

    def parse_arguments(self) -> list[Expr]:
        arguments = []
        if self.check(TokenKind.RIGHT_PAREN):
            return arguments
        arguments.append(self.parse_expression())
        while self.match(TokenKind.COMMA):
            arguments.append(self.parse_expression())
        return arguments