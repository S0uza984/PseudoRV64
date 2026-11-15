"""Ponto de implementação do reconhecimento de padrões e custos mínimos."""

from patterns import *


class Selector:
    """Selecione coberturas sem executar expressões ou emitir instruções."""

    def __init__(self, rules):
        self.rules = tuple(rules)

    def _match(self, node, pattern):
        if pattern.kind is not None and not isinstance(node, pattern.kind): return None
        if pattern.operator is not None and getattr(node, "operator", None) is not pattern.operator: return None
        if pattern.predicate is not None:
            if not pattern.predicate(node): return None
            if not pattern.children: return ()
        kids = children(node)
        variadic = len(pattern.children) == 1 and isinstance(pattern.children[0], Args)
        if not variadic and len(kids) != len(pattern.children): return None
        needs=[]
        if variadic:
            spec=pattern.children[0]
            if not isinstance(node, CallExpr): return None
            return tuple((arg,spec.result) for arg in node.arguments)
        for child, spec in zip(kids, pattern.children):
            if isinstance(spec, Need): needs.append((child,spec.result))
            elif isinstance(spec, Args):
                if not isinstance(node, CallExpr): return None
                needs.extend((arg,spec.result) for arg in node.arguments)
            elif isinstance(spec, Pattern):
                if self._match(child,spec) is None: return None
            else: return None
        return tuple(needs)    
    
    def analyze(self, expr):
        table=SelectionTable()
        seen=set()
        def visit(node):
            if id(node) in seen: return
            seen.add(id(node))
            for child in children(node): visit(child)
            for rule in self.rules:
                from ast_nodes import BinaryExpr, BinaryOperator
                if rule.name == "sub_imm":
                    subs = ((node.left, REG),) if isinstance(node, BinaryExpr) and node.operator is BinaryOperator.SUBTRACT and neg_imm12(node.right) else None
                else:
                    subs=self._match(node,rule.pattern)
                if subs is None: continue
                cost=rule.cost
                valid=True
                for child, cls in subs:
                    choice=table.lookup(child,cls)
                    if choice is None: valid=False; break
                    cost += choice.cost
                if valid:
                    old=table.lookup(node,rule.result)
                    if old is None or cost < old.cost:
                        table.put(node,rule.result,Choice(cost,rule,subs))
        visit(expr)
        return table
