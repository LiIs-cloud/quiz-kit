# -*- coding: utf-8 -*-
"""把「题库模板」文档直接转成页面用的题库 JSON。

支持 .md / .txt / .docx（Word 里照模板写也行）。模板见 kit/bank_template.md：
每题一个 `## 题号 | 第X章 | 题型` 标题，选项写 `A. xxx`，答案写「答案：」，解析写「解析：」。

用法：
  python kit/make_bank.py 我的题库.md -o 我的科目/quiz_bank.json
  python kit/make_bank.py 题库.docx -o quiz_bank.json --start-id 1 --prefix q
"""
import argparse, json, os, re

HEAD = re.compile(r'^#{1,3}\s*(.*)$')
OPT = re.compile(r'^\s*([A-Za-z])\s*[.．、)）]\s*(.+)$')
ANS = re.compile(r'^\s*(?:正确答案|参考答案|答案)\s*[:：]\s*(.*)$')
EXP = re.compile(r'^\s*解析\s*[:：]\s*(.*)$')
BLANK = re.compile(r'_{2,}|＿{2,}|【[①②③④⑤⑥⑦⑧⑨⑩]】')
MARK = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]')
CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}

TYPE_MAP = [
    (r'判断|对错|true|false', 'choice'),
    (r'选择|单选|多选|单项|不定项', 'choice'),
    (r'填空|填|计算|程序填空', 'fill'),
    (r'简答|问答|编程|综合|应用|设计|分析|论述', 'subj'),
]


def read_text(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.docx':
        from docx import Document
        doc = Document(path)
        out = []
        for p in doc.paragraphs:
            out.append(p.text)
        for t in doc.tables:
            for row in t.rows:
                out.append(' | '.join(c.text for c in row.cells))
        return '\n'.join(out)
    return open(path, encoding='utf-8', errors='replace').read()


def split_blocks(text):
    blocks, cur = [], None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m and not line.lstrip().startswith('###'):
            if cur:
                blocks.append(cur)
            cur = {'head': m.group(1).strip(), 'lines': []}
            continue
        if cur is not None:
            cur['lines'].append(line)
    if cur:
        blocks.append(cur)
    return blocks


def parse_head(head):
    parts = [p.strip() for p in re.split(r'[|｜]', head) if p.strip()]
    no, chapter, qtype = '', '', ''
    for p in parts:
        if not no and re.match(r'^[\w\-]+$', p) and not re.match(r'^(第|\d+章)', p):
            no = p
            continue
        if not chapter and re.match(r'^(第\s*[一二三四五六七八九十\d]+\s*章|ch\d+)$', p, re.I):
            chapter = p
            continue
        if not qtype:
            qtype = p
    return no, chapter, qtype


def chapter_no(s):
    if isinstance(s, int):
        return s
    m = re.search(r'ch(\d+)', str(s), re.I)
    if m:
        return int(m.group(1))
    m = re.search(r'第\s*([一二三四五六七八九十\d]+)\s*章', str(s))
    if not m:
        m = re.search(r'(\d+)', str(s))
        return int(m.group(1)) if m else 1
    k = m.group(1)
    return CN.get(k) or int(k)


def detect_type(qtype, opts, stem, answer):
    for rx, t in TYPE_MAP:
        if qtype and re.search(rx, qtype):
            return t
    if len(opts) >= 2:
        return 'choice'
    if BLANK.search(stem) and answer:
        return 'fill'
    if answer and len(answer) > 40:
        return 'subj'
    if answer:
        return 'fill'
    return 'subj'


def norm_parts(answer, stem, n_marks):
    body = MARK.sub('', answer).strip()
    parts = [p.strip(' 。.；;') for p in re.split(r'[；;、]| {2,}', body) if p.strip()]
    if n_marks and len(parts) != n_marks:
        alt = [p.strip() for p in re.split(r'\s+', body) if p.strip()]
        if len(alt) == n_marks:
            return alt
    return parts


def build_item(idx, block, prefix, start_id, chapter_default):
    no, chapter, qtype = parse_head(block['head'])
    stem, opts, answer, exp = [], [], '', ''
    mode = 'stem'
    for raw in block['lines']:
        line = raw.rstrip()
        s = line.strip()
        m_ans, m_exp = ANS.match(line), EXP.match(line)
        if m_exp:
            mode = 'exp'
            exp = (exp + '\n' + m_exp.group(1)).strip()
            continue
        if m_ans:
            mode = 'answer'
            answer = (answer + '\n' + m_ans.group(1)).strip()
            continue
        if not s:
            if mode == 'stem' and stem and stem[-1] != '':
                stem.append('')
            elif mode != 'stem':
                (exp if mode == 'exp' else answer)  # 保留空行
            continue
        m_opt = OPT.match(line)
        if m_opt and mode == 'stem' and not (s.startswith('解析') or s.startswith('答案')):
            opts.append({'k': m_opt.group(1).upper(), 't': m_opt.group(2).strip()})
            continue
        if mode == 'exp':
            exp = (exp + '\n' + s).strip()
        elif mode == 'answer':
            answer = (answer + '\n' + s).strip()
        else:
            stem.append(s)

    text = '\n'.join(stem).strip()
    if not text:
        return None
    qtype = detect_type(qtype, opts, text, answer)
    chapter_n = chapter_no(chapter) if chapter else chapter_default
    qid = '%s%03d' % (prefix, start_id + idx)
    item = {'id': qid, 'ch': chapter_n, 'type': qtype, 'text': text}

    if qtype == 'choice':
        letters = re.findall(r'[A-Za-z]', answer.split('\n')[0]) if answer else []
        if opts:
            item['opts'] = opts
        if not letters and answer:
            if re.search(r'正确|√|对|true', answer, re.I):
                item['correct'] = [opts[0]['k'] if opts else 'A']
            elif re.search(r'错误|×|错|false', answer, re.I):
                item['correct'] = [opts[1]['k'] if len(opts) > 1 else 'B']
        if letters:
            item['correct'] = sorted({l.upper() for l in letters})
        if exp:
            item['exp'] = exp
        return item

    if qtype == 'fill':
        n_marks = len(BLANK.findall(text)) or len(MARK.findall(block['head'] + text))
        parts = norm_parts(answer, text, n_marks)
        if not parts:
            return None
        item['blank'] = len(parts)
        item['parts'] = parts
        item['answer'] = '；'.join(parts)
        if exp:
            item['exp'] = exp
        return item

    item['answer'] = (answer + (('\n\n' + exp) if exp else '')).strip()
    return item


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--out', default='quiz_bank.json')
    ap.add_argument('--start-id', type=int, default=1)
    ap.add_argument('--prefix', default='q')
    ap.add_argument('--chapter', type=int, default=1, help='标题里没写章节时用这个')
    a = ap.parse_args()

    blocks = split_blocks(read_text(a.src))
    items, skipped = [], 0
    for i, b in enumerate(blocks):
        it = build_item(len(items), b, a.prefix, a.start_id, a.chapter)
        if it:
            items.append(it)
        else:
            skipped += 1
    json.dump(items, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    kinds = {}
    for it in items:
        kinds[it['type']] = kinds.get(it['type'], 0) + 1
    chapters = {}
    for it in items:
        chapters[it['ch']] = chapters.get(it['ch'], 0) + 1
    print('blocks', len(blocks), '-> questions', len(items), kinds,
          '| chapters', dict(sorted(chapters.items())), '| skipped', skipped)
    print('->', a.out)


if __name__ == '__main__':
    main()
