from itertools import groupby
import unicodedata
from graphlib import TopologicalSorter

from kanjidb import KANJI, RawElement, RawStroke


FAKE = {
    '丿', '丨', '丶', None, '倠', '𦍒', '𠫯', 'CDP-8CB8', '亅'
}


def extract_elements(e):
    if isinstance(e, RawElement):
        yield e
        for c in e._filtered_children(lambda c: c.name in KANJI and c.name not in FAKE):
            yield from extract_elements(c)


raw_elements = []

for k in KANJI.values():
    raw_elements.extend(extract_elements(k.raw))


def group(it, key=None):
    return [list(g) for k, g in groupby(sorted(it, key=key), key=key)]


def children_key(e):
    # TODO we need to skip some children here. elements like 䍃 are not
    # useful -- they don't have meaning and also differ between kanji (揺 vs 徭)

    # maybe decide usefulness by the number of kanji it's present in?
    return tuple(
        ('s',) if type(c) is RawStroke else ('e', str(c.name))
        for c in e._filtered_children(lambda c: isinstance(c, RawStroke) or (c.name in KANJI and c.name not in FAKE and c.name != e.name)))


raw_element_parents = {}


def extract_elements_with_parent(e, p):
    if isinstance(e, RawElement):
        raw_element_parents[e] = p
        for c in e._filtered_children(lambda c: c.name in KANJI and c.name not in FAKE):
            extract_elements_with_parent(c, e)


for k in KANJI.values():
    extract_elements_with_parent(k.raw, k.raw)


def infer_elementspec(elem):
    errant_strokes = tuple(c for c in elem._filtered_children(lambda c: isinstance(c, RawStroke) or (c.name in KANJI and c.name not in FAKE)) if isinstance(c, RawStroke))
    errant_stroke_idxs = tuple(elem.strokes.index(s) + 1 for s in errant_strokes)

    elements = tuple(elem._filtered_children(lambda c: c.name in KANJI and c.name not in FAKE and c.name != elem.name))
    strokes_to_elements = {
        tuple(elem.strokes.index(s) + 1 for s in e.strokes): e.name
        for e in elements
    }

    no_overlap = sum(len(k) for k in strokes_to_elements) \
        == len(set(i for k in strokes_to_elements for i in k))
    no_split = all(set(k) == set(range(min(k), max(k) + 1)) for k in strokes_to_elements)
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
            return 'by_stroke_count', set(), elements_by[0]
        return 'by_elements', set(e.name for e in elements), *elements_by

    return 'by_strokes_to_elements', set(e.name for e in elements), strokes_to_elements, errant_stroke_idxs
    # ElementSpec(elem.name).by_strokes_to_elements(
    #     strokes_to_elements, errant_stroke_idxs)


def allowed_as_identifier(c):
    return unicodedata.category(c) in {'Lu', 'Ll', 'Lt', 'Lm', 'Lo', 'Nl'}


def encode(x):
    if isinstance(x, int):
        return str(x)
    if allowed_as_identifier(x):
        return x
    return f"ElementSpec('{x}')"


ts = TopologicalSorter()
content = {}


for g in group(raw_elements, key=lambda e: e.name):
    decomposed_identically = group(g, key=children_key)
    children_sets = []
    p = []
    for sg in decomposed_identically:
        elem = sg[0]
        method, children, *args = infer_elementspec(elem)
        children_sets.append(children)

        if allowed_as_identifier(elem.name):
            p.append(f'{elem.name} = ')
        if method == 'by_stroke_count':
            stroke_count, = args
            p.append(f"ElementSpec('{elem.name}').by_stroke_count({stroke_count})\n")
        elif method == 'by_elements':
            elements = ', '.join(encode(a) for a in args)
            p.append(f"ElementSpec('{elem.name}').by_elements({elements})\n")
        else:
            strokes_to_elements, errant_stroke_idxs = args
            p.append(f"ElementSpec('{elem.name}')")
            p.append(".by_strokes_to_elements({\n")
            for k, v in strokes_to_elements.items():
                p.append(f'    {k}: {encode(v)},\n')
            p.append('}')
            if errant_stroke_idxs:
                p.append(f', {errant_stroke_idxs}')
            p.append(')\n')

        same_parent = group(sg, key=lambda e: raw_element_parents[e].name)
        parent_with_kanjis = {raw_element_parents[ssg[0]].name: [e.kanji.spec.name for e in ssg] for ssg in same_parent}
        if len(decomposed_identically) == 1:
            del parent_with_kanjis[elem.name]
        direct_kanji_parents = [p for p, ks in parent_with_kanjis.items() if len(ks) == 1 and ks[0] == p]
        for par in direct_kanji_parents:
            del parent_with_kanjis[par]

        if direct_kanji_parents:
            p.append(f'# {" ".join(direct_kanji_parents)}\n')
        for par, ks in parent_with_kanjis.items():
            p.append(f'# {par} ({" ".join(ks)})\n')
    content[elem.name] = ''.join(p)

    # ts.add(elem.name, *max(children_sets, key=len))
    ts.add(elem.name, *set.intersection(*children_sets))


print('from kanjidb import ElementSpec\n')
for name in ts.static_order():
    print(content[name])


# TODO this is not the end -- we need to validate that we can correctly
# decompose every kanji, we could (will) have stroke mismatch
