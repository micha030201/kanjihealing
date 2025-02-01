from pprint import pprint
from pathlib import Path
from collections import defaultdict

from lxml import etree


# fuck xml. all my homies hate xml
SVG = '{http://www.w3.org/2000/svg}'
KVG = '{http://kanjivg.tagaini.net}'


files = list(Path('kanjivg/kanji').glob('?????.svg'))  # ignore variants

bare_elements = defaultdict(set)
decomposition = defaultdict(set)


# we're referring to the kanji element here, as kanjivg defines it. that
# it also happens to be an svg element is coincidental
def handle_element(parent_element: str, *gs: etree.Element):
    element = gs[0].get(KVG + 'element')
    if element is not None:
        decomposition[parent_element].add(element)
    else:
        element = parent_element
    # print(element)
    for g in gs:
        for child in g:
            if child.tag.endswith('g'):
                if child.get(KVG + 'part') == '1':
                    child_element = child.get(KVG + 'element')
                    handle_element(element, *g.xpath(
                        f'svg:g[@kvg:element="{child_element}"]',
                        namespaces={'svg': SVG.strip('}{'),
                                    'kvg': KVG.strip('}{')}))
                handle_element(element, child)
            elif child.tag.endswith('path'):
                if element is not parent_element:
                    bare_elements[element].add(parent_element)
            else:
                raise Exception(child.tag)


for file in files:
    # print(file)
    root = etree.parse(file).getroot()
    # g = root.xpath("//svg:g[@id and starts-with(@id, 'kvg:StrokePaths_07e4d')]",
    #                namespaces={'svg': 'http://www.w3.org/2000/svg'})
    g = root.xpath(f"//svg:g[@id='kvg:{file.stem}']",
                   namespaces={'svg': SVG.strip('}{')})
    handle_element(False, *g)

# print(len(bare_elements))
# pprint(dict(bare_elements))
pprint({k: v for k, v in bare_elements.items() if len(v) > 10})
