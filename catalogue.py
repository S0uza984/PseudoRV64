"""Ponto de implementação das regras declarativas do enunciado."""

from patterns import *
from ast_nodes import *

def catalogue():
    R=[]
    def add(name, result, kind, op=None, kids=(), pred=None, cost=1, action=None):
        R.append(Rule(name,result,Pattern(kind,op,kids,pred),cost,action or name))
    add("literal_reg",REG,(IntLiteral,BoolLiteral) if False else IntLiteral,cost=1)
    add("bool_reg",REG,BoolLiteral,cost=1)
    add("identifier_reg",REG,IdentifierExpr,cost=0)
    add("literal_imm12",IMM12,IntLiteral,pred=imm12,cost=0)
    add("literal_pow2",POW2,IntLiteral,pred=pow2,cost=0)
    add("negative_imm12",IMM12,UnaryExpr,pred=imm12,cost=0)
    add("negative_pow2",POW2,UnaryExpr,pred=pow2,cost=0)
    add("negate",REG,UnaryExpr,UnaryOperator.NEGATE,(Need(REG),),cost=1)
    add("not_reg",REG,UnaryExpr,UnaryOperator.NOT,(Need(REG),),cost=1)
    add("not_cond",COND,UnaryExpr,UnaryOperator.NOT,(Need(COND),),cost=0)
    arithmetic={BinaryOperator.ADD:"Add",BinaryOperator.SUBTRACT:"Sub",BinaryOperator.MULTIPLY:"Mul",BinaryOperator.DIVIDE:"Div",BinaryOperator.REMAINDER:"Rem"}
    for op,ins in arithmetic.items():
        add("arith_"+ins.lower(),REG,BinaryExpr,op,(Need(REG),Need(REG)),cost=1)
    add("add_imm_right",REG,BinaryExpr,BinaryOperator.ADD,(Need(REG),Need(IMM12)),cost=1)
    add("add_imm_left",REG,BinaryExpr,BinaryOperator.ADD,(Need(IMM12),Need(REG)),cost=1)
    R.append(Rule("sub_imm",REG,Pattern(BinaryExpr,BinaryOperator.SUBTRACT,(Need(REG),)),1,"sub_imm"))
    for side in (0,1):
        kids=(Need(POW2),Need(REG)) if side==0 else (Need(REG),Need(POW2))
        add("mul_pow2_"+str(side),REG,BinaryExpr,BinaryOperator.MULTIPLY,kids,cost=1)
    for op in (BinaryOperator.LESS,BinaryOperator.GREATER):
        add("compare_"+op.name.lower(),REG,BinaryExpr,op,(Need(REG),Need(REG)),cost=1)
    for op in (BinaryOperator.LESS_EQUAL,BinaryOperator.GREATER_EQUAL):
        add("compare_"+op.name.lower(),REG,BinaryExpr,op,(Need(REG),Need(REG)),cost=2)
    for op in (BinaryOperator.EQUAL,BinaryOperator.NOT_EQUAL):
        add("compare_"+op.name.lower(),REG,BinaryExpr,op,(Need(REG),Need(REG)),cost=2)
    for op in (BinaryOperator.LESS,BinaryOperator.LESS_EQUAL,BinaryOperator.GREATER,BinaryOperator.GREATER_EQUAL,BinaryOperator.EQUAL,BinaryOperator.NOT_EQUAL):
        add("compare_cond_"+op.name.lower(),COND,BinaryExpr,op,(Need(REG),Need(REG)),cost=2)
    for op in (BinaryOperator.LOGICAL_AND,BinaryOperator.LOGICAL_OR):
        add("logical_cond_"+op.name.lower(),COND,BinaryExpr,op,(Need(COND),Need(COND)),cost=0)
        add("logical_reg_"+op.name.lower(),REG,BinaryExpr,op,(Need(COND),Need(COND)),cost=3)
    add("bool_cond",COND,BoolLiteral,cost=1)
    add("identifier_cond",COND,IdentifierExpr,cost=2)
    add("call_reg",REG,CallExpr,kids=(Args(REG),),cost=1)
    add("call_effect",EFFECT,CallExpr,kids=(Args(REG),),cost=1)
    add("call_cond",COND,CallExpr,kids=(Args(REG),),cost=3)
    return R
