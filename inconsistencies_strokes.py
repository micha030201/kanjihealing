from itertools import groupby

from kanjidb import KANJI, LogicalElement, LogicalStroke


def unnamed(_index=[0]):
    _index[0] += 1
    return f'<unnamed element #{_index[0]}>'


def extract_elements(e):
    if isinstance(e, LogicalElement):
        yield e
        for c in e.children:
            #print(e.raw, c.raw)
            yield from extract_elements(c)


elements = []

for k in KANJI.values():
    # print(k.filename.stem)
    # # print(list(k.raw.children))
    # print(k)
    # print(k.filename)
    elements.extend(extract_elements(k))


def group(it, key=None):
    return [list(g) for k, g in groupby(sorted(it, key=key), key=key)]


def children_key(e):
    # return tuple(
    #     ('s', str(c.name)) if type(c) is LogicalStroke else ('e', str(c.name))
    #     for c in e.children)
    # return tuple(
    #     ('s',) if type(c) is LogicalStroke else ('e', str(c.name))
    #     for c in e.children)
    # return tuple(
    #     str(c.name)
    #     for c in e.children
    #     if type(c) is LogicalElement)

    # return sorted(tuple(
    #     str(c.name)
    #     for c in e.children
    #     if type(c) is LogicalElement))

    return len([1 for c in e.children if type(c) is LogicalStroke])


whoopsies = 0

exceptions = {
    # '𦥑',
    '𢦏',  # can't decide if it's 十 or 土
    # '齊',
    '鳥',  # sometimes written without the bottom 4 strokes
    # '闌',  # the line in the middle can be split in two, not an error
    '走', '足',  # often look like 止, but ig it's semantic or whatever
    # '襄',  # this one is a mf
    # '長',  # sometimes contains ム
    '益',  # used only in variant form
    '歴',  # sometimes tree has top stroke
    '呉',  # the bottom part is ocassionally an 大
    # '亞',  # the top is 冖 in 壺
    '菫',  # the top is 艹 in 菫 勤 but 廿 in 懃
    # '謁',  # has 匂 in 謁 but 匃 in 靄 藹
    '曷',  # has 匂 in 掲 謁 渇 褐 喝 but 曷 in 竭 鞨 碣 蝎 曷 靄 藹 羯 偈 蠍 歇 臈 遏 葛
    '堇',  # has 艹 in 謹 but 廿 in 槿 饉 瑾 覲 XXX also has 口 in 謹 but nowhere else
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
            print(*[e.kanji.filename for e in g2])
            print(*[e.kanji.filename.stem for e in g2], sep=', ')
            print(children_key(g2[0]), ''.join([c.name or '　' for c in g2[0].children if type(c) is LogicalStroke]))
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
