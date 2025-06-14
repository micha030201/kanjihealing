def spec(ElementSpec):
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
    c('⺍', 3)
    c('⻌', 3)

    E('㐄').by_stroke_count(4)
    E('㐄', 1).by_stroke_count(3)
    E('舛').by_elements('夕', E('㐄', 1))

    c('一', 1)
    c('丁', 2)
    c('七', 2)
    c('三', 3)

    E('烝').by_elements('丞', '灬')
    E('丞').by_strokes_to_elements({
        (1, 2): '了',
        (2, 3, 4, 5): '水',
        (6): '一'
    })
    E('両').by_elements('一', '冂', '山')

    E('hat2').by_stroke_count(3)
    E('並').by_elements('hat2', '业')

    E('主').by_elements(1, '王')
    E('主', 1).by_strokes_to_elements({
        (1, 2): '亠',
        (2, 3, 4, 5): '王'
    })
