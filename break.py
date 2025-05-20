import sys

from kanjidb import KANJI, inconsistent, children_key


k = KANJI[sys.argv[1]]

print(k.filename)
print(k.raw)

if sys.argv[1] in inconsistent:
    print('inconsistent decomposition')
    for sg in inconsistent[sys.argv[1]]:
        print(f'variant {children_key(sg[0])}')
        print('in kanji', ' '.join(e.kanji.spec.name for e in sg))
        print(sg[0])

print(k)
