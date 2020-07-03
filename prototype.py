from scipy.stats import gamma, beta, norm, truncnorm
from scipy.integrate import quad
from scipy.special import gammainc
from collections import ChainMap
from enum import Enum
from bitarray.util import count_and
from bitarray import bitarray as bitmap
from numpy import linspace

import matplotlib.pyplot as plt
import json
import glob
import time
import math

SET = lambda x, para : para
MAX = lambda x, para : max(x, para)
MIN = lambda x, para : min(x, para)
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
    PPF = 3
    MEAN = 4
    PMEAN = 5

class Curve:
    def __init__(self, distrib, paras):
        self.distrib = distrib
        self.paras = paras
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
        elif query == Query.PPF:
            return run_helper(self.do_update().distrib.ppf, self.paras, x)
        elif query == Query.MEAN:
            return run_helper(self.do_update().distrib.mean, self.paras)
        elif query == Query.PMEAN:
            if type(self.distrib) == type(beta):
                return self.paras[2].value / (self.paras[2].value + self.paras[3].value) * beta.cdf(x, self.paras[2].value + 1, self.paras[3].value, self.paras[0].value, self.paras[1].value) / self.do_query(Query.CDF, x)
            elif type(self.distrib) == type(gamma):
                return self.paras[1].value * (self.paras[2].value - (math.pow(x, self.paras[2].value) * math.exp(-x) / gammainc(self.paras[2].value, x)))
            elif type(self.distrib) == type(norm):
                return truncnorm.mean(0, x, self.paras[0], self.paras[1])
            else:
                return quad(lambda x, curve : x * curve.do_query(Query.PDF, x), 0, x, args=(self,))[0] / self.do_query(Query.CDF, x)

        return None

