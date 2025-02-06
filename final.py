from collections import defaultdict

from kanjidb import KANJI, LogicalElement, LogicalStroke
from kanjidic import STROKE_COUNT


def unnamed(_index=[0]):
    _index[0] += 1
    return f'<unnamed element #{_index[0]}>'


parents = defaultdict(set)


def extract_elements(e):
    if isinstance(e, LogicalElement):
        yield e
        for c in e.children:
            # if isinstance(c, LogicalElement):
            #     parents[c].add(e)
            yield from extract_elements(c)


# print(sum(all(type(c) is LogicalStroke for c in k.children) for k in KANJI.values()))


elements = defaultdict(list)

for k in KANJI.values():
    # for e in k.children:
    for e in extract_elements(k):
        if (
                isinstance(e, LogicalElement)
                and e.name != k.name
                and (e.name not in STROKE_COUNT
                     or all([type(c) is LogicalStroke for c in e.children]))):
            elements[e.name].append(k)

count = 0

for e, ks in sorted(elements.items(), key=lambda t: len(t[1])):
    # if any([type(c) is LogicalStroke for c in e.children]):
    #if len(ks) > 1:
    count += 1
    print(e, len(ks))
    # print(' '.join(k.name for k in ks))
    # print('###############')

print(count)
