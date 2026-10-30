import json, re, glob

with open('translate_map.json', encoding='utf-8') as f:
    DICT = json.load(f)

files = glob.glob('src/frontend/src/**/*.ts', recursive=True) + \
        glob.glob('src/frontend/src/**/*.js', recursive=True) + \
        glob.glob('src/frontend/src/**/*.vue', recursive=True)
files = [f for f in files if '__tests__' not in f]

total = 0
for fn in files:
    s = open(fn, encoding='utf-8').read()
    new = s
    for orig, zh in DICT.items():
        if orig not in new:
            continue
        # only replace when orig is a quoted string literal: 'orig' "orig" `orig`
        pat = r"([\"'`])" + re.escape(orig) + r"\1"
        def repl(m, zh=zh):
            return m.group(1) + zh + m.group(1)
        new, n = re.subn(pat, repl, new)
        total += n
    if new != s:
        open(fn, 'w', encoding='utf-8').write(new)

print("total literal replacements:", total)
# show which dict keys still unmatched anywhere (likely dynamic/code-only)
found = set()
for fn in files:
    s = open(fn, encoding='utf-8').read()
    for k in DICT:
        if k in s:
            found.add(k)
still = [k for k in DICT if k not in found]
print("still unmatched keys:", len(still))
for k in still:
    print("  ", repr(k))
