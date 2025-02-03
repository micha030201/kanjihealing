import sys
from functools import cached_property
from itertools import zip_longest, groupby, takewhile, islice, product
from pprint import pprint
from pathlib import Path
from collections import defaultdict
from typing import Iterable

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
        stuff = list(stuff)
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

    def __contains__(self, thing):
        return thing == self._anything or thing in self._stuff

    def __hash__(self):
        return hash(frozenset(self._anything, *self._stuff))

    def __eq__(self, other):
        if not isinstance(other, AgreeingAttributes):
            raise NotImplementedError
        return (
            {self._anything, *self._stuff} ==
            {other._anything, *other._stuff}
        )


def flatten(forest):
    return (leaf for tree in forest for leaf in tree)


def autoconsume(collection):
    def pred(generator_function):
        def function_returning_list(*args, **kwargs):
            return collection(generator_function(*args, **kwargs))
        return function_returning_list
    return pred


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


class KanjiPart:
    def __init__(self, kanji):
        self.kanji = kanji

    @property
    def _equiv(self):
        # we do a little caching
        try:
            equiv = type(self)._EQUIV
        except AttributeError:
            equiv = type(self)._EQUIV = {
                t: equiv_cls[0]
                for equiv_cls in self.EQUIVALENT
                for t in equiv_cls}

        try:
            return equiv[self.name]
        except KeyError:
            return self.name

    def __hash__(self):
        return hash(self._hash())

    @cached_property
    def parent(self):
        for p in product(*self.g):  # yes it's O(n^n)
            potential_parent_innards = AgreeingAttributes(p)
            if potential_parent_innards in self.kanji._element_innards:
                return self.kanji._element_innards[potential_parent_innards]


