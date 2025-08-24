from itertools import groupby

from kanjidb import KANJI, RawElement, RawStroke, ElementSpec


FAKE = {
    '丿', '丨', '丶', '一', None, '倠', '𦍒', '㐫', '昷', '雁', '𠔉', '吋',
    '𠫯', '厽', 'CDP-8CB8', '曷', '舄', '寍', '堇', '亅'
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


def unnamed(_index=[0]):
    _index[0] += 1
    return f'<unnamed element #{_index[0]}>'


def children_key(e):
    # TODO we need to skip some children here. elements like 䍃 are not
    # useful -- they don't have meaning and also differ between kanji (揺 vs 徭)

    # maybe decide usefulness by the number of kanji it's present in?
    return tuple(
        ('s',) if type(c) is RawStroke else ('e', str(c.name))
        for c in e._filtered_children(lambda c: c.name in KANJI and c.name not in FAKE))


import specinfo
specinfo.spec(ElementSpec)


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

    elements = tuple(elem._filtered_children(lambda c: c.name in KANJI and c.name not in FAKE))
    strokes_to_elements = {
        tuple(elem.strokes.index(s) + 1 for s in e.strokes): e.name
        for e in elements
    }

    no_overlap = sum(len(k) for k in strokes_to_elements) \
        == len(set(i for k in strokes_to_elements for i in k))
    no_split = all(set(k) == set(range(min(k), max(k) + 1)) for k in strokes_to_elements)
    if no_overlap and no_split:
        elements = [0]
        stroke_to_element = {
            i: e
            for idxs, e in strokes_to_elements.items()
            for i in idxs
        }
        for i in range(1, len(elem.strokes) + 1):
            e = stroke_to_element.get(i, None)
            if e is None:
                if isinstance(elements[-1], int):
                    elements[-1] += 1
                else:
                    elements.append(1)
            else:
                if elements[-1] != e:
                    elements.append(e)

        if elements[0] == 0:
            elements = elements[1:]

        if len(elements) == 1 and isinstance(elements[0], int):
            return 'by_stroke_count', elements[0]
        return 'by_elements', *elements

    return 'by_strokes_to_elements', strokes_to_elements, errant_stroke_idxs
    # ElementSpec(elem.name).by_strokes_to_elements(
    #     strokes_to_elements, errant_stroke_idxs)


for g in group(raw_elements, key=lambda e: e.name or unnamed()):
    decomposed_identically = group(g, key=children_key)
    # g[any]
    elem = g[0]

    specced_elem_names = {n.name for n in ElementSpec._DATA}
    if elem.name is None or elem.name in specced_elem_names:
        continue
    if len(decomposed_identically) == 1:
        # print(f'assuming decomposition {g[0]} for {g[0].name}')
        method, *args = infer_elementspec(elem)
        getattr(ElementSpec(elem.name), method)(*args)
    else:
        print(f'inconsistent decomposition: {g[0].name}')
        for sg in decomposed_identically:
            elem = sg[0]
            method, *args = infer_elementspec(elem)
            joined_args = ', '.join(repr(a) for a in args)
            print(f"ElementSpec('{elem.name}').{method}({joined_args})")
            # TODO write parent decomposition? to speed up the process
            same_parent = group(sg, key=lambda e: raw_element_parents[e].name or '<unnamed>')
            print(' with parents', ' '.join((raw_element_parents[ssg[0]].name or '<unnamed>') + '(' + ' '.join(e.kanji.spec.name for e in ssg) + ')' for ssg in same_parent))
            # print(sg[0])
        print()
        #break

# TODO this is not the end -- we need to validate that we can correctly
# decompose every kanji, we could (will) have stroke mismatch
