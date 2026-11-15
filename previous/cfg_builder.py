"""Construa um CFG auxiliar por função, preservando os nós da AST."""

from __future__ import annotations

import load_previous  # Disponibiliza os módulos das etapas anteriores.

from ast_nodes import (
    Assignment, Block, BoolLiteral, CallStmt, FunctionDecl, IfStmt, PrintStmt,
    ReturnStmt, Stmt, VarDecl, WhileStmt,
)
from cfg import BlockId, Branch, CFG, Jump, Return, ScopeExit


class CFGBuilder:
    def build(self, function: FunctionDecl) -> CFG:
        self.cfg = CFG(function)
        body_entry = self.cfg.new_block()
        self.cfg.terminate(self.cfg.entry, Jump(body_entry.id))
        continuation = self._build_block(function.body, body_entry.id)
        if continuation is not None:
            self.cfg.terminate(continuation, Jump(self.cfg.fallthrough_exit))
        return self.cfg

    def _build_block(self, block: Block, current: BlockId) -> BlockId | None:
        """Percorra um bloco da AST e devolva sua continuação normal.

        `current` identifica um bloco básico aberto. Comandos sequenciais
        permanecem nele. Comandos de controle podem mudar a continuação.
        None indica que os caminhos deste bloco não alcançam o próximo comando.
        """

        for statement in block.statements:
            current = self._build_statement(statement, current)
            # Nenhum caminho continua: os comandos restantes são inalcançáveis.
            if current is None:
                return None
        # Fim normal do bloco: os locais deste escopo deixam de existir.
        self.cfg.blocks[current].operations.append(ScopeExit(block.metadata["scope"]))
        return current

    def _build_statement(self, statement: Stmt, current: BlockId) -> BlockId | None:
        """Incorpore um comando ao CFG e devolva sua continuação normal."""

        if isinstance(statement, (VarDecl, Assignment, PrintStmt, CallStmt)):
            # Comandos sequenciais ficam no bloco aberto.
            self.cfg.blocks[current].operations.append(statement)
            return current
        if isinstance(statement, ReturnStmt):
            # O retorno fecha o bloco e não há próximo comando.
            self.cfg.terminate(current, Return(statement))
            return None
        if isinstance(statement, Block):
            # Chaves aninhadas não exigem um novo bloco básico.
            return self._build_block(statement, current)
        if isinstance(statement, IfStmt):
            return self._build_if(statement, current)
        if isinstance(statement, WhileStmt):
            return self._build_while(statement, current)
        raise TypeError(f"comando desconhecido: {type(statement).__name__}")

    def _build_if(self, statement: IfStmt, current: BlockId) -> BlockId | None:
        """Construa o fluxo da condicional e devolva sua continuação."""

        then_start = self.cfg.new_block().id
        then_end = self._build_block(statement.then_block, then_start)

        if statement.else_block is not None:
            else_start = self.cfg.new_block().id
            else_end = self._build_block(statement.else_block, else_start)
        else:
            else_start = None
            else_end = None

        # Sem else, o caminho falso continua direto após o if.
        if then_end is None and statement.else_block is not None and else_end is None:
            # Os dois ramos se encerram: não há continuação nem junção.
            self.cfg.terminate(current, Branch(statement.condition, then_start, else_start))
            return None

        join = self.cfg.new_block().id
        false_target = else_start if else_start is not None else join
        self.cfg.terminate(current, Branch(statement.condition, then_start, false_target))
        # Somente ramos que continuam são ligados à junção.
        if then_end is not None:
            self.cfg.terminate(then_end, Jump(join))
        if else_end is not None:
            self.cfg.terminate(else_end, Jump(join))
        return join

    def _build_while(self, statement: WhileStmt, current: BlockId) -> BlockId | None:
        """Construa o fluxo do laço e devolva sua continuação."""

        # O teste fica em um bloco próprio, pois é o destino da volta do laço.
        header = self.cfg.new_block().id
        self.cfg.terminate(current, Jump(header))

        body_start = self.cfg.new_block().id
        body_end = self._build_block(statement.body, body_start)
        if body_end is not None:
            self.cfg.terminate(body_end, Jump(header))

        condition = statement.condition
        if isinstance(condition, BoolLiteral) and condition.value is True:
            # while (true): somente o literal não possui saída normal.
            self.cfg.terminate(header, Jump(body_start))
            return None

        # Laços comuns mantêm o caminho de zero iterações.
        exit_block = self.cfg.new_block().id
        self.cfg.terminate(header, Branch(condition, body_start, exit_block))
        return exit_block
