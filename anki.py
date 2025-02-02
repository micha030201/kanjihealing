import sys
from itertools import zip_longest, groupby
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
    # workaround for 05883 etc.
    return ilen(1 for a in e.iterancestors() if a.get(KVG + 'element'))


def _eq_or_missing(a, b, sentinel=None):
    return a is sentinel or b is sentinel or a == b


def _eq_zip(a, b):
    return all(x == y for x, y in zip_longest(a, b, fillvalue=object()))


class Stroke:
    def __init__(self, path: etree.Element, kanji):
        self.kanji = kanji
        assert path.tag == SVG + 'path'
        self.path = path

    @property
    def type(self):
        t = self.path.get(KVG + 'type')
        if t is not None:
            t = t[0]
        return t

    def _hash(self):
        return '-'

    def __hash__(self):
        return hash(self._hash())

    def __eq__(self, other):
        return isinstance(other, Stroke) \
            and _eq_or_missing(self.type, other.type)

    def _print(self, level):
        yield '・' * level + (self.type or '')
        # return ()


class Element:
    FAKE_ELEMENTS = {
        #'丿',
        #'丨',
    }

    def __init__(self, *g: etree.Element, kanji=None, faux=False):
        if not faux:
            assert kanji is not None
        self.kanji = kanji
        self.g = AgreeingAttributes(g)
        assert self.g.tag == SVG + 'g'
        if not faux and self is not kanji:
            assert self.name not in self.FAKE_ELEMENTS
        if len(self.g) > 1:
            for i, g in enumerate(self.g):
                assert g.get(KVG + 'part') == str(i + 1)

    @property
    def name(self):
        return self.g.get(KVG + 'element')

    @property
    def children(self):
        for g in self.g:
            for e in g:
                # print(e.attrib)
                if e.tag == SVG + 'path':
                    yield Stroke(e, kanji=self.kanji)
                elif e.tag == SVG + 'g':
                    # if (len(e) == 1 and (
                    #         e.get(KVG + 'radical') not in {None, 'general', 'tradit'}
                    #         or not e.get(KVG + 'element'))):
                    e_name = e.get(KVG + 'element')
                    # 053b6, etc.
                    if (
                            (len(e) == 1 and (not e_name or e_name == self.name))
                            or (e_name in self.FAKE_ELEMENTS)):
                        # print('recursing')
                        yield from Element(e, kanji=self.kanji, faux=True).children
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
                            yield Element(*es, kanji=self.kanji)
                        else:
                            yield from Element(e, kanji=self.kanji).children
                    elif e.get(KVG + 'part') is not None:
                        pass
                    else:
                        yield Element(e, kanji=self.kanji)
                else:
                    raise Exception

    def _hash(self):
        return '(' + ''.join(c._hash() for c in self.children) + ')'

    def __hash__(self):
        return hash(self._hash())

    def __eq__(self, other):
        return isinstance(other, Element) \
            and _eq_or_missing(self.name, other.name) \
            and _eq_zip(self.children, other.children)

    def _print(self, level):
        yield '－' * level + str(self.name)  # + '   ' + self._hash()
        for c in self.children:
            yield from c._print(level + 1)

    def __str__(self):
        return '\n'.join(self._print(0)) + '\n'


class Kanji(Element):
    def __init__(self, g: etree.Element):
        return super().__init__(g, kanji=self)


def extract_elements(e):
    if isinstance(e, Element):
        yield e
        for c in e.children:
            yield from extract_elements(c)


elements = []


for file in files:
    # print(file.stem)
    root = etree.parse(file).getroot()
    # g = root.xpath("//svg:g[@id and starts-with(@id, 'kvg:StrokePaths_07e4d')]",
    #                namespaces={'svg': 'http://www.w3.org/2000/svg'})
    g = root.xpath(f"//svg:g[@id='kvg:{file.stem}']",
                   namespaces={'svg': SVG.strip('}{')})
    # handle_element(False, *g)
    e = Kanji(*g)
    elements.extend(extract_elements(e))
    # print(e)
    # print()


def group(it, key=None):
    return [list(g) for k, g in groupby(sorted(it, key=key), key=key)]


def children_key(e):
    return tuple(
        ('s', str(c.type)) if type(c) is Stroke else ('e', str(c.name))
        for c in e.children)


whoopsies = 0

groups = group(elements, key=lambda e: e.name or unnamed())
for g in groups:
    groups2 = group(g, key=children_key)
    if len(groups2) > 1:
        whoopsies += 1
        for g2 in groups2:
            print(len(g2), [e.kanji.name for e in g2])
            print(g2[0])
        print('############')
    # if g.count(g[0]) != len(g):
    #     whoopsies += 1
    #     for e in set(g):
    #         print(e)
    #     print('############')

print(whoopsies)

# print(len(bare_elements))
# pprint(dict(bare_elements))
# for k, v in bare_elements.items():
#     if len(v) > 10:
#         print(k, '\t', ''.join(x for x in v if x))
# pprint({k: v for k, v in bare_elements.items() if len(v) > 10})
