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
                return self.paras[2].value * self.paras[1].value * gammainc(self.paras[2].value + 1, x / self.paras[1].value) / gammainc(self.paras[2].value, x / self.paras[1].value)
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
        self.defines = dict()
        
        self.systems = dict()
        self.systems_id = dict()
        self.values_id = dict()

        self.systems_bitmap = bitmap()
        self.values_bitmap = bitmap()

    def add_item(self, name, item):
        self.objs[name] = item

    def get_item(self, name):
        return self.objs.get(name)

    def set_defines(self, item):
        self.defines = item

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
        self.objs = dict()
        self.defines = dict()
        
        files = []
        templates = {}
        defines = []
        
        for path in glob.glob(f'{root}\\World\\*.json'):
            files.append(json.load(open(path)))
        for path in glob.glob(f'{root}\\Template\\*.txt'):
            templates[path.split('\\')[-1].split('.')[0].strip()] = open(path).read()
        for path in glob.glob(f'{root}\\Defines\\*.json'):
            defines.append(json.load(open(path)))

        self.defines = parse_list(defines)

        for file in files:
            for dct in file:
                name = dct.get('name')
                tp = dct.get('type')

                if name and tp:
                    if tp == 'Template':
                        self.convert_template(templates, templates[name], dct)
                    else:
                        obj = dict(dct)

                        obj['parents'] = list()
                        obj['children'] = list()

                        self.objs[name] = obj
                else:
                    file.remove(dct)

        for name, obj in self.objs.items():
            parents = obj['parents']
            children = obj['children']
            tp = obj['type']

            if tp == 'CurveSum':
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
                for para in obj['paras']:
                    add_helper(parents, para)
                    add_helper(self.objs[para]['children'], name)

                if tp == 'Instance':
                    add_helper(parents, obj['curve'])
                    add_helper(self.objs[obj['curve']]['children'], name)

    def convert_template(self, templates, template, dct):
        for arg, val in dct.items():
            if f'%{arg}%' in template:
                template = template.replace(f'%{arg}%', str(val))

        template = apply_conditional('!', '@', template, dct)
        template = apply_conditional('#', '$', template, dct)

        parsed = json.loads(template)

        for dct in parsed:
            name = dct.get('name')
            tp = dct.get('type')

            if name and tp:
                if tp == 'Template':
                    self.convert_template(templates, templates[name], dct)
                else:
                    obj = dict(dct)

                    obj['parents'] = list()
                    obj['children'] = list()

                    self.objs[name] = obj

    def gen(self):
        world = World()
        world.set_defines(self.defines)

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

