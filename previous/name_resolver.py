from __future__ import annotations

from ast_nodes import (
    Assignment,
    BinaryExpr,
    Block,
    CallExpr,
    CallStmt,
    Expr,
    IdentifierExpr,
    IfStmt,
    Node,
    PrintStmt,
    Program,
    ReturnStmt,
    Stmt,
    TypeName,
    UnaryExpr,
    VarDecl,
    WhileStmt,
)
from semantic_errors import SemanticDiagnostic, SemanticError, SemanticErrorKind
from symbols import FunctionSymbol, Scope, Symbol, SymbolKind


def resolve_names(program: Program) -> None:
    """Construa escopos, símbolos e vínculos entre usos e declarações."""

    functions: dict[str, FunctionSymbol] = {}
    diagnostics: list[SemanticDiagnostic] = []

    # 1. Colete todas as assinaturas de função.
    for function in program.functions:
        if function.name in functions:
            diagnostics.append(SemanticDiagnostic(
                SemanticErrorKind.DUPLICATE_FUNCTION,
                f"função '{function.name}' já declarada",
                function.span,
            ))
            continue

        functions[function.name] = FunctionSymbol(
            name=function.name,
            kind=SymbolKind.FUNCTION,
            type=function.return_type,
            declaration=function,
            parameter_types=tuple(param.type for param in function.parameters),
        )

    # 2. Valide a existência e a assinatura de main.
    main = functions.get("main")
    if main is None:
        diagnostics.append(SemanticDiagnostic(
            SemanticErrorKind.INVALID_MAIN,
            "programa não declara a função 'main'",
            program.span,
        ))
    elif main.type is not TypeName.INT or main.parameter_types:
        diagnostics.append(SemanticDiagnostic(
            SemanticErrorKind.INVALID_MAIN,
            "a função 'main' deve ter a assinatura 'int main()'",
            main.declaration.span,
        ))

    # 3. Percorra os corpos em ordem, criando um escopo para cada bloco.
    def declare(scope: Scope, symbol: Symbol, node: Node) -> None:
        # 4. Anote declarações, usos e blocos na AST.
        node.metadata["symbol"] = symbol

        if symbol.name in scope.symbols:
            diagnostics.append(SemanticDiagnostic(
                SemanticErrorKind.DUPLICATE_DECLARATION,
                f"'{symbol.name}' já declarado neste escopo",
                node.span,
            ))
            return
        scope.symbols[symbol.name] = symbol

    def lookup(scope: Scope | None, name: str) -> Symbol | None:
        while scope is not None:
            if name in scope.symbols:
                return scope.symbols[name]
            scope = scope.parent
        return None

    def resolve_block(block: Block, scope: Scope) -> None:
        # 4. Anote declarações, usos e blocos na AST.
        block.metadata["scope"] = scope

        for statement in block.statements:
            resolve_statement(statement, scope)

    def resolve_statement(statement: Stmt, scope: Scope) -> None:
        if isinstance(statement, Block):
            resolve_block(statement, Scope(parent=scope))
        elif isinstance(statement, VarDecl):
            declare(scope, Symbol(
                name=statement.name,
                kind=SymbolKind.VARIABLE,
                type=statement.type,
                declaration=statement,
            ), statement)
            if statement.initializer is not None:
                resolve_expression(statement.initializer, scope)
        elif isinstance(statement, Assignment):
            resolve_expression(statement.target, scope)
            resolve_expression(statement.value, scope)
        elif isinstance(statement, CallStmt):
            resolve_expression(statement.call, scope)
        elif isinstance(statement, IfStmt):
            resolve_expression(statement.condition, scope)
            resolve_statement(statement.then_block, scope)
            if statement.else_block is not None:
                resolve_statement(statement.else_block, scope)
        elif isinstance(statement, WhileStmt):
            resolve_expression(statement.condition, scope)
            resolve_statement(statement.body, scope)
        elif isinstance(statement, ReturnStmt):
            if statement.value is not None:
                resolve_expression(statement.value, scope)
        elif isinstance(statement, PrintStmt):
            for item in statement.items:
                if isinstance(item, Expr):
                    resolve_expression(item, scope)

    def resolve_expression(expression: Expr, scope: Scope) -> None:
        if isinstance(expression, IdentifierExpr):
            variable = lookup(scope, expression.name)
            if variable is None:
                diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.UNDECLARED_VARIABLE,
                    f"variável '{expression.name}' não declarada",
                    expression.span,
                ))
            else:
                # 4. Anote declarações, usos e blocos na AST.
                expression.metadata["symbol"] = variable
        elif isinstance(expression, CallExpr):
            callee = functions.get(expression.name)
            if callee is None:
                diagnostics.append(SemanticDiagnostic(
                    SemanticErrorKind.UNDECLARED_FUNCTION,
                    f"função '{expression.name}' não declarada",
                    expression.span,
                ))
            else:
                # 4. Anote declarações, usos e blocos na AST.
                expression.metadata["symbol"] = callee
            for argument in expression.arguments:
                resolve_expression(argument, scope)
        elif isinstance(expression, UnaryExpr):
            resolve_expression(expression.operand, scope)
        elif isinstance(expression, BinaryExpr):
            resolve_expression(expression.left, scope)
            resolve_expression(expression.right, scope)

    for function in program.functions:
        # 4. Anote declarações, usos e blocos na AST.
        if functions[function.name].declaration is function:
            function.metadata["symbol"] = functions[function.name]

        function_scope = Scope(parent=None)
        for param in function.parameters:
            declare(function_scope, Symbol(
                name=param.name,
                kind=SymbolKind.PARAMETER,
                type=param.type,
                declaration=param,
            ), param)
        resolve_block(function.body, function_scope)

    # 5. Acumule os diagnósticos desta passagem antes de lançar SemanticError.
    if diagnostics:
        raise SemanticError(diagnostics)
