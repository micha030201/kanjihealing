import sys
from pprint import pprint
from pathlib import Path
from collections import defaultdict

from lxml import etree


# fuck xml. all my homies hate xml
SVG = '{http://www.w3.org/2000/svg}'
KVG = '{http://kanjivg.tagaini.net}'


files = list(Path('kanjivg/kanji').glob(sys.argv[1] + '.svg'))

bare_elements = defaultdict(set)
decomposition = defaultdict(set)


def unnamed(_index=[0]):
    _index[0] += 1
    return f'<unnamed element #{_index[0]}>'


class Unnamed:
    # TODO is this necessary
    index = 0

    def __new__(cls, *args, **kwargs):
        cls.index += 1
        return super().__new__(*args, **kwargs)

    def __init__(self):
        self.index = self.index

    # this is just so that all unnamed elements don't become one element
    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)

    def __repr__(self):
        return f'<unnamed element {self.index}>'


class AgreeingAttributes:
    def __init__(self, stuff):
        self._anything = stuff[0]
        self._stuff = stuff[1:]

    def __getattr__(self, name):
        try:
            attr = getattr(self._anything, name)
        except AttributeError:
            s = object()
            # TODO make a new exception class instead of using assert
            assert all(getattr(thing, name, s) == s for thing in self._stuff)
            raise
        if callable(attr):
            def agreeing_method(*args, **kwargs):
                ret = attr(*args, **kwargs)
                assert all(
                    getattr(thing, name)(*args, **kwargs) == ret
                    for thing in self._stuff)
                return ret

            return agreeing_method
        assert all(
            getattr(thing, name) == attr
            for thing in self._stuff)
        return attr

    def __iter__(self):
        yield self._anything
        yield from self._stuff

    def __len__(self):
        return 1 + len(self._stuff)


def flatten(forest):
    return (leaf for tree in forest for leaf in tree)


def ilen(it):
    i = 0
    for _ in it:
        i += 1
    return i


def nesting_level(e):
    return ilen(e.iterancestors())


class Stroke:
    def __init__(self, path: etree.Element):
        assert path.tag == SVG + 'path'
        self.path = path

    def _print(self, level):
        # yield '・' * level + self.path.get(KVG + 'type')
        return ()


class Element:
    def __init__(self, *g: etree.Element):
        self.g = AgreeingAttributes(g)
        assert self.g.tag == SVG + 'g'
        if len(self.g) > 1:
            for i, g in enumerate(self.g):
                assert g.get(KVG + 'part') == str(i + 1)

    @property
    def name(self):
        # can't use get(key, fallback) here because we don't want the
        # index to increase when the element has a name
        return self.g.get(KVG + 'element') or unnamed()

    @property
    def children(self):
        for g in self.g:
            for e in g:
                # print(e.attrib)
                if e.tag == SVG + 'path':
                    yield Stroke(e)
                elif e.tag == SVG + 'g':
                    # if (len(e) == 1 and (
                    #         e.get(KVG + 'radical') not in {None, 'general', 'tradit'}
                    #         or not e.get(KVG + 'element'))):
                    e_name = e.get(KVG + 'element')
                    # 053b6, etc.
                    if len(e) == 1 and not e_name or e_name == self.name:
                        # print('recursing')
                        yield from Element(e).children
                    elif e.get(KVG + 'part') is not None:
                        # the not thing is for 05de8 etc.
                        xpath = f'//svg:g[@kvg:part \
                                      and @kvg:element="{e_name}" \
                                      and not(../@kvg:element="{e_name}" \
                                          and ../@kvg:part=./@kvg:part)]'
                        if (number := e.get(KVG + 'number')) is not None:
                            xpath = f'//svg:g[@kvg:part \
                                          and @kvg:element="{e_name}" \
                                          and @kvg:number="{number}" \
                                          and not(../@kvg:element="{e_name}" \
                                              and ../@kvg:part=./@kvg:part \
                                              and ../@kvg:number="{number}")]'
                        es_ = self.g.xpath(xpath,
                                           namespaces={'svg': SVG.strip('}{'),
                                                       'kvg': KVG.strip('}{')})
                        es_ = list(es_)
                        # print(xpath)
                        # print('es_')
                        # pprint([e.attrib for e in es_])
                        # this is a workaround for 05f41 etc.
                        es = []
                        passed = False
                        for e_ in es_:
                            if (not es or e_.get(KVG + 'part') <=
                                    es[-1].get(KVG + 'part')):
                                if passed:
                                    break
                                es = []
                            es.append(e_)
                            if e == e_:
                                passed = True
                        # print('es')
                        # pprint([e.attrib for e in es])
                        topmost_es = [
                            e for e in es
                            if nesting_level(e) == min(map(nesting_level, es))]
                        # print('topmost_es')
                        # pprint([e.attrib for e in topmost_es])
                        # print(min(topmost_es, key=lambda e: int(e.get(KVG + 'part'))).attrib)
                        if e == min(topmost_es,
                                    key=lambda e: int(e.get(KVG + 'part'))):
                            # print('creating multipart')
                            yield Element(*es)
                        else:
                            yield from Element(e).children
                    elif e.get(KVG + 'part') is not None:
                        pass
                    else:
                        yield Element(e)
                else:
                    raise Exception

    def _print(self, level):
        yield '・' * level + self.name
        for c in self.children:
            yield from c._print(level + 1)

    def __str__(self):
        return '\n'.join(self._print(0)) + '\n'


# we're referring to the kanji element here, as kanjivg defines it. that
# it also happens to be an svg element is coincidental
def handle_element(parent_element: str, *gs: etree.Element):
    element = gs[0].get(KVG + 'element')
    if element is not None:
        decomposition[parent_element].add(element)
    else:
        element = parent_element
    # print(element)
    for g in gs:
        for child in g:
            if child.tag.endswith('g'):
                if child.get(KVG + 'part') == '1':
                    child_element = child.get(KVG + 'element')
                    handle_element(element, *g.xpath(
                        f'svg:g[@kvg:element="{child_element}"]',
                        namespaces={'svg': SVG.strip('}{'),
                                    'kvg': KVG.strip('}{')}))
                handle_element(element, child)
            elif child.tag.endswith('path'):
                if element is not parent_element:
                    bare_elements[element].add(parent_element)
            else:
                raise Exception(child.tag)


for file in files:
    print(file.stem)
    root = etree.parse(file).getroot()
    # g = root.xpath("//svg:g[@id and starts-with(@id, 'kvg:StrokePaths_07e4d')]",
    #                namespaces={'svg': 'http://www.w3.org/2000/svg'})
    g = root.xpath(f"//svg:g[@id='kvg:{file.stem}']",
                   namespaces={'svg': SVG.strip('}{')})
    # handle_element(False, *g)
    e = Element(*g)
    print(e)
    print()

# print(len(bare_elements))
# pprint(dict(bare_elements))
# for k, v in bare_elements.items():
#     if len(v) > 10:
#         print(k, '\t', ''.join(x for x in v if x))
# pprint({k: v for k, v in bare_elements.items() if len(v) > 10})
