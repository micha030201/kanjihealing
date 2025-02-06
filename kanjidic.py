from lxml import etree

STROKE_COUNT = {}

root = etree.parse('kanjidic2.xml').getroot()
for element in root.iter('character'):
    STROKE_COUNT[element.xpath('literal')[0].text] = \
        int(element.xpath('misc/stroke_count')[0].text)
