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


def multiindex(collection, idxs):
    return tuple(collection[i - 1] for i in idxs)


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


class RawElement(RawPart):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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


class _StrokesToElements:
    def __init__(self, strokes_to_elements, errant_strokes):
        assert (
            isinstance(errant_strokes, tuple)
            and all(isinstance(x, int) for x in errant_strokes)
        )
        self.errant_strokes = errant_strokes

        elements = []
        for k, v in strokes_to_elements.items():
            if isinstance(k, int):
                k = (k,)
            assert isinstance(k, tuple) and all(isinstance(x, int) for x in k)
            assert isinstance(v, ElementSpec)
            elements.append((v, k))
        self.elements = tuple(elements)

        counted_strokes = tuple(chain(
            chain.from_iterable(s for e, s in self.elements),
            self.errant_strokes
        ))
        assert (
            min(counted_strokes) == 1 and
            all(x in counted_strokes for x in range(1, max(counted_strokes)))
        )
        # it could be that len(counted_strokes) != max(counted_strokes)
        self.stroke_count = max(counted_strokes)


class ElementSpec:
    _DATA = {}

    def __init__(self, name, variation=None):
        self.name = name
        self.variation = variation

    def __eq__(self, other):
        if not isinstance(other, ElementSpec):
            raise NotImplementedError
        return (
            self.name == other.name
            and self.variation == other.variation
        )

    def __hash__(self):
        return hash((self.name, self.variation))

    def __repr__(self):
        return f'<ElementSpec name={self.name} variation={self.variation}>'

    # Specification:

    def by_stroke_count(self, stroke_count):
        # used when it's a leaf element
        assert self not in self._DATA
        self._DATA[self] = [stroke_count]

    def by_elements(self, *elements):
        # should be a list containing ints and ElementSpecs, to
        # indicate errant strokes and sub-elements

        # this is a bit annoying because it doesn't allow us to always
        # know the stroke count of an ElementSpec on the specification
        # stage, because some of the sub-elements may have not yet been
        # specified. we will ensure the stroke count matches when
        # parsing
        assert self not in self._DATA
        elements = tuple(
            ElementSpec(s) if isinstance(s, str) else s
            for s in elements)
        assert all(isinstance(e, ElementSpec) or isinstance(e, int)
                   for e in elements)
        self._DATA[self] = elements

    def by_strokes_to_elements(self, strokes_to_elements, errant_strokes=()):
        # for the cases where elements overlap
        assert self not in self._DATA
        strokes_to_elements = {k: ElementSpec(v) if isinstance(v, str) else v
                               for k, v in strokes_to_elements.items()}
        self._DATA[self] = _StrokesToElements(strokes_to_elements, errant_strokes)

    # Parsing:

    # all elements should be specified at this stage. we are free to
    # pull sub-elements from cache

    @property
    def _spec(self):
        spec = self._DATA[self]

        if isinstance(spec, list):
            errant_strokes = []
            strokes_to_elements = {}
            i = 1  # we number strokes from 1
            for c in spec:
                if isinstance(c, int):
                    for _ in range(c):
                        errant_strokes.append(i)
                        i += 1
                elif isinstance(c, ElementSpec):
                    strokes_to_elements[tuple(range(i, i + c.stroke_count))] = c
                    i += c.stroke_count
                else:
                    raise Exception()
            spec = _StrokesToElements(strokes_to_elements, tuple(errant_strokes))
            self._DATA[self] = spec

        return spec

    @property
    def stroke_count(self):
        return self._spec.stroke_count

    @property
    def elements(self):
        return self._spec.elements

    @property
    def errant_strokes(self):
        return self._spec.errant_strokes


