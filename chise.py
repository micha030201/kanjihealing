import re
from pathlib import Path
from contextlib import suppress


DECOMPOSITION = {}


for filename in Path('ids').glob('*.txt'):
    with open(filename) as file:
        for line in file:
            line = line.strip()
            if ';;' not in line:
                m = re.match(
                    r'[^\t]+\t([^\t]+)(?:\t([^\t]+))?(?:\t@apparent=(.+?))?',
                    line)
                decomposition = m.group(3) or m.group(2) or ''
                decomposition = re.findall(
                    r'&.+?;|[^a-zA-Z0-9_-]', decomposition)
                decomposition = [
                    c for c in decomposition
                    if not (0x2FF0 <= ord(c[0]) <= 0x2FFF)]
                character = m.group(1)

                with suppress(ValueError):
                    decomposition.remove(character)

                if decomposition:
                    DECOMPOSITION[character] = decomposition