class CurveSum:
    def __init__(self, curves, functions=None, paras=None, functions_mean=None, paras_mean=None):
        self.curves = curves
        self.functions = functions
        self.paras = paras
        self.functions_mean = functions_mean
        self.paras_mean = paras_mean
        self.mean = None
        self.update = True

        self.children = []

        for curve in self.curves:
            add_helper(curve.children, self)

        if self.paras:
            for paras in self.paras:
                for para in paras:
                    add_helper(para.children, self)
        if self.paras_mean:
            for paras in self.paras_mean:
                for para in paras:
                    add_helper(para.children, self)

        self.do_update()

    def do_update(self):
        if self.update:
            self.update = False

            self.mean = 0

            for i, curve in enumerate(self.curves):
                functions = []
                paras = []
                
                if self.paras_mean:
                    functions = self.functions_mean[i]
                    paras = self.paras_mean[i]

                mean = curve.do_query(Query.MEAN)

                for ii in range(len(paras)):
                    mean = functions[ii](mean, paras[ii].do_update())

                self.mean += mean

        return self

    def do_query(self, query, x=None):
        if query == Query.PDF or query == Query.CDF or query == Query.PPF or query == Query.PMEAN:
            result = 0

            for i, curve in enumerate(self.curves):
                functions = []
                paras = []

                if self.paras:
                    functions = self.functions[i]
                    paras = self.paras[i]

                t = curve.do_query(query, x)

                for ii in range(len(paras)):
                    t = functions[ii](t, paras[ii].do_update())

                result += t

            return result
        elif query == Query.MEAN:
            return self.do_update().mean

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

    def change_base(self, function, para):
        self.set_base(function(self.base, para))

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
        
        self.systems = dict()
        self.systems_id = dict()
        self.values_id = dict()

        self.systems_bitmap = bitmap()
        self.values_bitmap = bitmap()

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

    def add_system(self, name, item, parents=None):
        if not name in self.systems:
            self.systems_id[name] = len(self.systems_bitmap)
            self.systems_bitmap.append(False)

            for system in self.systems.values():
                system.parents.append(False)

            item.parents = self.systems_bitmap.copy()
            item.parents.setall(False)

            for value in item.writes:
                if not value in self.values_id:
                    self.values_id[value] = len(self.values_bitmap)
                    self.values_bitmap.append(False)

                    for system in self.systems.values():
                        system.values.append(False)

            item.values = self.values_bitmap.copy()
            item.values.setall(False)

            if parents:
                for parent in parents:
                    item.parents[self.systems_id[parent]] = True

            for value in item.writes:
                item.values[self.values_id[value]] = True

            self.systems[name] = item

    def do_run(self):
        systems = dict(self.systems)
        self.systems_bitmap.setall(True)

        while True:
            self.values_bitmap.setall(False)
            
            lst = []
            
            for name, system in systems.items():
                if not count_and(self.systems_bitmap, system.parents) and not count_and(self.values_bitmap, system.values):
                    self.values_bitmap = self.values_bitmap | system.values

                    lst.append((name, system))

            if lst:
                for name, system in lst:
                    systems.pop(name)
                    self.systems_bitmap[self.systems_id[name]] = False
                    system.do_run()
            else:
                break
        

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

                obj['type'] = typ

                if typ == 'CurveSum':
                    obj['curves'] = dct['curves']
                    obj['functions'] = dct['functions']
                    obj['paras'] = dct['paras']
                    obj['functions_mean'] = dct['functions_mean']
                    obj['paras_mean'] = dct['paras_mean']

                    for curve in obj['curves']:
                        add_helper(parents, curve)
                        add_helper(self.objs[curve]['children'], name)
                    for paras in obj['paras']:
                        for para in paras:
                            add_helper(parents, para)
                            add_helper(self.objs[para]['children'], name)
                    for paras in obj['paras_mean']:
                        for para in paras:
                            add_helper(parents, para)
                            add_helper(self.objs[para]['children'], name)
                else:
                    paras = dct['paras']

                    for para in paras:
                        add_helper(parents, para)
                        add_helper(self.objs[para]['children'], name)

                    obj['paras'] = paras
                    
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
                
                typ = obj['type']

                if typ == 'CurveSum':
                    world.add_item(
                        name,
                        CurveSum(
                            [world.get_item(curve) for curve in obj['curves']],
                            [[str_2_function(function) for function in functions] for functions in obj['functions']],
                            [[world.get_item(para) for para in paras] for paras in obj['paras']],
                            [[str_2_function(function) for function in functions] for functions in obj['functions_mean']],
                            [[world.get_item(para) for para in paras] for paras in obj['paras_mean']]
                        )
                    )
                elif typ == 'Curve':
                    distrib = obj['distrib']
                    
                    if distrib == 'gamma':
                        distrib = gamma
                    elif distrib == 'beta':
                        distrib = beta
                    elif distrib == 'normal':
                        distrib = normal

                    world.add_item(
                        name,
                        Curve(
                            distrib,
                            [world.get_item(para) for para in obj['paras']]
                        )
                    )
                elif typ == 'Value':
                    world.add_item(
                        name,
                        Value(
                            float(obj['base']),
                            [str_2_function(function) for function in obj['functions']],
                            [world.get_item(para) for para in obj['paras']]
                        )
                    )
                elif typ == 'Instance':
                    query = obj['query']

                    if query == 'PDF':
                        query = Query.PDF
                    elif query == 'CDF':
                        query = Query.CDF
                    elif query == 'PPF':
                        query = Query.PPF
                    elif query == 'MEAN':
                        query = Query.MEAN
                    elif query == 'PMEAN':
                        query = Query.PMEAN

                    world.add_item(
                        name,
                        Instance(
                            float(obj['base']),
                            query,
                            world.get_item(obj['curve']),
                            [str_2_function(function) for function in obj['functions']],
                            [world.get_item(para) for para in obj['paras']]
                        )
                    )

                for child in obj['children']:
                    self.objs[child]['parents'].remove(name)

            lst = [pair for pair in self.objs.items() if not pair[1]['parents']]
            
        return world

class System:
    def __init__(self, writes=None, reads=None):
        self.writes = parse_list(writes)
        self.reads = parse_list(reads)
        self.parents = bitmap()
        self.values = bitmap()

    def do_run(self):
        pass

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

def str_2_function(string):
    if string == 'SET':
        return SET
    elif string == 'MAX':
        return MAX
    elif string == 'MIN':
        return MIN
    elif string == 'MULT':
        return MULT
    elif string == 'DIV':
        return DIV
    elif string == 'ADD':
        return ADD
    elif string == 'SUBT':
        return SUBT
    elif string == 'POW':
        return POW
    elif string == 'ROOT':
        return ROOT
    elif string == 'LOG':
        return LOG

    return None

def parse_list(item):
    if type(item) == type(dict()):
        return item
    elif type(item) == type(list()):
        return dict(ChainMap(*item))
    else:
        return dict()
                        
