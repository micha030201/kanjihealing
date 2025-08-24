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

    ElementSpec('龍').by_elements('立', '月', 7)
    ElementSpec('齧').by_elements('三', 1, '刀', '齒')
    ElementSpec('齊').by_elements('亠', 3, '刀', 4, '二', 1)
    ElementSpec('鼡').by_elements('⺍', '用')
    ElementSpec('白').by_elements(1, '日')
    # ElementSpec('頁').by_elements(2, '貝')
    # ElementSpec('百').by_elements(1, '白')
    ElementSpec('革').by_elements('廿', '口', '十')
    ElementSpec('貝').by_elements('目', '八')
    ElementSpec('豆').by_elements(1, '口', 3)
    ElementSpec('謁').by_elements('言', '日', '匂')
    ElementSpec('血').by_elements(1, '皿')
    ElementSpec('虫').by_elements('中', 2)
    ElementSpec('艹').by_stroke_count(3)
    ElementSpec('臼').by_stroke_count(6)
    ElementSpec('糸').by_stroke_count(6)
    ElementSpec('米').by_elements(2, '木')
    ElementSpec('章').by_elements('立', '早')
    ElementSpec('竜').by_elements('立', 5)
    ElementSpec('禾').by_elements(1, '木')
    ElementSpec('真').by_elements('十', '具')
    ElementSpec('目').by_stroke_count(5)
    ElementSpec('由').by_stroke_count(5)  # variant of 田?
    ElementSpec('田').by_stroke_count(5)
    ElementSpec('王').by_stroke_count(4)
    ElementSpec('玉').by_elements('王', 1)
    ElementSpec('玄').by_elements('亠', '幺')
    ElementSpec('之').by_elements('亠', 1)
    ElementSpec('羊').by_stroke_count(6)
    ElementSpec('罒').by_stroke_count(5)
    
