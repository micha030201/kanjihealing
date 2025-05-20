import sys

from kanjidb import KANJI


k = KANJI[sys.argv[1]]

print(k.filename)
print(k.raw)

print(k)