if __name__ == '__main__':
    loader = WorldLoader('C:\\Users\\wogud\\Desktop\\Prototype\\World')
    world = loader.gen()

    fig, ax = plt.subplots(1, 1)

    farmers_wealth = world.get_item("Farmers Wealth Distrib Curve")
    lumberjacks_wealth = world.get_item("Lumberjacks Wealth Distrib Curve")
    herdsmen_wealth = world.get_item("Herdsmen Wealth Distrib Curve")
    craftsmen_wealth = world.get_item("Craftsmen Wealth Distrib Curve")
    nobles_wealth = world.get_item("Nobles Wealth Distrib Curve")
    pops_wealth = world.get_item("Pops Wealth Distrib Curve")

    farmers_total = world.get_item("Farmers Total")
    lumberjacks_total = world.get_item("Lumberjacks Total")
    herdsmen_total = world.get_item("Herdsmen Total")
    craftsmen_total = world.get_item("Craftsmen Total")
    nobles_total = world.get_item("Nobles Total")
    pops_total = world.get_item("Pops Total")

    size = int(150*nobles_wealth.do_query(Query.MEAN))

    x = np.linspace(0.01, 1.5*nobles_wealth.do_query(Query.MEAN), size)

    farmers_y = [farmers_total.value * farmers_wealth.do_query(Query.PDF, xx) for xx in x]
    lumberjacks_y = [lumberjacks_total.value * lumberjacks_wealth.do_query(Query.PDF, xx) for xx in x]
    herdsmen_y = [herdsmen_total.value * herdsmen_wealth.do_query(Query.PDF, xx) for xx in x]
    craftsmen_y = [craftsmen_total.value * craftsmen_wealth.do_query(Query.PDF, xx) for xx in x]
    nobles_y = [nobles_total.value * nobles_wealth.do_query(Query.PDF, xx) for xx in x]
    pops_y = [pops_total.value * pops_wealth.do_query(Query.PDF, xx) for xx in x]

    ax.plot(x, farmers_y, 'r-', alpha=0.6)
    ax.plot(x, lumberjacks_y, 'b-', alpha=0.6)
    ax.plot(x, herdsmen_y, 'g-', alpha=0.6)
    ax.plot(x, craftsmen_y, 'k', alpha=0.6)
    ax.plot(x, nobles_y, 'y', alpha=0.6)
    ax.plot(x, pops_y, 'teal', alpha=0.6)

    fig, ax = plt.subplots(1, 1)

    workhour = world.get_item("Workhour Distrib Curve")
    leisure = world.get_item("Leisure Distrib Curve")

    size = int(100*world.get_item("Hours in Day").value)

    x = np.linspace(0.01, world.get_item("Hours in Day").value, size)

    workhour_y = [workhour.do_query(Query.PDF, xx) for xx in x]
    leisure_y = [leisure.do_query(Query.PDF, xx) for xx in x]

    ax.plot(x, workhour_y, 'r-', alpha=0.6)
    ax.plot(x, leisure_y, 'b-', alpha=0.6)

    fig, ax = plt.subplots(1, 1)

    farmers_skill = world.get_item("Farmers Skill Distrib Curve")
    lumberjacks_skill = world.get_item("Lumberjacks Skill Distrib Curve")
    herdsmen_skill = world.get_item("Herdsmen Skill Distrib Curve")
    craftsmen_skill = world.get_item("Craftsmen Skill Distrib Curve")
    nobles_skill = world.get_item("Nobles Skill Distrib Curve")
    pops_skill = world.get_item("Pops Skill Distrib Curve")

    size = 100

    x = np.linspace(0.01, 1, size)

    farmers_y = [farmers_total.value * farmers_skill.do_query(Query.PDF, xx) for xx in x]
    lumberjacks_y = [lumberjacks_total.value * lumberjacks_skill.do_query(Query.PDF, xx) for xx in x]
    herdsmen_y = [herdsmen_total.value * herdsmen_skill.do_query(Query.PDF, xx) for xx in x]
    craftsmen_y = [craftsmen_total.value * craftsmen_skill.do_query(Query.PDF, xx) for xx in x]
    nobles_y = [nobles_total.value * nobles_skill.do_query(Query.PDF, xx) for xx in x]
    pops_y = [pops_total.value * pops_skill.do_query(Query.PDF, xx) for xx in x]

    ax.plot(x, farmers_y, 'r-', alpha=0.6)
    ax.plot(x, lumberjacks_y, 'b-', alpha=0.6)
    ax.plot(x, herdsmen_y, 'g-', alpha=0.6)
    ax.plot(x, craftsmen_y, 'k', alpha=0.6)
    ax.plot(x, nobles_y, 'y', alpha=0.6)
    ax.plot(x, pops_y, 'teal', alpha=0.6)

    fig, ax = plt.subplots(1, 1)

    farmers_wealth = world.get_item("Farmers Property Distrib Curve")
    lumberjacks_wealth = world.get_item("Lumberjacks Property Distrib Curve")
    herdsmen_wealth = world.get_item("Herdsmen Property Distrib Curve")
    craftsmen_wealth = world.get_item("Craftsmen Property Distrib Curve")
    nobles_wealth = world.get_item("Nobles Property Distrib Curve")
    pops_wealth = world.get_item("Pops Property Distrib Curve")

    farmers_total = world.get_item("Farmers Total")
    lumberjacks_total = world.get_item("Lumberjacks Total")
    herdsmen_total = world.get_item("Herdsmen Total")
    craftsmen_total = world.get_item("Craftsmen Total")
    nobles_total = world.get_item("Nobles Total")
    pops_total = world.get_item("Pops Total")

    size = int(150*nobles_wealth.do_query(Query.MEAN))

    x = np.linspace(0.01, 1.5*nobles_wealth.do_query(Query.MEAN), size)

    farmers_y = [farmers_total.value * farmers_wealth.do_query(Query.PDF, xx) for xx in x]
    lumberjacks_y = [lumberjacks_total.value * lumberjacks_wealth.do_query(Query.PDF, xx) for xx in x]
    herdsmen_y = [herdsmen_total.value * herdsmen_wealth.do_query(Query.PDF, xx) for xx in x]
    craftsmen_y = [craftsmen_total.value * craftsmen_wealth.do_query(Query.PDF, xx) for xx in x]
    nobles_y = [nobles_total.value * nobles_wealth.do_query(Query.PDF, xx) for xx in x]
    pops_y = [pops_total.value * pops_wealth.do_query(Query.PDF, xx) for xx in x]

    ax.plot(x, farmers_y, 'r-', alpha=0.6)
    ax.plot(x, lumberjacks_y, 'b-', alpha=0.6)
    ax.plot(x, herdsmen_y, 'g-', alpha=0.6)
    ax.plot(x, craftsmen_y, 'k', alpha=0.6)
    ax.plot(x, nobles_y, 'y', alpha=0.6)
    ax.plot(x, pops_y, 'teal', alpha=0.6)

    print(world.get_item("Farmers Low Skill Total").value)
    print(world.get_item("Farmers Med Skill Total").value)
    print(world.get_item("Farmers High Skill Total").value)
    print('----------------------------')

    print(world.get_item("Lumberjacks Low Skill Total").value)
    print(world.get_item("Lumberjacks Med Skill Total").value)
    print(world.get_item("Lumberjacks High Skill Total").value)
    print('----------------------------')

    print(world.get_item("Herdsmen Low Skill Total").value)
    print(world.get_item("Herdsmen Med Skill Total").value)
    print(world.get_item("Herdsmen High Skill Total").value)
    print('----------------------------')

    print(world.get_item("Craftsmen Low Skill Total").value)
    print(world.get_item("Craftsmen Med Skill Total").value)
    print(world.get_item("Craftsmen High Skill Total").value)
    print('----------------------------')

    print(world.get_item("Nobles Low Skill Total").value)
    print(world.get_item("Nobles Med Skill Total").value)
    print(world.get_item("Nobles High Skill Total").value)
    print('----------------------------')

    print(world.get_item("Pops Low Skill Total").value)
    print(world.get_item("Pops Med Skill Total").value)
    print(world.get_item("Pops High Skill Total").value)
    print('----------------------------')

    print(world.get_item("Farmers Labor").value)
    print(world.get_item("Lumberjacks Labor").value)
    print(world.get_item("Herdsmen Labor").value)
    print(world.get_item("Craftsmen Labor").value)
    print('----------------------------')

    print(world.get_item("Farmers Food Consumption").value)

    world.do_run()

    plt.show()
