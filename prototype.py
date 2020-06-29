from scipy.stats import gamma
from scipy.stats import norm
from scipy.stats import skewnorm

from enum import Enum

import math

MULT = lambda x, para : x * para
DIV = lambda x, para : x / para
ADD = lambda x, para : x + para
SUBT = lambda x, para : x - para
POW = lambda x, para : math.pow(x, para)
ROOT = lambda x, para : math.pow(x, 1 / para)
LOG = lambda x, para : math.log(x, para)

class Query(Enum):
    PDF = 1
    CDF = 2
    MEDN = 3
    MEAN = 4

class Curve:
    def __init__(self, distrib, *paras):
        self.distrib = distrib
        self.paras = list(paras)
        self.update = False

        self.children = []

        for para in paras:
            add_helper(para.children, self)

    def do_update(self):
        if self.update:
            self.update = False
            
            for para in self.paras:
                para.do_update()

        return self

    def do_query(self, query, x=None):
        funct = None
        
        if query == Query.PDF:
            return run_helper(self.do_update().distrib.pdf, self.paras, x)
        elif query == Query.CDF:
            return run_helper(self.do_update().distrib.cdf, self.paras, x)
        elif query == Query.MEDN:
            return run_helper(self.do_update().distrib.median, self.paras)
        elif query == Query.MEAN:
            return run_helper(self.do_update().distrib.mean, self.paras)

        return None
        
class Value:
    def __init__(
        self, base,
        functions=None, paras=None,
        functions_curve=None, paras_curve=None,
        curve=None, query=None
        ):
        self.base = base
        self.functions = functions
        self.paras = paras
        self.functions_curve = functions_curve
        self.paras_curve = paras_curve
        self.value = None
        self.curve = curve
        self.query = query
        self.update = True

        self.children = []

        if self.curve:
            add_helper(self.curve.children, self)
        if self.functions:
            for para in self.paras:
                add_helper(para.children, self)
        if self.functions_curve:
            for para in self.paras_curve:
                add_helper(para.children, self)

        self.do_update()

    def do_update(self):
        if self.update:
            self.update = False

            self.value = self.base

            if self.functions_curve:
                for i in range(len(self.functions_curve)):
                    self.value = self.functions_curve[i](self.value, self.paras_curve[i].do_update())
            if self.curve:
                self.value = self.curve.do_query(self.query, self.value)
            if self.functions:
                for i in range(len(self.functions)):
                    self.value = self.functions[i](self.value, self.paras[i].do_update())
        return self.value

    def set_base(self, base):
        if base != self.base:
            self.update = True
            
            self.base = base

    def change_base(self, base, function, para):
        self.base = function(self.base, para)
        

class World:
    def __init__(self):
        self.curves = dict()
        self.values = dict()

    def add_item(self, name, item, curve=False, value=False):
        if curve:
            self.curves[name] = item
        elif value:
            self.values[name] = item

    def get_item(self, name, curve=False, value=False):
        if curve:
            return self.curves.get(name)
        elif value:
            return self.values.get(name)

        return None

    def do_update(self):
        lst = [value for value in self.values.values() if value.update]

        while lst:
            for child in lst.pop().children:
                if not child.update:
                    child.update = True

                    lst.append(child)

        for value in self.values.values():
            value.do_update()

def add_helper(lst, item):
    if not item in lst:
        lst.append(item)

def run_helper(funct, paras, x=None):
    if len(paras) == 3:
        if x:
            return funct(x, paras[2].value, paras[0].value, paras[1].value)
        else:
            return funct(paras[2].value, paras[0].value, paras[1].value)
    elif len(paras) == 2:
        if x:
            return funct(x, paras[0].value, paras[1].value)
        else:
            return funct(paras[0].value, paras[1].value)

    return None

foo = World()
foo.add_item("Total Wealth", Value(100), value=True)
foo.add_item("Total Pop", Value(10), value=True)
foo.add_item("Wealth Distrib Base", Value(2), value=True)
foo.add_item("Wealth Distrib Modi", Value(1), value=True)
foo.add_item("Wealth Distrib Loc", Value(0), value=True)
foo.add_item(
    "Wealth Distrib Shape",
    Value(
        1,
        [
            MULT,
            MULT
            ],
        [
            foo.get_item("Wealth Distrib Base", value=True),
            foo.get_item("Wealth Distrib Modi", value=True)
            ],
        ),
    value=True
    )
foo.add_item(
    "Wealth Distrib Scale",
    Value(
        1,
        [
            MULT,
            DIV,
            DIV
            ],
        [
            foo.get_item("Total Wealth", value=True),
            foo.get_item("Total Pop", value=True),
            foo.get_item("Wealth Distrib Shape", value=True)
            ],
        ),
    value=True
    )
foo.add_item(
    "Wealth Distrib Curve",
    Curve(
        gamma,
        foo.get_item("Wealth Distrib Loc", value=True),
        foo.get_item("Wealth Distrib Scale", value=True),
        foo.get_item("Wealth Distrib Shape", value=True)
        ),
    curve=True
    )

curve = foo.get_item("Wealth Distrib Curve", curve=True)

print(curve.do_query(Query.MEAN))
