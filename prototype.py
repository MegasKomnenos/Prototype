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

    def get(self, x, query):
        funct = None
        
        if query == Query.PDF:
            funct = self.do_update().distrib.pdf
        elif query == Query.CDF:
            funct = self.do_update().distrib.cdf
        elif query == Query.MEDN:
            funct = self.do_update().distrib.median
        elif query == Query.MEAN:
            funct = self.do_update().distrib.mean

        if funct:
            return run_helper(funct, x, self.paras)

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
        self.size = 0
        self.functions_curve = functions_curve
        self.paras_curve = paras_curve
        self.size_curve = 0
        self.value = None
        self.curve = curve
        self.query = query
        self.update = True

        self.children = []

        if self.curve:
            add_helper(self.curve.children, self)
        if self.functions:
            self.size = len(self.functions)

            for para in self.paras:
                add_helper(para.children, self)
        if self.functions_curve:
            self.size_curve = len(self.functions_curve)

            for para in self.paras_curve:
                add_helper(para.children, self)

        self.do_update()

    def do_update(self):
        if self.update:
            self.update = False

            self.value = self.base

            if self.size_curve:
                for i in range(self.size_curve):
                    self.value = self.functions_curve[i](self.value, self.paras_curve[i].do_update())
            if self.curve:
                self.value = self.curve.get(self.value, self.query)
            if self.size:
                for i in range(self.size):
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

    def add_item(self, name, item, curve=False, value=False, system=False):
        if curve:
            self.curves[name] = item
        elif value:
            self.values[name] = item
        elif system:
            self.systems[name] = item

    def get_item(self, name, curve=False, value=False, system=False):
        if curve:
            return self.curves.get(name)
        elif value:
            return self.values.get(name)
        elif system:
            return self.systems.get(name)

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

def run_helper(funct, x, paras):
    if len(paras) == 3:
        return funct(x, paras[2].value, paras[0].value, paras[1].value)
    elif len(paras) == 2:
        return funct(x, paras[0].value, paras[1].value)

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
            foo.get_item("Wealth Distrib Modi", value=True)
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
