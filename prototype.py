from scipy.stats import gamma
from scipy.stats import norm
from scipy.stats import skewnorm
from scipy.stats import beta
from enum import Enum

import matplotlib.pyplot as plt
import numpy as np
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

        for para in self.paras:
            add_helper(para.children, self)

    def do_update(self):
        if self.update:
            self.update = False
            
            for para in self.paras:
                para.do_update()

        return self

    def do_query(self, query, x=None):
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
    def __init__(self, base, functions=None, paras=None):
        self.base = base
        self.functions = functions
        self.paras = paras
        self.value = None
        self.update = True

        self.children = []

        if self.paras:
            for para in self.paras:
                add_helper(para.children, self)

        self.do_update()

    def do_update(self):
        if self.update:
            self.update = False

            self.value = self.base
            
            if self.functions:
                for i in range(len(self.functions)):
                    self.value = self.functions[i](self.value, self.paras[i].do_update())

        return self.value

    def set_base(self, base):
        if base != self.base:
            self.update = True
            
            self.base = base

class Instance(Value):
    def __init__(self, base, query, curve, functions=None, paras=None):
        self.query = query
        self.curve = curve
        
        super().__init__(base, functions, paras)

        add_helper(self.curve.children, self)

    def do_update(self):
        if self.update:
            self.value = self.curve.do_query(self.query, super().do_update())

        return self.value

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
    if len(paras) == 4:
        if x:
            return funct(x, paras[2].value, paras[3].value, paras[0].value, paras[1].value)
        else:
            return funct(paras[2].value, paras[3].value, paras[0].value, paras[1].value)
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
foo.add_item("1", Value(1), value=True)
foo.add_item("0", Value(0), value=True)
foo.add_item("-1", Value(-1), value=True)

foo.add_item("Soldiers Total", Value(4), value=True)
foo.add_item("Soldiers Wealth Distrib Shape Base", Value(5), value=True)
foo.add_item(
    "Soldiers Wealth Distrib Shape A",
    Value(
        0,
        [ADD],
        [foo.get_item("Soldiers Wealth Distrib Shape Base", value=True)],
    ),
    value=True
    )
foo.add_item(
    "Soldiers Wealth Distrib Shape B",
    Value(
        0,
        [ADD],
        [foo.get_item("Soldiers Wealth Distrib Shape Base", value=True)],
    ),
    value=True
    )
foo.add_item("Soldiers Wealth Distrib Scale", Value(1), value=True)
foo.add_item(
    "Soldiers Wealth Distrib Curve",
    Curve(
        beta,
        foo.get_item("0", value=True),
        foo.get_item("Soldiers Wealth Distrib Scale", value=True),
        foo.get_item("Soldiers Wealth Distrib Shape A", value=True),
        foo.get_item("Soldiers Wealth Distrib Shape B", value=True)
        ),
    curve=True
    )

foo.add_item("Nobles Total", Value(3), value=True)
foo.add_item("Nobles Wealth Distrib Shape Base", Value(5), value=True)
foo.add_item(
    "Nobles Wealth Distrib Shape A",
    Value(
        5,
        [ADD],
        [foo.get_item("Nobles Wealth Distrib Shape Base", value=True)],
    ),
    value=True
    )
foo.add_item(
    "Nobles Wealth Distrib Shape B",
    Value(
        0,
        [ADD],
        [foo.get_item("Nobles Wealth Distrib Shape Base", value=True)],
    ),
    value=True
    )
foo.add_item("Nobles Wealth Distrib Scale", Value(2), value=True)
foo.add_item(
    "Nobles Wealth Distrib Curve",
    Curve(
        beta,
        foo.get_item("0", value=True),
        foo.get_item("Nobles Wealth Distrib Scale", value=True),
        foo.get_item("Nobles Wealth Distrib Shape A", value=True),
        foo.get_item("Nobles Wealth Distrib Shape B", value=True)
        ),
    curve=True
    )

foo.add_item(
    "Pops Total",
    Value(
        0,
        [
            ADD,
            ADD
            ],
        [
            foo.get_item("Soldiers Total", value=True),
            foo.get_item("Nobles Total", value=True)
            ]
        ),
    value=True
    )

soldiers_wealth = foo.get_item("Soldiers Wealth Distrib Curve", curve=True)
nobles_wealth = foo.get_item("Nobles Wealth Distrib Curve", curve=True)

soldiers_total = foo.get_item("Soldiers Total", value=True).value
nobles_total = foo.get_item("Nobles Total", value=True).value
pops_total = foo.get_item("Pops Total", value=True).value

fig, ax = plt.subplots(1, 1)
size = int(150*nobles_wealth.do_query(Query.MEAN))
x = np.linspace(0.01, 1.5*nobles_wealth.do_query(Query.MEAN), size)
ax.plot(x, [soldiers_total * soldiers_wealth.do_query(Query.PDF, xx) for xx in x], 'r-', alpha=0.6)
ax.plot(x, [nobles_total * nobles_wealth.do_query(Query.PDF, xx) for xx in x], 'b-', alpha=0.6)

print(soldiers_wealth.do_query(Query.MEAN))
print(nobles_wealth.do_query(Query.MEAN))


foo.add_item("Hours in Day", Value(24), value=True)
foo.add_item("Maximum Workhour", Value(18), value=True)
foo.add_item(
    "Minimum Leisure",
    Value(
        1,
        [
            MULT,
            SUBT
            ],
        [
            foo.get_item("Hours in Day", value=True),
            foo.get_item("Maximum Workhour", value=True),
            ],
        ),
    value=True
    )        

foo.add_item("Labor Drive", Value(6), value=True)
foo.add_item("Labor Shape Base", Value(4), value=True)
foo.add_item(
    "Labor Shape",
    Value(
        1,
        [
            MULT,
            ADD
            ],
        [
            foo.get_item("Labor Shape Base", value=True),
            foo.get_item("Labor Drive", value=True)
            ]
        ),
    value=True
    )
foo.add_item(
    "Workhour Distrib Curve",
    Curve(
        beta,
        foo.get_item("0", value=True),
        foo.get_item("Maximum Workhour", value=True),
        foo.get_item("Labor Shape", value=True),
        foo.get_item("Labor Shape Base", value=True),
        ),
    curve=True
    )
foo.add_item(
    "Leisure Distrib Curve",
    Curve(
        beta,
        foo.get_item("Minimum Leisure", value=True),
        foo.get_item("Maximum Workhour", value=True),
        foo.get_item("Labor Shape Base", value=True),
        foo.get_item("Labor Shape", value=True),
        ),
    curve=True
    )
foo.add_item(
    "Average Workhour",
    Instance(
        0,
        Query.MEAN,
        foo.get_item("Workhour Distrib Curve", curve=True)
    ),
    value=True
    )
foo.add_item(
    "Average Leisure",
    Instance(
        0,
        Query.MEAN,
        foo.get_item("Leisure Distrib Curve", curve=True)
    ),
    value=True
    )

plt.show()
