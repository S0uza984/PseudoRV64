"""Alcance no CFG. O percurso da AST já foi realizado pelo builder."""

from __future__ import annotations

from cfg import BlockId, CFG


def compute_reachable(cfg: CFG) -> set[BlockId]:
    """Devolva os IDs alcançáveis a partir da entrada, incluindo a entrada."""
    # Percorra o grafo do CFG, ignorando os blocos que não são alcançáveis (DFS).
    reachable: set[BlockId] = set()
    pending = [cfg.entry]
    while pending:
        current = pending.pop()
        if current in reachable:
            continue
        reachable.add(current)
        for successor in cfg.blocks[current].successors:
            if successor not in reachable:
                pending.append(successor)
    return reachable
