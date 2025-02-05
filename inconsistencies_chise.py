from itertools import groupby

from kanjidb import KANJI, LogicalElement, LogicalStroke
from chise import DECOMPOSITION


def extract_elements(e):
    if isinstance(e, LogicalElement):
        yield e
        for c in e.children:
            yield from extract_elements(c)


elements = set()

for k in KANJI.values():
    elements.update(extract_elements(k))

element_names = {e.name for e in elements}

NORMALIZE = [
    *LogicalElement.NORMALIZE,
    '人𠆢',
    '犭⺨',
    '王𤣩',
    '日曰',
]

_equiv = {
    t: equiv_cls[0]
    for equiv_cls in NORMALIZE
    for t in equiv_cls}


def equiv(c):
    try:
        return _equiv[c]
    except KeyError:
        return c


def decompose(p, first=True):
    dec = DECOMPOSITION.get(p, [])
    if len(dec) == 1:
        yield dec[0]
    elif len(dec) == 0:
        if not first:
            yield p
    else:
        for c in dec:
            c = equiv(c)
            if c in element_names:
                yield c
            else:
                yield from decompose(c, first=False)


def print_elements(elements):
    print(' '.join([f'{e}({ord(e)})' if len(e) == 1 else e for e in elements]))


if __name__ == '__main__':
    whoopsies = 0

    for e in elements:
        elements_kanjivg = list(sorted([
            str(c.name)
            for c in e.children
            if type(c) is LogicalElement]))
        elements_chise = list(sorted(list(decompose(e.name))))
        if elements_kanjivg != elements_chise:
            whoopsies += 1
            print(e.kanji.name, e.name)
            print_elements(elements_kanjivg)
            print_elements(elements_chise)
            print('####################')

    print(whoopsies)


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
    '亞',  # the top is 冖 in 壺
    '菫',  # the top is 艹 in 菫 勤 but 廿 in 懃
    # '謁',  # has 匂 in 謁 but 匃 in 靄 藹
    '曷',  # has 匂 in 掲 謁 渇 褐 喝 but 曷 in 竭 鞨 碣 蝎 曷 靄 藹 羯 偈 蠍 歇 臈 遏 葛
    '堇',  # has 艹 in 謹 but 廿 in 槿 饉 瑾 覲 XXX also has 口 in 謹 but nowhere else
    '羲',  # XXX
}
