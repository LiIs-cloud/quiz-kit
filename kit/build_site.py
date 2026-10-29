# -*- coding: utf-8 -*-
"""按「学科配置 + 题库」生成一个可离线使用的复习/答题网页。

用法：
  python build_site.py subjects/c.json            # 只生成 HTML
  python build_site.py subjects/c.json --pwa      # 同时生成可安装的 PWA 目录

配置见 subjects/*.json；题库统一用字段 id/ch/type/text/opts/correct/parts/answer/exp。
原始题库（quiz_bank.json）由 extract.py 或人工整理产生，build_site.py 负责清洗成页面数据。
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import docs as docslib

# ---------------------------------------------------------------- 清洗器

def _strip_ch(t):
    return re.sub(r'（第\d+章）\s*$', '', t).strip()


def _parse_choice_ds(q):
    lines = [l.strip() for l in q['answer'].split('\n') if l.strip()]
    head = lines[0] if lines else ''
    m = re.match(r'^[（(]?([A-Da-d])[）)]?', head)
    return (m.group(1).upper() if m else ''), '\n'.join(lines[1:]).strip()


def _parse_opts(opts):
    out = []
    for o in opts:
        m = re.match(r'^\s*([A-Da-d])[\.．、]\s*(.*)$', o, re.S)
        if m:
            out.append({'k': m.group(1).upper(), 't': m.group(2).strip()})
        else:
            out.append({'k': chr(65 + len(out)), 't': o.strip()})
    return out


def _blank_count(text):
    return len(re.findall(r'_{2,}|＿{2,}', text))


def clean_ds(raw, cfg):
    items = []
    for q in raw:
        t = q['type']
        text = _strip_ch(q['question'])
        ans = q['answer'].strip()
        if t == 'choice':
            letter, exp = _parse_choice_ds(q)
            items.append({'id': q['id'], 'ch': q['chapter'], 'type': 'choice', 'text': text,
                          'opts': _parse_opts(q['options']), 'correct': [letter], 'exp': exp})
        elif t == 'fill_blank':
            n = _blank_count(q['question'])
            parts = ans.split()
            if len(parts) != n:
                parts = None
            items.append({'id': q['id'], 'ch': q['chapter'], 'type': 'fill', 'text': text,
                          'blank': n, 'parts': parts, 'answer': ans})
        else:
            items.append({'id': q['id'], 'ch': q['chapter'], 'type': 'subj', 'text': text, 'answer': ans})
    items += cfg.get('extra_items', [])
    return items


MARK = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]')
CODE_HINT = re.compile(r'参考代码|参考程序')
PTA_NOISE = re.compile(r'^(在这里给出一组输入|在这里给出相应的输出|请在这里写输入格式|请在这里描述输出格式|请在这里写题目描述|输入样例:|输出样例:|输入格式:|输出格式:)\s*')


def _normalize_stem(text):
    keep = [ln.rstrip() for ln in text.splitlines() if not PTA_NOISE.match(ln.strip())]
    out, blank = [], False
    for ln in keep:
        if not ln.strip():
            if blank:
                continue
            blank = True
            out.append('')
        else:
            blank = False
            out.append(ln)
    return '\n'.join(out).strip()


def _split_parts(correct, n):
    body = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*', '', correct.strip())
    parts = [re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩\s]+', '', p).strip() for p in re.split(r'[；;]\s*', body)]
    parts = [p for p in parts if p]
    if not parts:
        return None
    if n and len(parts) != n:
        parts = parts[:n] if len(parts) > n else parts + [''] * (n - len(parts))
    return parts


def clean_pta(raw, cfg):
    """PTA 风格：题干尾部带「正确答案：X」，填空用【①】，编程题带「参考代码」。"""
    items = []
    skip = tuple(cfg.get('skip_keywords', []))
    for q in raw:
        text_q = q['question']
        if any(k in text_q for k in skip):
            continue
        m = re.search(r'正确答案：(.+)$', text_q, flags=re.S)
        correct = (m.group(1).strip() if m else '')
        stem = re.sub(r'正确答案：.*$', '', text_q, flags=re.S)
        stem = re.sub(r'\s*\u3000?（\d+\s*分）\s*$', '', stem).strip()
        expl = re.sub(r'\n?你的作答[:：].*$', '', q.get('answer', ''), flags=re.S).strip()
        base = {'id': q['id'], 'ch': 0, 'text': _normalize_stem(stem)}
        blob = stem + ' ' + ' '.join(q.get('options') or [])
        if q['type'] == 'choice':
            letter = re.search(r'[A-D]', correct)
            it = dict(base, type='choice', opts=_parse_opts(q.get('options') or []),
                      correct=[letter.group(0) if letter else ''], exp=expl)
        elif CODE_HINT.search(text_q) or '输入格式' in text_q:
            code, stem_only = '', text_q
            for kw in ('参考代码', '参考程序'):
                if kw in text_q:
                    stem_only, code = text_q.split(kw, 1)
                    code = code.lstrip('：: \n')
                    break
            it = dict(base, type='subj', text=_normalize_stem(stem_only),
                      answer=(('参考代码：\n' + code.strip()) if code.strip() else expl))
        else:
            n = len(MARK.findall(stem))
            parts = _split_parts(correct, n) if correct else None
            if parts and (n == 0 or len(parts) == n):
                it = dict(base, type='fill', blank=len(parts), parts=parts, answer='；'.join(parts))
                if expl:
                    it['exp'] = expl
            else:
                it = dict(base, type='subj', answer=(correct + ('\n' + expl if expl else '')).strip())
        it['_blob'] = blob
        items.append(it)
    return items


CLEANERS = {'ds': clean_ds, 'pta': clean_pta}


def assign_kp(items, cfg):
    rules = [(r, n) for r, n in cfg.get('kp_rules', [])]
    groups = cfg.get('kp_groups', [])
    known = {n for _, names in groups for n in names}
    secondary = cfg.get('kp_secondary')
    for it in items:
        if 'kp' in it and it['kp']:
            continue
        blob = it.get('_blob') or (it['text'] + ' ' + it.get('answer', '') + ' ' + it.get('exp', '') +
                                   ' ' + ' '.join(o['t'] for o in it.get('opts', [])))
        primary = None
        for rx, name in rules:
            if re.search(rx, blob, re.I):
                primary = name
                break
        kps = [primary] if primary else ['其他']
        if secondary and re.search(secondary['regex'], blob) and primary != secondary['add']:
            kps.append(secondary['add'])
        it['kp'] = kps
        it.pop('_blob', None)
    return known


def apply_chapters(items, cfg):
    """按 regex 规则给题目分章；配置 chapters 里没写规则的就沿用原始 chapter。"""
    rules = [(r, n) for r, n in cfg.get('chapter_rules', [])]
    for it in items:
        if not rules:
            break
        blob = it['text'] + ' ' + ' '.join(o['t'] for o in it.get('opts', []))
        for rx, n in rules:
            if re.search(rx, blob):
                it['ch'] = n
                break
        else:
            it.setdefault('ch', 1)
    return items


# ---------------------------------------------------------------- 渲染

def render(cfg, items, docs):
    base = cfg['dir']
    app_js = open(os.path.join(HERE, 'app.js'), encoding='utf-8').read()
    html = open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()

    kp_meta = [{'n': n, 'g': g} for g, names in cfg.get('kp_groups', []) for n in names]
    tabs = [['all', '全部']]
    for ch in cfg.get('chapters', []):
        tabs.append(['ch%d' % ch['n'], ch.get('label') or ('第%d章' % ch['n'])])
    tabs += cfg.get('extra_tabs', [])

    js = app_js
    js = js.replace('__DATA__', json.dumps(items, ensure_ascii=False, separators=(',', ':')))
    js = js.replace('__KPMETA__', json.dumps(kp_meta, ensure_ascii=False, separators=(',', ':')))
    js = js.replace('__LSKEY__', "'%s'" % cfg.get('storage_key', 'quiz_v1'))
    js = js.replace('__CHTABS__', json.dumps(tabs, ensure_ascii=False, separators=(',', ':')))
    js = js.replace('__DOCS__', json.dumps(docs, ensure_ascii=False, separators=(',', ':')))
    js = js.replace('__KPDOC__', json.dumps(cfg.get('kp_doc', {}), ensure_ascii=False, separators=(',', ':')))

    n = len(items)
    sub = cfg.get('subtitle') or ('%d 题' % n)
    sub = sub.replace('{n}', str(n))
    html = html.replace('__SCRIPT__', js)
    html = html.replace('__TITLE__', '%s · %d 题' % (cfg['name'], n))
    html = html.replace('__BRAND__', cfg['name'])
    html = html.replace('__SUB__', sub)

    out = os.path.join(base, cfg['out'])
    os.makedirs(os.path.dirname(out) or base, exist_ok=True)
    open(out, 'w', encoding='utf-8').write(html)
    return out, n


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    if not args:
        print('usage: build_site.py subjects/<name>.json [--pwa]')
        return 2
    cfg_path = args[0]
    if not os.path.isabs(cfg_path):
        cand = os.path.abspath(cfg_path)
        cfg_path = cand if os.path.exists(cand) else os.path.join(HERE, cfg_path)
    cfg = json.load(open(cfg_path, encoding='utf-8'))
    base = cfg['dir']
    if not os.path.isabs(base):
        base = os.path.normpath(os.path.join(os.path.dirname(cfg_path), base))
    cfg['dir'] = base

    bank_path = os.path.join(base, cfg['bank'])
    raw = json.load(open(bank_path, encoding='utf-8'))
    cleaner = cfg.get('cleaner') or 'none'
    items = raw if cleaner == 'none' else CLEANERS[cleaner](raw, cfg)
    for it in items:
        it.setdefault('ch', 1)
    assign_kp(items, cfg)
    apply_chapters(items, cfg)

    if cfg.get('docs_file'):
        dpath = cfg['docs_file']
        docs = json.load(open(dpath if os.path.isabs(dpath) else os.path.join(base, dpath), encoding='utf-8'))
    else:
        docs = docslib.build(cfg.get('docs', []), base) if cfg.get('docs') else []
    cfg['count'] = str(len(items))
    out, n = render(cfg, items, docs)
    dist = {}
    for it in items:
        dist[it['ch']] = dist.get(it['ch'], 0) + 1
    print('built', out, '| questions', n, '| chapters', dict(sorted(dist.items())),
          '| docs', [(d['id'], len(d['secs'])) for d in docs])

    if '--pwa' in flags:
        import pwa
        p = pwa.build(cfg, out)
        print('pwa', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
