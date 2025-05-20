from functools import cached_property
from itertools import (  # can you tell it's my favourite module
    zip_longest, takewhile, islice, chain, combinations, groupby)
from collections import Counter
from pathlib import Path
from typing import Iterable

from lxml import etree


# fuck xml. all my homies hate xml
SVG = '{http://www.w3.org/2000/svg}'
KVG = '{http://kanjivg.tagaini.net}'


class AgreeingAttributes:
    def __init__(self, stuff):
        stuff = tuple(dict.fromkeys(stuff))
        assert all(isinstance(thing, etree._Element) for thing in stuff)
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


def _eq_or_missing(a, b, sentinel=None):
    return a is sentinel or b is sentinel or a == b


def _eq_zip(a, b):
    return all(x == y for x, y in zip_longest(a, b, fillvalue=object()))


def powerset(iterable):
    "powerset([1,2,3]) --> (1,) (2,) (3,) (1,2) (1,3) (2,3) (1,2,3)"
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(1, len(s)+1))


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

    def __repr__(self):
        return f'<{type(self).__name__} {self.name}>'


class LogicalPart:
    @property
    def name(self):
        if self.alias is not None:
            return self.alias

        # we do a little caching
        try:
            equiv = type(self)._NORMALI
        except AttributeError:
            c = Counter(flatten(self.NORMALIZE))
            if c:
                if c.most_common(1)[0][1] > 1:
                    raise Exception(f'Repeated in normalize: {c}')
            equiv = type(self)._NORMALI = {
                t: equiv_cls[0]
                for equiv_cls in self.NORMALIZE
                for t in equiv_cls}

        try:
            return equiv[self.raw.name]
        except KeyError:
            return self.raw.name

    def __str__(self):
        return '\n'.join(self._print(0)) + '\n'

    def __repr__(self):
        return f'<{type(self).__name__} {self.name}>'


class ExistingLogicalPart(LogicalPart):
    def __init__(self, raw_part: RawPart, alias=None):
        self.alias = alias
        self.raw = raw_part


class LogicalElement(LogicalPart):
    def _hash(self):
        return '(' + ''.join(c._hash() for c in self.children) + ')'

    def __hash__(self):
        return hash(self._hash())

    def __eq__(self, other):
        if not isinstance(other, LogicalPart):
            raise NotImplementedError
        return _eq_or_missing(self.name, other.name) \
            and _eq_zip(self.children, other.children)

    def _print(self, level):
        yield '・' * level + str(self.name) + ' ' + str(ord(str(self.name)[0]))
        for c in self.children:
            yield from c._print(level + 1)


class NewLogicalElement(LogicalPart):
    def __init__(self, alias, strokes, kanji):
        self.strokes = tuple(strokes)
        self.alias = alias
        self.kanji = kanji

    @property
    def children(self):
        return self.strokes


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

    def __contains__(self, other):
        if isinstance(other, RawStroke):
            return other == self
        if isinstance(other, RawElement):
            return False
        raise NotImplementedError

    def _print(self, level):
        yield '　' * level + (str(self.name) or '')


