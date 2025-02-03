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
        stuff = tuple(dict.fromkeys(stuff))
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
        return hash((self._anything, self._stuff))

    def __eq__(self, other):
        if not isinstance(other, AgreeingAttributes):
            raise NotImplementedError
        return (
            self._anything == other._anything and
            self._stuff == other._stuff
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


class RawPart:
    def __init__(self, gs: Iterable[etree.Element], kanji):
        self.g = AgreeingAttributes(gs)
        self.kanji = kanji

    def __hash__(self):
        return hash(self.g)

    def __eq__(self, other):
        if not isinstance(other, RawPart):
            raise NotImplementedError
        return self.g == other.g

    @cached_property
    def parent(self):
        for p in product(*(e.iterancestors(SVG + 'g') for e in self.g)):  # yes it's O(n^n)
            potential_parent = RawElement(p, faux=True, kanji=self.kanji)
            if potential_parent in self.kanji._elements_flattened_set:
                potential_parent._sanity_check()
                return potential_parent

    def __repr__(self):
        return f'<{type(self).__name__} {self.name}>'


class LogicalPart:
    def __init__(self, raw_part: RawPart):
        self.raw = raw_part

    def __hash__(self):
        return hash(self._hash())

    @property
    def name(self):
        # we do a little caching
        try:
            equiv = type(self)._EQUIV
        except AttributeError:
            equiv = type(self)._EQUIV = {
                t: equiv_cls[0]
                for equiv_cls in self.EQUIVALENT
                for t in equiv_cls}

        try:
            return equiv[self.raw.name]
        except KeyError:
            return self.raw.name

    def __str__(self):
        return str(self.raw)

    def __repr__(self):
        return f'<{type(self).__name__} {self.name}>'


class RawStroke(RawPart):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        assert self.g.tag == SVG + 'path'
        assert len(self.g) == 1

    @property
    def path(self):
        return list(self.g)[0]

    @property
    def name(self):
        t = self.path.get(KVG + 'type')
        if t is not None:
            t = t[0]
        return t

    def _print(self, level):
        yield '　' * level + (str(self.name) or '')


class LogicalStroke(LogicalPart):
    EQUIVALENT = [
        ('㇐', '㇀'),
        ('㇏', '㇔'),
        ('㇑', '㇕', '㇙'),
        ('㇆', '㇖'),
    ]

    def _hash(self):
        return '-'

    def __eq__(self, other):
        if not isinstance(other, LogicalPart):
            raise NotImplementedError
        return _eq_or_missing(self.name, other.name)


class RawElement(RawPart):
    def __init__(self, *args, faux=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not faux:
            self._sanity_check()

    def _sanity_check(self):
        assert self.g.tag == SVG + 'g'
        if len(self.g) > 1:
            for i, g in enumerate(self.g):
                assert g.get(KVG + 'part') == str(i + 1)

    @property
    def name(self):
        return self.g.get(KVG + 'element')

    @cached_property
    def children(self):
        return [
            p
            for p
            in self.kanji._parts_flattened
            if p.parent is not None and p.parent == self]

    def _print(self, level):
        yield '・' * level + str(self.name) + ' ' + str(ord(str(self.name)[0]))
        for c in self.children:
            yield from c._print(level + 1)

    def __str__(self):
        return '\n'.join(self._print(0)) + '\n'


class LogicalElement(LogicalPart):
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
        '叉㕚',
        '臼𦥑',
        '匚匸',
        '儿八',
    ]

    @property
    def kanji(self):
        return self.raw.kanji

    def _does_not_contain(self, element_name):
        return element_name in self.DOES_NOT_CONTAIN.get(self.name, [])

    def _iterate_children(self, good_parent=None):
        if good_parent is None:
            good_parent = self

        if self.name in self.FINAL:
            return

        for c in self.raw.children:
            if isinstance(c, RawStroke):
                yield LogicalStroke(c)
            elif isinstance(c, RawElement):
                c = LogicalElement(c)
                if ((c.name in kanji_names)  # FIXME
                        and (c.name not in self.FAKE)
                        and not good_parent._does_not_contain(c.name)
                        # self.kanji.name == good_parent.kanji.name
                        and self.kanji.name not in
                        good_parent.NOT_PRESENT_IN_KANJI.get(c.name, {})):
                    yield c
                else:
                    # we are a bad child
                    yield from c._iterate_children(good_parent)
            else:
                raise Exception

    @property
    def children(self):
        return self._iterate_children()

    def _hash(self):
        return '(' + ''.join(c._hash() for c in self.children) + ')'

    def __eq__(self, other):
        if not isinstance(other, LogicalPart):
            raise NotImplementedError
        return _eq_or_missing(self.name, other.name) \
            and _eq_zip(self.children, other.children)  # FIXME


class Kanji(LogicalElement):
    def __init__(self, filename):
        root = etree.parse(filename).getroot()
        g = root.xpath(f"//svg:g[@id='kvg:{filename.stem}']",
                       namespaces={'svg': SVG.strip('}{')})
        self.filename = filename
        return super().__init__(RawElement(g, kanji=self))

    # optimization for RawPart.parent
    @cached_property
    def _elements_flattened_set(self):
        return {p for p in self._parts_flattened if isinstance(p, RawElement)}

    @cached_property
    @autoconsume(list)
    def _parts_flattened(self):
        def redundant(g):  # workaround for 05de8
            return (
                len(g.getparent()) == 1
                and g.get(KVG + 'part') is not None
                and g.getparent().get(KVG + 'element') == g.get(KVG + 'element')
                and g.getparent().get(KVG + 'part') == g.get(KVG + 'part')
            )

        for i, e in enumerate(self.raw.g.iter()):
            if e.tag == SVG + 'path':
                yield RawStroke([e], kanji=self)
            elif (
                    e.tag == SVG + 'g'
                    and e.get(KVG + 'part', '1') == '1'
                    and not redundant(e)):
                # p = 0
                # yield Element(
                #     e1 for e1 in islice(self.g.iter(), i, None))
                #     if e1.get(KVG + 'element') == e.get(KVG + 'element')
                #     and e1.get(KVG + 'number') == e.get(KVG + 'number'))
                #     and p < (k := e1.get(KVG + 'part'))
                #     and (p := max(k, p)))

                # you decide which is more (less) readable lmao

                yield RawElement(takewhile(
                    lambda e1: e1 == e or e1.get(KVG + 'part', '1') != '1',
                    filter(lambda e1: (
                        e1.get(KVG + 'element') == e.get(KVG + 'element')
                        and e1.get(KVG + 'number') == e.get(KVG + 'number')
                        and not redundant(e1)),
                        islice(self.raw.g.iter(), i, None))  # yes it's O(n^2)
                ), kanji=self)


def extract_elements(e):
    if isinstance(e, LogicalElement):
        yield e
        for c in e.children:
            yield from extract_elements(c)


kanji_names = set()  # FIXME
kanjis = []
elements = []


for filename in files:
    # print(file.stem)
    # g = root.xpath("//svg:g[@id and starts-with(@id, 'kvg:StrokePaths_07e4d')]",
    #                namespaces={'svg': 'http://www.w3.org/2000/svg'})
    # handle_element(False, *g)
    e = Kanji(filename)
    kanjis.append(e)
    kanji_names.add(e.name)
    # print(e)
    # print()


for k in kanjis:
    print(k.filename.stem)
    # print(list(k.raw.children))
    print(k)
    elements.extend(extract_elements(e))


exit()


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
