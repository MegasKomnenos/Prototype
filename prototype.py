from scipy.stats import gamma
from scipy.stats import norm
from scipy.stats import beta
from enum import Enum

import matplotlib.pyplot as plt
import numpy as np
import math
import json
import glob

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
        self.objs = dict()

    def add_item(self, name, item):
        self.objs[name] = item

    def get_item(self, name):
        return self.objs.get(name)

    def do_update(self):
        lst = [obj for obj in self.objs.values() if obj.update]

        while lst:
            for child in lst.pop().children:
                if not child.update:
                    child.update = True

                    lst.append(child)

        for obj in self.objs.values():
            obj.do_update()

class WorldLoader:
    def __init__(self, root):
        files = []

        for path in glob.glob(f'{root}\\*.json'):
            files.append(json.load(open(path)))

        self.objs = dict()

        for file in files:
            for dct in file:
                name = dct.get('name')

                if name:
                    obj = dict()

                    obj['loaded'] = False
                    obj['parents'] = list()
                    obj['children'] = list()

                    self.objs[name] = obj
                else:
                    file.remove(dct)

        for file in files:
            for dct in file:
                name = dct['name']
                obj = self.objs[name]
                parents = obj['parents']
                children = obj['children']
                typ = dct.get('type')

                paras = dct['paras']

                for para in paras:
                    add_helper(parents, para)
                    add_helper(self.objs[para]['children'], name)

                obj['paras'] = paras
                obj['type'] = typ

                if typ == 'Curve':
                    obj['distrib'] = dct['distrib']
                elif typ == 'Value':
                    obj['functions'] = dct['functions']
                    obj['base'] = dct['base']
                elif typ == 'Instance':
                    curve = dct['curve']

                    obj['curve'] = curve
                    obj['query'] = dct['query']
                    obj['functions'] = dct['functions']
                    obj['base'] = dct['base']

                    add_helper(parents, curve)
                    add_helper(self.objs[curve]['children'], name)

    def gen(self):
        world = World()

        lst = [pair for pair in self.objs.items() if not pair[1]['parents']]

        while lst:
            for (name, obj) in lst:
                self.objs.pop(name)
                
                paras = obj['paras']
                typ = obj['type']
                
                if typ == 'Curve':
                    distrib = obj['distrib']
                    
                    if distrib == 'gamma':
                        world.add_item(
                            name,
                            Curve(
                                gamma,
                                world.get_item(paras[0]),
                                world.get_item(paras[1]),
                                world.get_item(paras[2])
                            )
                        )
                    elif distrib == 'beta':
                        world.add_item(
                            name,
                            Curve(
                                beta,
                                world.get_item(paras[0]),
                                world.get_item(paras[1]),
                                world.get_item(paras[2]),
                                world.get_item(paras[3])
                            )
                        )
                    elif distrib == 'normal':
                        world.add_item(
                            name,
                            Curve(
                                normal,
                                world.get_item(paras[0]),
                                world.get_item(paras[1])
                            )
                        )
                elif typ == 'Value':
                    paras = [world.get_item(para) for para in paras]
                    
                    functions = []

                    for function in obj['functions']:
                        if function == 'MULT':
                            functions.append(MULT)
                        if function == 'DIV':
                            functions.append(DIV)
                        if function == 'ADD':
                            functions.append(ADD)
                        if function == 'SUBT':
                            functions.append(SUBT)
                        if function == 'POW':
                            functions.append(POW)
                        if function == 'ROOT':
                            functions.append(ROOT)
                        if function == 'LOG':
                            functions.append(LOG)
                    
                    
                    world.add_item(
                        name,
                        Value(
                            float(obj['base']),
                            functions,
                            paras
                        )
                    )
                elif typ == 'Instance':
                    paras = [world.get_item(para) for para in paras]
                    
                    functions = []
                    query = obj['query']

                    for function in obj['functions']:
                        if function == 'MULT':
                            functions.append(MULT)
                        if function == 'DIV':
                            functions.append(DIV)
                        if function == 'ADD':
                            functions.append(ADD)
                        if function == 'SUBT':
                            functions.append(SUBT)
                        if function == 'POW':
                            functions.append(POW)
                        if function == 'ROOT':
                            functions.append(ROOT)
                        if function == 'LOG':
                            functions.append(LOG)

                    if query == 'PDF':
                        query = Query.PDF
                    elif query == 'CDF':
                        query = Query.CDF
                    elif query == 'MEDN':
                        query = Query.MEDN
                    elif query == 'MEAN':
                        query = Query.MEAN

                    world.add_item(
                        name,
                        Instance(
                            float(obj['base']),
                            query,
                            world.get_item(obj['curve']),
                            functions,
                            paras
                        )
                    )

                for child in obj['children']:
                    self.objs[child]['parents'].remove(name)

            lst = [pair for pair in self.objs.items() if not pair[1]['parents']]
            
        return world

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
                        

loader = WorldLoader('C:\\Users\\wogud\\Desktop\\Prototype\\World')
world = loader.gen()

fig, ax = plt.subplots(1, 1)

farmers_wealth = world.get_item("Farmers Wealth Distrib Curve")
lumberjacks_wealth = world.get_item("Lumberjacks Wealth Distrib Curve")
herdsmen_wealth = world.get_item("Herdsmen Wealth Distrib Curve")
nobles_wealth = world.get_item("Nobles Wealth Distrib Curve")

farmers_total = world.get_item("Farmers Total")
lumberjacks_total = world.get_item("Lumberjacks Total")
herdsmen_total = world.get_item("Herdsmen Total")
nobles_total = world.get_item("Nobles Total")
pops_total = world.get_item("Pops Total")

size = int(150*nobles_wealth.do_query(Query.MEAN))

x = np.linspace(0.01, 1.5*nobles_wealth.do_query(Query.MEAN), size)

farmers_y = [farmers_total.value * farmers_wealth.do_query(Query.PDF, xx) for xx in x]
lumberjacks_y = [lumberjacks_total.value * lumberjacks_wealth.do_query(Query.PDF, xx) for xx in x]
herdsmen_y = [herdsmen_total.value * herdsmen_wealth.do_query(Query.PDF, xx) for xx in x]
nobles_y = [nobles_total.value * nobles_wealth.do_query(Query.PDF, xx) for xx in x]
pops_y = [farmers_y[i] + lumberjacks_y[i] + herdsmen_y[i] + nobles_y[i] for i in range(size)]

ax.plot(x, farmers_y, 'r-', alpha=0.6)
ax.plot(x, lumberjacks_y, 'b-', alpha=0.6)
ax.plot(x, herdsmen_y, 'g-', alpha=0.6)
ax.plot(x, nobles_y, 'teal', alpha=0.6)
ax.plot(x, pops_y, 'black', alpha=0.6)

plt.show()
