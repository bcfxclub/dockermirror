import json, re, glob, sys

with open('translate_map.json', encoding='utf-8') as f:
    DICT = json.load(f)

ATTRS = ['placeholder', 'title', 'aria-label', 'label', 'alt']
attr_pats = [r'(%s)="([^"]*)"' % a for a in ATTRS] + \
            [r'(:%s)="([^"]*)"' % a for a in ATTRS]

text_re = re.compile(r'>([^<>{}\|@%#][^<>{}\|@%#]*?[A-Za-z][^<>{}\|@%#]*?)<')
attr_res = [re.compile(p) for p in attr_pats]

def tnode(m):
    v = m.group(1)
    if v in DICT:
        return '>%s<' % DICT[v]
    return m.group(0)

def attr_repl(m):
    pre, val = m.group(1), m.group(2)
    if val in DICT:
        return '%s="%s"' % (pre, DICT[val])
    return m.group(0)

files = glob.glob('src/frontend/src/**/*.vue', recursive=True)
changed = 0
for fn in files:
    s = open(fn, encoding='utf-8').read()
    tm = re.search(r'<template>(.*?)</template>', s, re.S)
    if not tm:
        continue
    orig_tpl = tm.group(1)
    new_tpl = orig_tpl
    new_tpl = text_re.sub(tnode, new_tpl)
    for ar in attr_res:
        new_tpl = ar.sub(attr_repl, new_tpl)
    if new_tpl != orig_tpl:
        s = s[:tm.start(1)] + new_tpl + s[tm.end(1):]
        open(fn, 'w', encoding='utf-8').write(s)
        changed += 1

print("templates updated:", changed)
found = set()
for fn in files:
    s = open(fn, encoding='utf-8').read()
    for k in DICT:
        if k in s:
            found.add(k)
missing = [k for k in DICT if k not in found]
print("dict keys not present in any .vue:", len(missing))
for k in missing[:50]:
    print("  missing:", repr(k))
