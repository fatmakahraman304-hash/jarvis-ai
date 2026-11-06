"""Bounded symbolic mathematics, numeric result checks and linear optimization."""
import ast
import json
import math
from ..tools import S, _schema


def _expr(text, symbols):
    import sympy as sp
    if not isinstance(text,str) or len(text)>1000:
        raise ValueError('İfade en fazla 1000 karakter olabilir.')
    tree=ast.parse(text.replace('^','**'),mode='eval')
    nodes=list(ast.walk(tree))
    if len(nodes)>150: raise ValueError('İfade çok karmaşık.')
    funcs={k:getattr(sp,k) for k in ['sin','cos','tan','sqrt','exp','log','Abs']}
    def visit(n):
        if isinstance(n,ast.Expression): return visit(n.body)
        if isinstance(n,ast.Constant) and type(n.value) in (int,float) and math.isfinite(n.value) and abs(n.value)<=1e12:
            return sp.Rational(str(n.value))
        if isinstance(n,ast.Name):
            if n.id in symbols:return symbols[n.id]
            if n.id=='pi':return sp.pi
            if n.id=='E':return sp.E
        if isinstance(n,ast.UnaryOp) and isinstance(n.op,(ast.UAdd,ast.USub)):
            return visit(n.operand) * (-1 if isinstance(n.op,ast.USub) else 1)
        if isinstance(n,ast.BinOp):
            a,b=visit(n.left),visit(n.right)
            if isinstance(n.op,ast.Add):return a+b
            if isinstance(n.op,ast.Sub):return a-b
            if isinstance(n.op,ast.Mult):return a*b
            if isinstance(n.op,ast.Div):return a/b
            if isinstance(n.op,ast.Pow) and b.is_number and abs(float(b))<=100:return a**b
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id in funcs and len(n.args)==1 and not n.keywords:
            return funcs[n.func.id](visit(n.args[0]))
        raise ValueError('Yalnızca matematik işlemleri ve izinli fonksiyonlar kullanılabilir.')
    return visit(tree)


def math_solve(equations, variables='x'):
    import sympy as sp
    names=[x.strip() for x in variables.split(',')]
    if not 1<=len(names)<=8 or any(not x.isidentifier() or x.startswith('_') or x in ('pi','E') for x in names):raise ValueError('1–8 geçerli değişken adı gerekli.')
    syms={n:sp.Symbol(n,real=True) for n in names}
    lines=[s.strip() for s in equations.replace(';','\n').splitlines() if s.strip()]
    if not 1<=len(lines)<=8:raise ValueError('1–8 denklem gerekli.')
    exprs=[]
    for line in lines:
        sides=line.split('=')
        if len(sides)>2:raise ValueError('Her denklemde en fazla bir = olabilir.')
        exprs.append(_expr(sides[0],syms)-_expr(sides[1],syms) if len(sides)==2 else _expr(line,syms))
    answers=sp.solve(exprs,list(syms.values()),dict=True)
    return {'solutions':[{str(k):str(v) for k,v in answer.items()} for answer in answers],
            'residuals':[[str(sp.simplify(e.subs(answer))) for e in exprs] for answer in answers],
            'note':'Gerçek değişkenler üzerinde çözüm; boş liste çözüm yok veya çözücü sınırı olabilir.'}


def math_verify(expression, values='{}', expected='0', tolerance=1e-8):
    import sympy as sp
    values=json.loads(values) if isinstance(values,str) else values
    if not isinstance(values,dict) or len(values)>20:raise ValueError('En fazla 20 değişken.')
    syms={n:sp.Symbol(n) for n in values}
    if any(not n.isidentifier() or n.startswith('_') for n in syms):raise ValueError('Geçersiz değişken.')
    substitutions={syms[n]:_expr(str(v),{}) for n,v in values.items()}
    actual=_expr(expression,syms).subs(substitutions)
    target=_expr(str(expected),{})
    residual=float(sp.N(actual-target,30))
    tol=float(tolerance)
    if not math.isfinite(residual) or not math.isfinite(tol) or not 0<tol<=1:raise ValueError('Sonlu değer ve 0–1 tolerans gerekli.')
    return {'value':str(sp.N(actual,20)),'expected':str(target),'residual':residual,'verified':abs(residual)<=tol,
            'scope':'Sayısal yerine koyma kontrolüdür; fiziksel model veya mühendislik standardı doğrulaması değildir.'}


def linear_optimize(problem):
    from scipy.optimize import linprog
    p=json.loads(problem) if isinstance(problem,str) else problem
    c=p['c']
    if not isinstance(c,list) or not 1<=len(c)<=50:raise ValueError('1–50 amaç katsayısı gerekli.')
    for key in ('A_ub','A_eq'):
        rows=p.get(key)
        if rows is not None and (len(rows)>100 or any(len(row)!=len(c) for row in rows)):raise ValueError('Matris boyutu geçersiz.')
    result=linprog(c,A_ub=p.get('A_ub'),b_ub=p.get('b_ub'),A_eq=p.get('A_eq'),b_eq=p.get('b_eq'),bounds=p.get('bounds',(0,None)),method='highs',options={'time_limit':10})
    return {'success':bool(result.success),'message':str(result.message),'x':result.x.tolist() if result.x is not None else None,'objective':float(result.fun) if result.fun is not None else None}


TOOLS={
 'math_solve':(math_solve,_schema('Sembolik denklem/sistem çözer; çözümü denkleme geri koyarak kalanı gösterir. ^ üs; denklemler ; veya yeni satırla ayrılır.',{'equations':S('denklemler'),'variables':S('virgülle değişkenler')},['equations']),False),
 'math_verify':(math_verify,_schema('Verilen sonucun sayısal yerine koyma kontrolünü yapar. Fiziksel model doğruluğunu kanıtlamaz.',{'expression':S('ifade'),'values':S('değişken JSON sözlüğü'),'expected':S('beklenen sonuç'),'tolerance':{'type':'number'}},['expression']),False),
 'linear_optimize':(linear_optimize,_schema('Doğrusal kısıtlar altında minimizasyon (SciPy HiGHS). JSON: c,A_ub,b_ub,A_eq,b_eq,bounds.',{'problem':S('problem JSON')},['problem']),False),
}
