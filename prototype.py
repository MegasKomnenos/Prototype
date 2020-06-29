from scipy.stats import gamma
from scipy.stats import norm

from enum import Enum

import math

GAMMAPDF = lambda x, paras : gamma.pdf(x, paras[2].value, paras[0].value, paras[1].value)
GAMMACDF = lambda x, paras : gamma.cdf(x, paras[2].value, paras[0].value, paras[1].value)

NORMPDF = lambda x, paras : norm.pdf(x, paras[0].value, paras[1].value)
NORMCDF = lambda x, paras : norm.cdf(x, paras[0].value, paras[1].value)

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

class Curve:
    def __init__(self, pdf, cdf, *paras):
        self.pdf = pdf
        self.cdf = cdf
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
        if query == Query.PDF:
            return self.do_update().pdf(x, self.paras)
        elif query == Query.CDF:
            return self.do_update().cdf(x, self.paras)

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

class Dict:
    def __init__(self):
        self.curves = dict()
        self.values = dict()

    def add_item(self, name, item, curve=False, value=False):
        if curve:
            self.curves[name] = item
        if value:
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

foo = Dict()
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
        GAMMAPDF,
        GAMMACDF,
        foo.get_item("Wealth Distrib Loc", value=True),
        foo.get_item("Wealth Distrib Scale", value=True),
        foo.get_item("Wealth Distrib Shape", value=True)
        ),
    curve=True
    )

foo.add_item("Total Farmland", Value(10), value=True)
foo.add_item("Average Temperature", Value(-1), value=True)
foo.add_item("Temperature Deviation", Value(1), value=True)
foo.add_item("1", Value(1), value=True)
foo.add_item("-1", Value(-1), value=True)
foo.add_item(
    "Temperature Distrib Curve",
    Curve(
        NORMPDF,
        NORMCDF,
        foo.get_item("Average Temperature", value=True),
        foo.get_item("Temperature Deviation", value=True)
        ),
    curve=True
    )
foo.add_item(
    "Wheat Possible Farmland",
    Value(
        15.5,
        [
            SUBT,
            MULT,
            MULT
            ],
        [
            foo.get_item("1", value=True),
            foo.get_item("-1", value=True),
            foo.get_item("Total Farmland", value=True)
            ],
        curve=foo.get_item("Temperature Distrib Curve", curve=True),
        query=Query.CDF
        ),
    value=True
    )
foo.add_item(
    "Grazing Possible Farmland",
    Value(
        0,
        [
            SUBT,
            MULT,
            MULT
            ],
        [
            foo.get_item("1", value=True),
            foo.get_item("-1", value=True),
            foo.get_item("Total Farmland", value=True)
            ],
        curve=foo.get_item("Temperature Distrib Curve", curve=True),
        query=Query.CDF
        ),
    value=True
    )

print(foo.get_item("Wheat Possible Farmland", value=True).value)
print(foo.get_item("Grazing Possible Farmland", value=True).value)