class LogicalStroke(ExistingLogicalPart):
    # makes it useless
    NORMALIZE = [
        # ('㇐', '㇀', '㇒'),
        # ('㇑', '㇕', '㇙', '㇏', '㇔'),
        # ('㇆', '㇖', '㇇'),
    ]

    def _hash(self):
        return '-'

    def __hash__(self):
        return hash(self._hash())

    def __eq__(self, other):
        if not isinstance(other, LogicalPart):
            raise NotImplementedError
        return True
        # return _eq_or_missing(self.name, other.name)

    def _print(self, level):
        return ()
        # yield '　' * level + (self.name or '')


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
    @autoconsume(tuple)
    def strokes(self):
        for s in self.kanji._parts_flattened:
            if type(s) is not RawStroke:
                continue
            for a in s.g.iterancestors(SVG + 'g'):  # yes it's O(n^2)
                if a in self.g:
                    yield s
                    break  # this is an optimization technically

    # optimization
    @cached_property
    def _strokes_set(self):
        return frozenset(self.strokes)

    def __contains__(self, other):
        if isinstance(other, RawStroke):
            return other in self._strokes_set
        if isinstance(other, RawElement):
            if other._strokes_set == self._strokes_set:
                return (
                    self.kanji._parts_flattened.index(self) <
                    self.kanji._parts_flattened.index(other)
                )
            return other._strokes_set < self._strokes_set
        raise NotImplementedError

    def _filtered_children(self, pred=lambda _: True):
        parts = [p for p in self.kanji._parts_flattened
                 if p != self and p in self and pred(p)]
        return [p for p in parts
                if not any((p != p1 and p in p1) for p1 in parts)]  # O(n^2)

    @cached_property
    def children(self):
        return self._filtered_children()

    def _print(self, level):
        yield '・' * level + str(self.name) + ' ' + str(ord(str(self.name)[0]))
        for c in self.children:
            yield from c._print(level + 1)

    def __str__(self):
        return '\n'.join(self._print(0)) + '\n'


class ElementSpec:
    def __init__(self, name, *,
                 stroke_count=None,
                 elements=None,
                 strokes_to_elements=None):
        assert (
            stroke_count is not None
            + elements is not None
            + strokes_to_elements is not None) == 1
        # stroke_count is used when it's a leaf element
        # elements should be a list containing ints and ElementSpecs, to
        # indicate errant strokes and sub-elements
        # strokes_to_elements should be a dict of int to None or
        # ElementSpec, for the cases where elements overlap


class E:
    def __init__(self, *elem_names):
        self.elem_names = elem_names


class R:
    def __init__(self, elem_name, variant=0):
        self.elem_name = elem_name
        self.variant = variant


class ExistingLogicalElement(LogicalElement, ExistingLogicalPart):
    COMPOSITION = {
        '齧': [
            '三刀齒',
            '彡刀齒'
        ],
        '囓': R('齧', 1)
    }

    FINAL = {  # FIXME
    }

    FAKE = {
        '丿', '丨', '丶', '一', None, '倠', '𦍒', '㐫', '𠔉', '𠫯', 'CDP-8CB8',
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
        '鐵': {'載', '裁'},
        '肅': {'聿'},
        '章': {'音'},
        # '黍': {None},
        '眞': '具',
        '烏': '鳥',
        '攴': '攵',
        '包': '巳',
        '匃': '匕',
        '算': '大',  # 大 vs 廾
        '捲': '巻',  # the top two strokes and the bottom element are different
        '薀': '温',
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
        '齊': '韲',
        '闌': '蘭',  # it's a variant
        '遂': '燧邃隧',
        '肖': '哨 屑 逍 鮹 峭 悄 趙 稍 霄 銷 蛸',  # TODO fix files
        '林': '瀝 癧 轣 櫪 靂',  # ig it's a variant but fuck it
        '林': '瀝 癧 轣 櫪 靂',
        '真': '癲 巓',
        '十': '癲巓',
        '皀': '梍',
        '朕': '謄',
        '月': '冑',
        '儿': '曽',
        '匕': '曷 藹 臈',
        '人': '掲 謁 渇 褐 喝 吶 衲 靹 銓 蚋 訥',
        '斉': '斎',
        '戔': '賎',
        '巽': '饌',
        '奚': '鶏 渓',
        '夾': '侠 頬',
        '叟': '痩 捜',
        '劵': '藤',
        '䍃': '謡 瑶 揺 遥',
        '顛': '癲 巓',
        '戊': '戊 幾 譏 饑 機 磯',  # caused by our normalization
    }

    ALIASED = {
        # 'A': {'B', 'C'}
        # when element named B is an element named A's child, alias it to C
        # i'm conflicted on this. the shape is like in 由, but the stroke order
        # is like in 用
        '専': {'用': '由'},
    }

    NORMALIZE = [
        # ('四', '罒'),
        # # '⻌辶',  # unfortunately, it's often not disassembled  like this
        # # '叉㕚',
        # # '臼𦥑',
        # '匸匚',  # i think it's always written like that
        # '儿八',
        # '三彡',
        # # '羊⺷',
        # '示礻',
        # # '母毋',
        # '手扌',
        # '小 ⺌',
        # '戍戌',
        # # '黒黑',
        # # '束柬'
    ]

    @property
    def kanji(self):
        return self.raw.kanji

    def _does_not_contain(self, element_name):
        return element_name in self.DOES_NOT_CONTAIN.get(self.name, [])

    @property
    def strokes(self):
        return tuple(LogicalStroke(s) for s in self.raw.strokes)

    _composition_data_checked = False

    @cached_property
    def children(self):
        if not self._composition_data_checked:
            ...  # TODO

        def decompose(name):
            try:
                c = self.COMPOSITION[name]
            except KeyError:
                yield from CONSISTENT_COMPOSITION[name]
            else:
                if isinstance(c, list):
                    yield from decompose(c[0])

        if self.name in self.COMPOSITION:
            ...

        def make_logical(c):
            alias = self.ALIASED.get(self.name, {}).get(c.name)
            if isinstance(c, RawStroke):
                return LogicalStroke(c, alias=alias)
            if isinstance(c, RawElement):
                return LogicalElement(c, alias=alias)
            raise Exception

        def f(c):
            c = make_logical(c)  # just for name normalization
            return (
                True
                and (type(c) is LogicalStroke or c.name in KANJI)
                and (c.name not in self.FAKE)
                and c.name != self.name
                and not self._does_not_contain(c.name)
                # self.kanji.name == good_parent.kanji.name
                and self.kanji.name not in
                self.NOT_PRESENT_IN_KANJI.get(c.name, {})
            )

        return tuple(make_logical(c) for c in self.raw._filtered_children(f))