class Stroke(KanjiPart):
    EQUIVALENT = [
        ('㇐', '㇀'),
        ('㇏', '㇔'),
        ('㇑', '㇕', '㇙'),
        ('㇆', '㇖'),
    ]

    def __init__(self, path: etree.Element, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert path.tag == SVG + 'path'
        self.path = path

    # for some methods in KanjiPart
    @property
    def g(self):
        return AgreeingAttributes([self.path])

    @property
    def name(self):
        t = self.path.get(KVG + 'type')
        if t is not None:
            t = t[0]
        return t

    def _hash(self):
        return '-'

    def __eq__(self, other):
        return isinstance(other, Stroke) \
            and _eq_or_missing(self._equiv, other._equiv)

    def _print(self, level):
        # yield '・' * level + (self.name or '')
        yield '・' * level + (str(self._equiv) or '')
        # return ()


class Element(KanjiPart):
    FAKE = {
        '丿', '丨', '丶', '一', None, '倠', '𦍒',
    }

    FINAL = {
        '立', '龰', '龶', '長', '里', '己', '貝', '豆', '衣', '血', '虫', '艹',
        '廿', '大', '糸', '白', '王', '氵', '小', '土', '糸', '禾', '王', '正',
    }

    DOES_NOT_CONTAIN = {
        '𢦏': {'土', '㇐'},
        '𡗗': {'大'},
        '𠔉': {'大'},
        '𠂤': {'㠯'},
        '竜': {'龍'},
        '鼡': {'臼'},
        '革': {'口'},  # kinda does contain ig
        '遂': {'八'},
        '鐵': {'載', '裁'}
        # '黍': {None},
    }

    NOT_PRESENT_IN_KANJI = {
        # lazy. space is technically also not present as an element so
        # whatever
        '頁': '獺 懶 癩 籟 嬾 藾',
        '頼': '獺 懶 癩 籟 嬾 藾',
        '静': '瀞',
        '青': '蜻 猜 靜 菁 錆 倩 瀞 睛 鯖',
        '難': '儺 攤',  # debatable tbh, one line difference
        '載': '鐡',
        '贈': '囎',
        '裁': '殱 纎',
        '艸': '趨 皺 蒭 芻 雛 鄒',
        '乙': '巴',
    }

    EQUIVALENT = [
        ('四', '罒'),
        '⻌辶',
        '㕚叉',
        '臼𦥑',
        '匚匸',
        '儿八',
    ]

    def __init__(self, gs: Iterable[etree.Element], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.g = AgreeingAttributes(gs)
        assert self.g.tag == SVG + 'g'
        if len(self.g) > 1:
            for i, g in enumerate(self.g):
                assert g.get(KVG + 'part') == str(i + 1)

    @property
    def name(self):
        return self.g.get(KVG + 'element')

    def _does_not_contain(self, element_name):
        return element_name in self.DOES_NOT_CONTAIN.get(self.name, [])

    @property
    def children(self):
        for g in self.g:
            for e in g:
                if e.tag == SVG + 'path':
                    yield Stroke(e, kanji=self.kanji)
                elif e.tag == SVG + 'g':
                    # if (len(e) == 1 and (
                    #         e.get(KVG + 'radical') not in {None, 'general', 'tradit'}
                    #         or not e.get(KVG + 'element'))):
                    e_name = e.get(KVG + 'element')
                    # 053b6, etc.
                    if (len(e) == 1 and (not e_name or e_name == self.name)):
                        # print('recursing')
                        yield from Element(e, kanji=self.kanji).children
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
                    else:
                        yield Element(e, kanji=self.kanji)
                else:
                    raise Exception

    def _iterate_elements(self, good_parent=None):
        if good_parent is None:
            good_parent = self

        if self.name in self.FINAL:
            return

        for c in self.children:
            if not isinstance(c, Element):
                pass
            elif ((c.name in kanji_names)
                    and (c.name not in self.FAKE)
                    and not good_parent._does_not_contain(c.name)
                    # self.kanji.name == good_parent.kanji.name
                    and self.kanji.name not in
                    good_parent.NOT_PRESENT_IN_KANJI.get(c.name, {})):
                yield c
            else:
                # we are a bad child
                yield from c._iterate_elements(good_parent)

    @property
    def elements(self):
        return self._iterate_elements()

    def _hash(self):
        return '(' + ''.join(c._hash() for c in self.children) + ')'

    def __eq__(self, other):
        return isinstance(other, Element) \
            and _eq_or_missing(self.name, other.name) \
            and _eq_zip(self.children, other.children)  # FIXME

    def _print(self, level):
        yield '・' * level + str(self.name) + str(ord(str(self.name)[0]))  # + '   ' + self._hash()
        for c in self.elements:
            yield from c._print(level + 1)

    def __str__(self):
        return '\n'.join(self._print(0)) + '\n'


class Kanji(Element):
    def __init__(self, g: etree.Element, file):
        self.file = file
        return super().__init__(g, kanji=self)

    @cached_property
    def _element_innards(self):
        return {e.g: e for e in self._parts_flattened if isinstance(e, Stroke)}

    @cached_property
    @autoconsume(list)
    def _parts_flattened(self):
        for i, e in enumerate(self.g.iter()):
            if e.tag == SVG + 'path':
                yield Stroke(e, kanji=self)
            elif e.tag == SVG + 'g' and e.get(KVG + 'part', '1') == '1':
                # p = 0
                # yield Element(
                #     e1 for e1 in islice(self.g.iter(), i))
                #     if e1.get(KVG + 'element') == e.get(KVG + 'element')
                #     and e1.get(KVG + 'number') == e.get(KVG + 'number'))
                #     and p < (k := e1.get(KVG + 'part'))
                #     and (p := max(k, p)))

                # you decide which is more (less) readable lmao

                yield Element(*takewhile(
                    lambda e1: e1 == e or e.get(KVG + 'part', '1') != '1',
                    filter(lambda e1: (
                        e1.get(KVG + 'element') == e.get(KVG + 'element')
                        and e1.get(KVG + 'number') == e.get(KVG + 'number')),
                        islice(self.g.iter(), i))  # yes it's O(n^2)
                ))


def extract_elements(e):
    if isinstance(e, Element):
        yield e
        for c in e.elements:
            yield from extract_elements(c)


kanji_names = set()
elements = []


for file in files:
    # print(file.stem)
    root = etree.parse(file).getroot()
    # g = root.xpath("//svg:g[@id and starts-with(@id, 'kvg:StrokePaths_07e4d')]",
    #                namespaces={'svg': 'http://www.w3.org/2000/svg'})
    g = root.xpath(f"//svg:g[@id='kvg:{file.stem}']",
                   namespaces={'svg': SVG.strip('}{')})
    # handle_element(False, *g)
    e = Kanji(*g, file=file)
    kanji_names.add(e.name)
    elements.extend(extract_elements(e))
    # print(e)
    # print()


def group(it, key=None):
    return [list(g) for k, g in groupby(sorted(it, key=key), key=key)]


def children_key(e):
    return tuple(
        ('s', str(c._equiv)) if type(c) is Stroke else ('e', str(c._equiv))
        for c in e.elements)


whoopsies = 0

exceptions = {
    '𦥑', '𢦏', '齊',
    '鳥',  # sometimes written without the bottom 4 strokes
    '闌',  # the line in the middle can be split in two, not an error
    '走', '足',  # often look like 止, but ig it's semantic or whatever
    '襄',  # this one is a mf
}

groups = group(elements, key=lambda e: e.name or unnamed())
for g in groups:
    if g[0].name in exceptions:
        continue
    groups2 = group(g, key=children_key)
    if len(groups2) > 1:
        whoopsies += 1
        for g2 in groups2:
            print(len(g2))
            print(*[e.kanji.name for e in g2])
            print(*[e.kanji.file for e in g2])
            print(*[e.kanji.file.stem for e in g2], sep=', ')
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