class LogicalElement:
    def __init__(self, spec, strokes, kanji):
        self.strokes = tuple(strokes)
        self.kanji = kanji
        self.spec = spec

    def _print(self, level):
        yield '・' * level + str(self.spec.name) + ' ' + str(ord(str(self.spec.name)[0]))
        for c in self.elements:
            yield from c._print(level + 1)
        if len(self.errant_strokes):
            yield '　' * (level + 1) + f'{len(self.errant_strokes)} errant strokes'

    def __str__(self):
        return '\n'.join(self._print(0)) + '\n'

    @cached_property
    @autoconsume(tuple)
    def elements(self):
        assert len(self.strokes) == self.spec.stroke_count
        for spec, stroke_idxs in self.spec.elements:
            yield LogicalElement(
                spec,
                multiindex(self.strokes, stroke_idxs),
                self.kanji
            )

    @cached_property
    def errant_strokes(self):
        assert len(self.strokes) == self.spec.stroke_count
        return multiindex(self.strokes, self.spec.errant_strokes)


class Kanji(LogicalElement):
    def __init__(self, filename):
        root = etree.parse(filename).getroot()
        g = root.xpath(f"//svg:g[@id='kvg:{filename.stem}']",
                       namespaces={'svg': SVG.strip('}{')})
        self.filename = filename
        self.raw = RawElement(g, kanji=self)
        return super().__init__(
            ElementSpec(self.raw.name), self.raw.strokes, self)

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


KANJI = {}


for filename in Path('kanjivg/kanji').glob('?????.svg'):
    k = Kanji(filename)
    KANJI[k.raw.name] = k


def extract_elements(e):
    if isinstance(e, RawElement):
        yield e
        for c in e.children:
            yield from extract_elements(c)


raw_elements = []

for k in KANJI.values():
    raw_elements.extend(extract_elements(k.raw))


def group(it, key=None):
    return [list(g) for k, g in groupby(sorted(it, key=key), key=key)]


def unnamed(_index=[0]):
    _index[0] += 1
    return f'<unnamed element #{_index[0]}>'


def children_key(e):
    # TODO we need to skip some children here. elements like 䍃 are not
    # useful -- they don't have meaning and also differ between kanji (揺 vs 徭)

    # maybe decide usefulness by the number of kanji it's present in?
    return tuple(
        ('s',) if type(c) is RawStroke else ('e', str(c.name))
        for c in e.children)


import specinfo
specinfo.spec(ElementSpec)


raw_element_parents = {}


def extract_elements_with_parent(e, p):
    if isinstance(e, RawElement):
        raw_element_parents[e] = p
        for c in e.children:
            extract_elements_with_parent(c, e)


for k in KANJI.values():
    extract_elements_with_parent(k.raw, k.raw)

for g in group(raw_elements, key=lambda e: e.name or unnamed()):
    decomposed_identically = group(g, key=children_key)
    # g[any]
    elem = g[0]

    specced_elem_names = {n.name for n in ElementSpec._DATA}
    if elem.name is None or elem.name in specced_elem_names:
        continue
    if len(decomposed_identically) == 1:

        errant_strokes = tuple(c for c in elem.children if isinstance(c, RawStroke))
        errant_stroke_idxs = tuple(elem.strokes.index(s) + 1 for s in errant_strokes)

        elements = tuple(c for c in elem.children if isinstance(c, RawElement))
        strokes_to_elements = {
            tuple(elem.strokes.index(s) + 1 for s in e.strokes): ElementSpec(e.name)
            for e in elements
        }

        ElementSpec(elem.name).by_strokes_to_elements(
            strokes_to_elements, errant_stroke_idxs)
        # print(f'assuming decomposition {g[0]} for {g[0].name}')
    else:
        print(f'inconsistent decomposition: {g[0].name}')
        for sg in decomposed_identically:
            print(f'variant {children_key(sg[0])}')
            # TODO write parent decomposition? to speed up the process
            same_parent = group(sg, key=lambda e: raw_element_parents[e].name or '<unnamed>')
            print('with parents', ' '.join((raw_element_parents[ssg[0]].name or '<unnamed>') + '(' + ' '.join(e.kanji.spec.name for e in ssg) + ')' for ssg in same_parent))
            print(sg[0])
        break

# TODO this is not the end -- we need to validate that we can correctly
# decompose every kanji, we could (will) have stroke mismatch