class Kanji(LogicalElement):
    def __init__(self, filename):
        root = etree.parse(filename).getroot()
        g = root.xpath(f"//svg:g[@id='kvg:{filename.stem}']",
                       namespaces={'svg': SVG.strip('}{')})
        self.filename = filename
        return super().__init__(RawElement(g, kanji=self))

    @cached_property
    def _elements_to_element(self):
        # i knew xml element vs kanji element would come to bite me in
        # the ass. make xml wasn't so wrong with this namespace thing
        ret = {}
        for p in self._parts_flattened:
            if isinstance(p, RawElement):
                for combo in powerset(p.g):
                    ret[frozenset(combo)] = p
        return ret

    @cached_property
    @autoconsume(tuple)
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
    if isinstance(e, RawElement):
        yield e
        for c in e.children:
            yield from extract_elements(c)


KANJI = {}
CONSISTENT_COMPOSITION = {}


for filename in Path('kanjivg/kanji').glob('?????.svg'):
    k = Kanji(filename)
    KANJI[k.raw.name] = k


elements = []

for k in KANJI.values():
    elements.extend(extract_elements(k.raw))


def group(it, key=None):
    return [list(g) for k, g in groupby(sorted(it, key=key), key=key)]


def unnamed(_index=[0]):
    _index[0] += 1
    return f'<unnamed element #{_index[0]}>'


def children_key(e):
    # return tuple(
    #     ('s', str(c.name)) if type(c) is LogicalStroke else ('e', str(c.name))
    #     for c in e.children)
    return tuple(
        ('s',) if type(c) is RawStroke else ('e', str(c.name))
        for c in e.children)
    # return tuple(
    #     str(c.name)
    #     for c in e.children
    #     if type(c) is LogicalElement)
    # return sorted([
    #     str(c.name)
    #     for c in e.children
    #     if type(c) is LogicalElement])


for g in group(elements, key=lambda e: e.name or unnamed()):
    if group(g, key=children_key) == 1:
        # g[any]
        CONSISTENT_COMPOSITION[g[0].name] = g[0]
