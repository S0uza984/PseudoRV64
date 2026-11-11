from __future__ import annotations

from ast_nodes import (Program, Assignment, BinaryExpr, BinaryOperator, Block, BoolLiteral, CallExpr, CallStmt, Expr, FunctionDecl, 
                       IdentifierExpr, IfStmt, IntLiteral, PrintStmt, ReturnStmt, StringLiteral, TypeName, UnaryExpr, UnaryOperator, VarDecl, WhileStmt)

from semantic_errors import SemanticErrorKind, SemanticDiagnostic, SemanticError

_UNKNOWN = object()

def check_types(program: Program) -> None:
    """Determine tipos de expressões e valide seus contextos."""

    diagnostics: list[SemanticDiagnostic] = []

    for function in program.functions:
        checker = _TypeChecker(function, diagnostics)
        checker.visit_block(function.body)

    if diagnostics:
        raise SemanticError(diagnostics)


class _TypeChecker:
    def __init__(self, function: FunctionDecl, diagnostics):
        self.function = function
        self.diagnostics = diagnostics

    def visit_block(self, block: Block) -> None:
        if block is self.function.body:
            for parameter in self.function.parameters:
                if parameter.type is TypeName.VOID:
                    self.error(SemanticErrorKind.VOID_PARAMETER, parameter, f"parametro {parameter.name!r} nao pode ter tipo void", )        
        
        for statement in block.statements:
            self.visit_stmt(statement)

    def visit_stmt(self, stmt) -> None:
        if isinstance(stmt, VarDecl):
            if stmt.type is TypeName.VOID:
                self.error(SemanticErrorKind.VOID_VARIABLE, stmt, f"variavel {stmt.name!r} nao pode ter tipo void")
            if stmt.initializer is not None:
                actual = self.visit_expr(stmt.initializer)
                if actual is not _UNKNOWN and stmt.type is not TypeName.VOID and actual is not stmt.type:
                    self.error(SemanticErrorKind.INITIALIZER_TYPE_MISMATCH, stmt.initializer, f"inicializador tem tipo {actual.value}, esperado {stmt.type.value}")
            return

        if isinstance(stmt, Assignment):
            target_type = self.visit_expr(stmt.target)
            value_type = self.visit_expr(stmt.value)
            if target_type is not _UNKNOWN and value_type is not _UNKNOWN and target_type is not value_type:
                self.error(SemanticErrorKind.ASSIGNMENT_TYPE_MISMATCH, stmt.value, f"atribuicao incompativel: esperado {target_type.value}, encontrado {value_type.value}")
            return

        if isinstance(stmt, CallStmt):
            self.visit_call(stmt.call, as_value=False)
            return

        if isinstance(stmt, IfStmt):
            condition = self.visit_expr(stmt.condition)
            if condition is not _UNKNOWN and condition is not TypeName.BOOL:
                self.error(SemanticErrorKind.CONDITION_TYPE_MISMATCH, stmt.condition, "a condicao deve ter tipo bool")
            self.visit_block(stmt.then_block)
            if stmt.else_block is not None:
                self.visit_block(stmt.else_block)
            return

        if isinstance(stmt, WhileStmt):
            condition = self.visit_expr(stmt.condition)
            if condition is not _UNKNOWN and condition is not TypeName.BOOL:
                self.error(SemanticErrorKind.CONDITION_TYPE_MISMATCH, stmt.condition, "a condicao deve ter tipo bool")
            self.visit_block(stmt.body)
            return

        if isinstance(stmt, ReturnStmt):
            if stmt.value is None:
                if self.function.return_type is not TypeName.VOID:
                    self.error(SemanticErrorKind.RETURN_MISMATCH, stmt, "return sem valor em função nao-void")
            else:
                actual = self.visit_expr(stmt.value)
                if self.function.return_type is TypeName.VOID:
                    self.error(SemanticErrorKind.RETURN_MISMATCH, stmt.value, "funcao void nao pode retornar um valor")
                elif actual is not _UNKNOWN and actual is not self.function.return_type:
                    self.error(SemanticErrorKind.RETURN_MISMATCH, stmt.value, f"retorno incompativel: esperado {self.function.return_type.value}, encontrado {actual.value}")
            return

        if isinstance(stmt, PrintStmt):
            for item in stmt.items:
                if isinstance(item, Expr):
                    self.visit_expr(item) # StringLiteral já é um item válido.
            return

        if isinstance(stmt, Block):
            self.visit_block(stmt)
            return

    def visit_expr(self, expr: Expr):
        if isinstance(expr, IntLiteral):
            if not (0 <= expr.value <= 2**63 - 1):
                self.error(SemanticErrorKind.INTEGER_LITERAL_OUT_OF_RANGE, expr, "literal inteiro fora do intervalo permitido")
                return _UNKNOWN
            expr.metadata["type"] = TypeName.INT
            return TypeName.INT

        if isinstance(expr, BoolLiteral):
            expr.metadata["type"] = TypeName.BOOL
            return TypeName.BOOL

        if isinstance(expr, StringLiteral): # StringLiteral não é Expr na AST pública, portanto este ramo é apenas defensivo.
            return _UNKNOWN

        if isinstance(expr, IdentifierExpr):
            symbol = expr.metadata.get("symbol")
            if symbol is None:
                return _UNKNOWN
            expr.metadata["type"] = symbol.type
            return symbol.type

        if isinstance(expr, CallExpr):
            return self.visit_call(expr, as_value=True)

        if isinstance(expr, UnaryExpr):
            operand = self.visit_expr(expr.operand)
            if operand is _UNKNOWN:
                return _UNKNOWN
            if expr.operator is UnaryOperator.NEGATE:
                if operand is not TypeName.INT:
                    self.error(SemanticErrorKind.INVALID_UNARY_OPERAND, expr, "operador - exige operando int")
                    return _UNKNOWN
                expr.metadata["type"] = TypeName.INT
                return TypeName.INT
            if expr.operator is UnaryOperator.NOT:
                if operand is not TypeName.BOOL:
                    self.error(SemanticErrorKind.INVALID_UNARY_OPERAND, expr, "operador ! exige operando bool")
                    return _UNKNOWN
                expr.metadata["type"] = TypeName.BOOL
                return TypeName.BOOL

        if isinstance(expr, BinaryExpr):
            left = self.visit_expr(expr.left)
            right = self.visit_expr(expr.right)
            if left is _UNKNOWN or right is _UNKNOWN:
                return _UNKNOWN

            op = expr.operator
            if op in {BinaryOperator.ADD, BinaryOperator.SUBTRACT, BinaryOperator.MULTIPLY, BinaryOperator.DIVIDE, BinaryOperator.REMAINDER,}:
                valid = left is TypeName.INT and right is TypeName.INT
                result = TypeName.INT
            elif op in {BinaryOperator.LESS, BinaryOperator.LESS_EQUAL, BinaryOperator.GREATER, BinaryOperator.GREATER_EQUAL,}:
                valid = left is TypeName.INT and right is TypeName.INT
                result = TypeName.BOOL
            elif op in {BinaryOperator.EQUAL, BinaryOperator.NOT_EQUAL}:
                valid = left is right and left in {TypeName.INT, TypeName.BOOL}
                result = TypeName.BOOL
            elif op in {BinaryOperator.LOGICAL_AND, BinaryOperator.LOGICAL_OR}:
                valid = left is TypeName.BOOL and right is TypeName.BOOL
                result = TypeName.BOOL
            else:
                valid = False
                result = _UNKNOWN

            if not valid:
                self.error(SemanticErrorKind.INVALID_BINARY_OPERANDS, expr, "operandos incompativeis para o operador")
                return _UNKNOWN

            expr.metadata["type"] = result
            return result

        return _UNKNOWN

    def visit_call(self, call: CallExpr, *, as_value: bool):
        symbol = call.metadata.get("symbol")

        argument_types = [self.visit_expr(arg) for arg in call.arguments] # Sempre visite todos os argumentos, inclusive com aridade errada.

        if symbol is None:
            return _UNKNOWN

        expected = symbol.parameter_types
        if len(argument_types) != len(expected):
            self.error(SemanticErrorKind.ARITY_MISMATCH, call, f"esperados {len(expected)} argumentos, encontrados {len(argument_types)}")

        for index, (actual, wanted) in enumerate(zip(argument_types, expected)):
            if actual is not _UNKNOWN and actual is not wanted:
                self.error(SemanticErrorKind.ARGUMENT_TYPE_MISMATCH, call.arguments[index], f"argumento {index + 1}: esperado {wanted.value}, encontrado {actual.value}")

        result = symbol.type
        if as_value and result is TypeName.VOID:
            self.error(SemanticErrorKind.VOID_VALUE_USED, call, f"função {call.name!r} retorna void e nao pode ser usada como valor")
            return _UNKNOWN

        call.metadata["type"] = result
        return result

    def error(self, kind, node, message):
        self.diagnostics.append(SemanticDiagnostic(kind, message, node.span))
