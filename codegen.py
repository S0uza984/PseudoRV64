"""Pontos de implementação da geração de comandos e expressões."""

import load_previous
from ast_nodes import *
import ir as I
from ir import Context, ProgramIR, FunctionIR
from catalogue import catalogue
from selector import Selector
from patterns import REG, COND, EFFECT
from patterns import signed_literal, pow2

class CodeGenerator:
    """Coordene comandos ad hoc e seleção de expressões com DP."""

    def __init__(self):
        self.program_ir=None
        self.context=None
        self.selector=None
        self.table=None    
    
    def generate(self, program):
        out=ProgramIR()
        # Estado interno reiniciado para permitir reutilização do gerador.
        self.program_ir=out
        for decl in program.functions:
            symbol=decl.metadata["symbol"]
            fn=FunctionIR(symbol)
            out.functions.append(fn)
            self.context=Context(fn,out)
            for index,param in enumerate(decl.parameters):
                dst=self.context.variable(param.metadata["symbol"])
                self.context.emit(I.Param(dst,index,origin=param.span))
            self.statement(decl.body)
            if decl.return_type is TypeName.VOID:
                # Um retorno adicional inalcançável é válido e garante saída normal.
                self.context.emit(I.Return(None,origin=decl.body.span))
        return out

    def expression(self, node, result_class, true_label=None, false_label=None):
        self.table=Selector(catalogue()).analyze(node)
        choice=self.table.lookup(node,result_class)
        if choice is None:
            span=node.span
            raise ValueError(f"expressão sem cobertura {result_class.value} em {span.start_line}:{span.start_column}")
        return self._emit_expr(node,result_class,true_label,false_label)

    def _emit_expr(self,node,cls,t=None,f=None):
        import ir as I
        from ast_nodes import BinaryOperator as B, UnaryOperator as U
        ch=self.table.lookup(node,cls)
        rule=ch.rule.name
        sub=ch.subproblems
        def subexpr(i, c=None, tt=None, ff=None):
            n,rc=sub[i]
            return self._emit_expr(n,c or rc,tt,ff)
        o=node.span
        if rule in ("literal_reg","bool_reg"):
            v=self.context.temp()
            value=int(node.value) if isinstance(node.value,bool) else node.value
            self.context.emit(I.Li(v,value,origin=o)); return v
        if rule=="identifier_reg":
            return self.context.variable(node.metadata["symbol"])
        if rule in ("literal_imm12","literal_pow2","negative_imm12","negative_pow2"):
            return None
        if rule=="negate":
            a=subexpr(0); d=self.context.temp(); self.context.emit(I.Neg(d,a,origin=o)); return d
        if rule=="not_reg":
            a=subexpr(0); d=self.context.temp(); self.context.emit(I.Seqz(d,a,origin=o)); return d
        if rule=="not_cond":
            return self._emit_expr(node.operand,COND,f,t)
        if rule.startswith("arith_"):
            a=subexpr(0); b=subexpr(1); d=self.context.temp()
            ins={"add":I.Add,"sub":I.Sub,"mul":I.Mul,"div":I.Div,"rem":I.Rem}[rule[6:]]
            self.context.emit(ins(d,a,b,origin=o)); return d
        if rule in ("add_imm_right","add_imm_left"):
            if rule.endswith("right"):
                a=subexpr(0); imm=signed_literal(node.right)
            else:
                a=subexpr(1); imm=signed_literal(node.left)
            d=self.context.temp(); self.context.emit(I.Addi(d,a,imm,origin=o)); return d
        if rule=="sub_imm":
            a=self._emit_expr(node.left,REG); imm=-signed_literal(node.right)
            d=self.context.temp(); self.context.emit(I.Addi(d,a,imm,origin=o)); return d
        if rule.startswith("mul_pow2_"):
            if rule.endswith("0"):
                immnode=node.left; a=subexpr(1)
            else:
                a=subexpr(0); immnode=node.right
            n=signed_literal(immnode); shift=n.bit_length()-1
            d=self.context.temp(); self.context.emit(I.Slli(d,a,shift,origin=o)); return d
        if rule.startswith("compare_") and cls==REG:
            a=subexpr(0); b=subexpr(1); d=self.context.temp()
            op=node.operator
            if op is B.LESS: self.context.emit(I.Slt(d,a,b,origin=o))
            elif op is B.GREATER: self.context.emit(I.Slt(d,b,a,origin=o))
            elif op in (B.LESS_EQUAL,B.GREATER_EQUAL):
                self.context.emit(I.Slt(d,b,a,origin=o) if op is B.LESS_EQUAL else I.Slt(d,a,b,origin=o))
                self.context.emit(I.Seqz(d,d,origin=o))
            else:
                tmp=self.context.temp(); self.context.emit(I.Xor(tmp,a,b,origin=o))
                (self.context.emit(I.Seqz(d,tmp,origin=o)) if op is B.EQUAL else self.context.emit(I.Snez(d,tmp,origin=o)))
            return d
        if rule.startswith("compare_cond_"):
            a=subexpr(0); b=subexpr(1)
            op=node.operator
            if op is B.LESS:
                self.context.emit(I.Blt(a,b,t,origin=o)); self.context.emit(I.Jump(f,origin=o))
            elif op is B.GREATER:
                self.context.emit(I.Blt(b,a,t,origin=o)); self.context.emit(I.Jump(f,origin=o))
            elif op is B.LESS_EQUAL:
                self.context.emit(I.Blt(b,a,f,origin=o)); self.context.emit(I.Jump(t,origin=o))
            elif op is B.GREATER_EQUAL:
                self.context.emit(I.Blt(a,b,f,origin=o)); self.context.emit(I.Jump(t,origin=o))
            elif op is B.EQUAL:
                self.context.emit(I.Beq(a,b,t,origin=o)); self.context.emit(I.Jump(f,origin=o))
            else:
                self.context.emit(I.Bne(a,b,t,origin=o)); self.context.emit(I.Jump(f,origin=o))
            return None
        if rule=="bool_cond":
            self.context.emit(I.Jump(t if node.value else f,origin=o)); return None
        if rule=="identifier_cond":
            a=self.context.variable(node.metadata["symbol"])
            self.context.emit(I.Bnez(a,t,origin=o)); self.context.emit(I.Jump(f,origin=o)); return None
        if rule=="call_reg" or rule=="call_effect" or rule=="call_cond":
            args=[self._emit_expr(a,REG) for a in node.arguments]
            sym=node.metadata["symbol"]
            dst=None if cls==EFFECT else self.context.temp()
            self.context.emit(I.Call(dst,sym,args,origin=o))
            if cls==COND:
                self.context.emit(I.Bnez(dst,t,origin=o)); self.context.emit(I.Jump(f,origin=o))
            return dst
        if rule.startswith("logical_cond_"):
            mid=self.context.label()
            if node.operator is B.LOGICAL_AND:
                self._emit_expr(node.left,COND,mid,f)
                self.context.emit(I.LabelInstr(mid))
                self._emit_expr(node.right,COND,t,f)
            else:
                self._emit_expr(node.left,COND,t,mid)
                self.context.emit(I.LabelInstr(mid))
                self._emit_expr(node.right,COND,t,f)
            return None
        if rule.startswith("logical_reg_"):
            yes,no,end=self.context.label(),self.context.label(),self.context.label()
            self._emit_expr(node,COND,yes,no)
            d=self.context.temp()
            self.context.emit(I.LabelInstr(yes)); self.context.emit(I.Li(d,1,origin=o)); self.context.emit(I.Jump(end,origin=o))
            self.context.emit(I.LabelInstr(no)); self.context.emit(I.Li(d,0,origin=o))
            self.context.emit(I.LabelInstr(end)); return d
        raise ValueError("regra de expressão não implementada: "+rule)

    def statement(self, node):
        import ir as I
        if isinstance(node,Block):
            for s in node.statements: self.statement(s)
        elif isinstance(node,VarDecl):
            if node.initializer is not None:
                value=self.expression(node.initializer,REG)
                dst=self.context.variable(node.metadata["symbol"])
                self.context.emit(I.Move(dst,value,origin=node.span))
        elif isinstance(node,Assignment):
            value=self.expression(node.value,REG)
            dst=self.context.variable(node.target.metadata["symbol"])
            self.context.emit(I.Move(dst,value,origin=node.span))
        elif isinstance(node,CallStmt):
            self.expression(node.call,EFFECT)
        elif isinstance(node,IfStmt):
            yes,no,end=self.context.label(),self.context.label(),self.context.label()
            self.expression(node.condition,COND,yes,no)
            self.context.emit(I.LabelInstr(yes)); self.statement(node.then_block); self.context.emit(I.Jump(end))
            self.context.emit(I.LabelInstr(no))
            if node.else_block is not None: self.statement(node.else_block)
            self.context.emit(I.LabelInstr(end))
        elif isinstance(node,WhileStmt):
            test,body,end=self.context.label(),self.context.label(),self.context.label()
            self.context.emit(I.LabelInstr(test))
            self.expression(node.condition,COND,body,end)
            self.context.emit(I.LabelInstr(body)); self.statement(node.body)
            self.context.emit(I.Jump(test)); self.context.emit(I.LabelInstr(end))
        elif isinstance(node,ReturnStmt):
            value=None if node.value is None else self.expression(node.value,REG)
            self.context.emit(I.Return(value,origin=node.span))
        elif isinstance(node,PrintStmt):
            newline=self.context.string("\n")
            for item in node.items:
                if isinstance(item,StringLiteral):
                    self.context.emit(I.PrintString(self.context.string(item.value),origin=item.span))
                else:
                    value=self.expression(item,REG)
                    typ=item.metadata["type"]
                    self.context.emit(I.PrintBool(value,origin=item.span) if typ is TypeName.BOOL else I.PrintInt(value,origin=item.span))
            self.context.emit(I.PrintString(newline,origin=node.span))
