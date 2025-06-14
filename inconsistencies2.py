from itertools import groupby

from kanjidb import KANJI, RawElement, RawStroke, ElementSpec


FAKE = {
    '丿', '丨', '丶', '一', None, '倠', '𦍒', '㐫', '昷', '雁', '𠔉', '吋',
    '𠫯', '厽', 'CDP-8CB8', '曷', '舄', '寍', '堇',
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
        #break

# TODO this is not the end -- we need to validate that we can correctly
# decompose every kanji, we could (will) have stroke mismatch