class SystemTrade(System):
    def __init__(self, world):
        self.pops = world.defines['Pop']
        self.goods = world.defines['Good']
        
        writes = dict()
        reads = dict()

        for pop in self.pops:
            for good in self.goods:
                writes[f'{pop} {good} Bid Matched'] = world.get_item(f'{pop} {good} Bid Matched')
                writes[f'{pop} {good} Offer Matched'] = world.get_item(f'{pop} {good} Offer Matched')
                writes[f'{pop} {good} Trade Balance'] = world.get_item(f'{pop} {good} Trade Balance')
                writes[f'{pop} {good} Price'] = world.get_item(f'{pop} {good} Price')
                
                reads[f'{pop} {good} Bid'] = world.get_item(f'{pop} {good} Bid')
                reads[f'{pop} {good} Offer'] = world.get_item(f'{pop} {good} Offer')

        super().__init__(writes, reads)

        world.add_system("Trade System", self)

    def do_run(self):
        def split_sections(price, amount, pop):
            return [[price * 0.75, amount * 0.25, 0, pop], [price, amount * 0.5, 0, pop], [price * 1.25, amount * 0.25, 0, pop]]
        
        for pop in self.pops:
            for good in self.goods:
                self.writes[f'{pop} {good} Bid Matched'].set_base(0)
                self.writes[f'{pop} {good} Offer Matched'].set_base(0)
                self.writes[f'{pop} {good} Trade Balance'].set_base(0)

        for good in self.goods:
            bids = []
            offers = []

            for pop in self.pops:
                price = self.writes[f'{pop} {good} Price'].value
                bid = self.reads[f'{pop} {good} Bid'].value
                offer = self.reads[f'{pop} {good} Offer'].value

                if bid:
                    bids.extend(split_sections(price, bid, pop))
                elif offer:
                    offers.extend(split_sections(price, offer, pop))

            bids.sort(key=lambda item: item[0], reverse=True)
            offers.sort(key=lambda item: item[0])

            scores = [[max(bid[0] - offer[0], 0) for offer in offers] for bid in bids]

            while True:
                bids_matching = [[0 for offer in offers] for bid in bids]

                for i, bid in enumerate(bids):
                    if bid[1] > bid[2]:
                        sm = 0
                        
                        for ii, offer in enumerate(offers):
                            bids_matching[i][ii] = scores[i][ii] * (offer[1] - offer[2])
                            sm += bids_matching[i][ii]

                        if sm > 0:
                            for ii, offer in enumerate(offers):
                                bids_matching[i][ii] /= sm
                                bids_matching[i][ii] *= bid[1] - bid[2]

                                if bids_matching[i][ii] > offer[1] - offer[2]:
                                    bids_matching[i][ii] = offer[1] - offer[2]
                                    
                trade_volume = 0
                
                for i, offer in enumerate(offers):
                    seller_balance = self.writes[f'{offer[3]} {good} Trade Balance']
                    
                    total_bid = sum([bids_matching[ii][i] for ii, _ in enumerate(bids) if scores[ii][i]])
                    total_offer = offer[1] - offer[2]

                    if total_bid <= total_offer:
                        offer[2] += total_bid
                        trade_volume += total_bid

                        for ii, bid in enumerate(bids):
                            bidder_balance = self.writes[f'{bid[3]} {good} Trade Balance']
                            
                            bid[2] += bids_matching[ii][i]

                            price = (offer[0] + bid[0]) / 2

                            seller_balance.change_base(ADD, price * bids_matching[ii][i])
                            bidder_balance.change_base(SUBT, price * bids_matching[ii][i])
                    else:
                        offer[2] += total_offer
                        trade_volume += total_offer
                        worst_bid = min([scores[ii][i] for ii, _ in enumerate(bids) if scores[ii][i] and bids_matching[ii][i]])
                        foo = 1 - total_offer / total_bid
                        sm = 0

                        for ii, bid in enumerate(bids):
                            if scores[ii][i]:
                                bids_matching[ii][i] *= 1 - foo * worst_bid / scores[ii][i]
                                sm += bids_matching[ii][i]
                            
                        for ii, bid in enumerate(bids):
                            if scores[ii][i]:
                                bidder_balance = self.writes[f'{bid[3]} {good} Trade Balance']
                                
                                bids_matching[ii][i] *= total_offer / sm
                                bid[2] += bids_matching[ii][i]

                                price = (offer[0] + bid[0]) / 2

                                seller_balance.change_base(ADD, price * bids_matching[ii][i])
                                bidder_balance.change_base(SUBT, price * bids_matching[ii][i])
                                
                if trade_volume == 0:
                    break

            for bid in bids:
                self.writes[f'{bid[3]} {good} Bid Matched'].change_base(ADD, bid[2])
                self.writes[f'{bid[3]} {good} Price'].change_base(MULT, 1 + (0.5 - bid[2] / bid[1]) / 50)
            for offer in offers:
                self.writes[f'{offer[3]} {good} Offer Matched'].change_base(ADD, offer[2])
                self.writes[f'{offer[3]} {good} Price'].change_base(MULT, 1 + (offer[2] / offer[1] - 0.5) / 50)
            
        
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
    
def apply_conditional(k0, k1, template, dct):
    i = 0
        
    while True:
        i = template.find(k0, i)

        if i + 1:
            ii = template.find(k0, i + 1)

            block = template[i:ii + 1]
            
            check = block[block.find(k1) + 1:]
            check = check[:check.find(k1)]

            if check in dct:
                block = block.replace(f'{k1}{check}{k1}', '').strip(k0 + k1)
            else:
                block = ''

            template = template[:i] + block + template[ii + 1:]
        else:
            break

    return template
                        
if __name__ == '__main__':
    world = WorldLoader('C:\\Users\\wogud\\Desktop\\Prototype').gen()
    SystemTrade(world)
    world.do_run()
    world.do_update()

    print(world.get_item('Peasants Food Trade Balance').value)
    print(world.get_item('Peasants Timber Trade Balance').value)
    print(world.get_item('Peasants Fiber Trade Balance').value)
    print(world.get_item('Peasants Tools Trade Balance').value)
    print('--------------')
    print(world.get_item('Peasants Food Offer Matched').value)
    print(world.get_item('Peasants Timber Offer Matched').value)
    print(world.get_item('Peasants Fiber Offer Matched').value)
    print(world.get_item('Peasants Tools Bid Matched').value)
    print('--------------')
    print(world.get_item('Peasants Food Offer').value)
    print(world.get_item('Peasants Timber Offer').value)
    print(world.get_item('Peasants Fiber Offer').value)
    print(world.get_item('Peasants Tools Bid').value)
    print('--------------')
    print(world.get_item('Craftsmen Food Bid').value)
    print(world.get_item('Craftsmen Timber Bid').value)
    print(world.get_item('Craftsmen Fiber Bid').value)
    print(world.get_item('Craftsmen Tools Offer').value)
    print('--------------')
    print(world.get_item('Peasants Food Price').value)
    print(world.get_item('Peasants Timber Price').value)
    print(world.get_item('Peasants Fiber Price').value)
    print(world.get_item('Peasants Tools Price').value)
    print('--------------')
    print(world.get_item('Craftsmen Food Price').value)
    print(world.get_item('Craftsmen Timber Price').value)
    print(world.get_item('Craftsmen Fiber Price').value)
    print(world.get_item('Craftsmen Tools Price').value)
    
    """
    foo = world.get_item("Pops Total")

    a = time.monotonic()

    for _ in range(100):
        foo.change_base(ADD, 1)
        world.do_run()
        world.do_update()

    print(time.monotonic() - a)
    """
