from functools import cached_property
from itertools import (  # can you tell it's my favourite module
    zip_longest, takewhile, islice, product, chain, combinations)
from collections import Counter
from contextlib import suppress
from pathlib import Path
from typing import Iterable

from lxml import etree


# fuck xml. all my homies hate xml
SVG = '{http://www.w3.org/2000/svg}'
KVG = '{http://kanjivg.tagaini.net}'


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

    @cached_property
    def parent(self):
        # yes it's O(n^n)
        for p in product(*(e.iterancestors(SVG + 'g') for e in self.g)):
            with suppress(KeyError):
                return self.kanji._elements_to_element[frozenset(p)]

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
    # makes it useless
    NORMALIZE = [
        # ('㇐', '㇀', '㇒'),
        # ('㇑', '㇕', '㇙', '㇏', '㇔'),
        # ('㇆', '㇖', '㇇'),
    ]

    def _hash(self):
        return '-'

    def __eq__(self, other):
        if not isinstance(other, LogicalPart):
            raise NotImplementedError
        return True
        # return _eq_or_missing(self.name, other.name)

    def _print(self, level):
        yield '　' * level + (self.name or '')


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
        '齊': '韲',
    }

    NORMALIZE = [
        ('四', '罒'),
        '⻌辶',
        '叉㕚',
        '臼𦥑',
        '匚匸',
        '儿八',
        '三彡',
    ]

    @property
    def kanji(self):
        return self.raw.kanji

    def _does_not_contain(self, element_name):
        return element_name in self.DOES_NOT_CONTAIN.get(self.name, [])

    @property
    def strokes(self):
        # FIXME
        # using raw.children to avoid infinite recursion
        for c in self.raw.children:
            if isinstance(c, RawStroke):
                yield LogicalStroke(c)
            else:
                yield from LogicalElement(c).strokes

    def _iterate_children(self, good_parent=None):
        if good_parent is None:
            good_parent = self

        if self.name in self.FINAL:
            yield from self.strokes
            return

        for c in self.raw.children:
            if isinstance(c, RawStroke):
                yield LogicalStroke(c)
            elif isinstance(c, RawElement):
                c = LogicalElement(c)
                if ((c.name in KANJI)
                        and (c.name not in self.FAKE)
                        and c.name != good_parent.name
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

    # you have a problem. you try to fix it with inheritance. now you
    # have two problems.
    def _print(self, level):
        yield '・' * level + str(self.name) + ' ' + str(ord(str(self.name)[0]))
        for c in self.children:
            yield from c._print(level + 1)


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


KANJI = {}


files = list(Path('kanjivg/kanji').glob('?????.svg'))
for filename in files:
    k = Kanji(filename)
    # assert k.name not in KANJI, k.name
    # if k.name in KANJI:
    #     print(k.name)
    KANJI[k.name] = k
