from collections import defaultdict
from itertools import groupby, chain, count
from graphlib import TopologicalSorter
import unicodedata

from kanjidb import KANJI, RawElement, RawStroke

element_variant = defaultdict(lambda: 1)
elements = set()
element_parents = defaultdict(list)


FAKE = {
    '丿', '丨', '丶', None, '倠', '𦍒', '𠫯', 'CDP-8CB8', '亅'
}


def good_children(e):
    return e._filtered_children(lambda c: isinstance(c, RawStroke) or (
        c.name in KANJI
        and c.name not in FAKE
        and c.name != e.name))


def extract_elements(e, p):
    if isinstance(e, RawElement):
        if p is not None:
            element_parents[e].append(p)
        yield e
        for c in good_children(e):
            yield from extract_elements(c, e)


for k in KANJI.values():
    assert k.raw.name in KANJI
    elements.update(extract_elements(k.raw, None))


def group(it, key=lambda x: x, sort_key=lambda x: None):
    def full_sort_key(x):
        return key(x), sort_key(x)
    return [list(g) for k, g in groupby(sorted(it, key=full_sort_key), key=key)]


def key(e):
    return tuple(
        ('s',) if type(c) is RawStroke else ('e', str(c.name), element_variant[c])
        for c in good_children(e))


done = False
while not done:
    done = True
    for g in group(elements, key=lambda e: (e.name, element_variant[e])):
        decomposed_identically = group(g, key=key)
        if len(decomposed_identically) != 1:
            done = False
        for i, sg in enumerate(decomposed_identically):
            for e in sg:
                element_variant[e] += i

variants = defaultdict(lambda: (set(), set()))
for e, v in element_variant.items():
    variants[e.name][0].add(v)
    variants[e.name][1].add(e)

for name, t in variants.items():
    vs, es = t
    if len(vs) == 1:
        for e in es:
            element_variant[e] = None


def allowed_as_identifier(c):
    return unicodedata.category(c) in {'Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nl'}


def encode(x):
    if isinstance(x, int):
        return str(x)
    if allowed_as_identifier(x[0]):
        if x[1] is None:
            return x[0]
        return f'{x[0]}_{x[1]}'
    if x[1] is None:
        return f'{hex(ord(x[0]))[1:]}'
    return f'{hex(ord(x[0]))[1:]}_{x[1]}'
    # return f"ElementSpec('{x[0]}', {x[1]})"


def infer_elementspec(elem):
    errant_strokes = tuple(c for c in good_children(elem) if isinstance(c, RawStroke))
    errant_stroke_idxs = tuple(elem.strokes.index(s) + 1 for s in errant_strokes)

    elements = tuple(c for c in good_children(elem) if isinstance(c, RawElement))
    strokes_to_elements = {
        tuple(elem.strokes.index(s) + 1 for s in e.strokes): (e.name, element_variant[e])
        for e in elements
    }

    p = []

    p.append(f'{encode((elem.name, element_variant[elem]))} = ')

    no_overlap = sum(len(k) for k in strokes_to_elements) \
        == len(set(i for k in strokes_to_elements for i in k))
    no_split = all(set(k) == set(range(min(k), max(k) + 1))
                   for k in strokes_to_elements)
    if no_overlap and no_split:
        elements_by = [0]
        last_strokeset = ()
        stroke_to_element = {
            i: (e, idxs)
            for idxs, e in strokes_to_elements.items()
            for i in idxs
        }
        for i in range(1, len(elem.strokes) + 1):
            e, strokeset = stroke_to_element.get(i, (None, None))
            if e is None:
                if isinstance(elements_by[-1], int):
                    elements_by[-1] += 1
                else:
                    elements_by.append(1)
            else:
                if last_strokeset != strokeset:
                    last_strokeset = strokeset
                    elements_by.append(e)

        if elements_by[0] == 0:
            elements_by = elements_by[1:]

        if len(elements_by) == 1 and isinstance(elements_by[0], int):
            assert not elements
            if element_variant[elem] is None:
                p.append(f"ElementSpec('{elem.name}').by_stroke_count({elements_by[0]})\n")
            else:
                p.append(f"ElementSpec('{elem.name}', {element_variant[elem]}).by_stroke_count({elements_by[0]})\n")
        else:
            ems = ', '.join(encode(a) for a in elements_by)
            if element_variant[elem] is None:
                p.append(f"ElementSpec('{elem.name}').by_elements({ems})\n")
            else:
                p.append(f"ElementSpec('{elem.name}', {element_variant[elem]}).by_elements({ems})\n")
    else:
        if element_variant[elem] is None:
            p.append(f"ElementSpec('{elem.name}')")
        else:
            p.append(f"ElementSpec('{elem.name}', {element_variant[elem]})")
        p.append(".by_strokes_to_elements({\n")
        for k, v in strokes_to_elements.items():
            p.append(f'    {k}: {encode(v)},\n')
        p.append('}')
        if errant_stroke_idxs:
            p.append(f', {errant_stroke_idxs}')
        p.append(')\n')

    return ''.join(p)


graph = defaultdict(set)
content = {}

for g in group(elements, key=lambda e: (e.name, element_variant[e])):
    elem = g[0]

    graph[(elem.name, element_variant[elem])].update((c.name, element_variant[c]) for c in good_children(elem) if isinstance(c, RawElement))

    parent_with_kanjis = defaultdict(set)
    for e in g:
        for p in element_parents[e]:
            parent_with_kanjis[p.name].add(e.kanji.spec.name)

    if elem.name in parent_with_kanjis and len(parent_with_kanjis) == 1:
        del parent_with_kanjis[elem.name]
    direct_kanji_parents = [p for p, ks in parent_with_kanjis.items() if len(ks) == 1 and list(ks)[0] == p]
    for par in direct_kanji_parents:
        del parent_with_kanjis[par]

    p = []
    p.append(infer_elementspec(elem))

    if direct_kanji_parents:
        p.append(f'# {" ".join(direct_kanji_parents)}\n')
    for par, ks in parent_with_kanjis.items():
        p.append(f'# {par} ({" ".join(ks)})\n')

    content[(elem.name, element_variant[elem])] = ''.join(p)


print('from kanjidb import ElementSpec\n')

# ts = TopologicalSorter()
# ts.prepare()
# while ts.is_active():
#     node_group = ts.get_ready()
#     for name in sorted(node_group):
#         print(content[name])
#     ts.done(*node_group)

printed = set()

f = 0

# world's worst topological sort
while graph:
    for g in group(graph.items(), key=lambda t: t[0][0], sort_key=lambda t: t[0][1]):
        if all(p in printed for e, ps in g for p in ps):
            for e, ps in g:
                printed.add(e)
                print(content[e])
            graph = {k: v for k, v in graph.items() if k not in printed}
            break
    else:
        f += 1
        for e, ps in sorted(graph.items()):
            if all(p in printed for p in ps):
                printed.add(e)
                print(content[e])
                graph = {k: v for k, v in graph.items() if k not in printed}
                break
        else:
            raise Exception()
# print(f) == 8
