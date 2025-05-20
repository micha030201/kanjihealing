from kanjidb import ElementSpec

E = ElementSpec


def c(name, stroke_count):
    ElementSpec(name).by_stroke_count(stroke_count)


ElementSpec('興').by_strokes_to_elements({
    (1, 2, 3, 4, 11, 12, 13): ElementSpec('𦥑'),
    (5, 6, 7, 8, 9, 10): ElementSpec('同'),
    (14,): ElementSpec('一'),
    (15, 16): ElementSpec('八')
})

ElementSpec('簔').by_elements(ElementSpec('竹'), ElementSpec('衰'))

E('口').by_stroke_count(3)
c('立', 5)
c('日', 4)
c('人', 2)
c('二', 2)
