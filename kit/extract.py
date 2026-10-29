# -*- coding: utf-8 -*-
"""把一份资料（txt/md，比如从 docx 转出来的题目文件）抽成 quiz_bank.json。

支持两种常见排版：
  pta —— 题目正文里带「正确答案：X」；选项写成 "A. xxx" 独立行；填空用【①】占位
  md  —— 题目块后面跟「答案：X」/「解析：…」；选项写成 "- A. xxx" 或 "A. xxx"

用法：
  python extract.py 题库.txt -o quiz_bank.json --style auto --start-id 1 --chapter 1
"""
import argparse, json, re

MARK = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]')
OPT_LINE = re.compile(r'^\s*(?:[-*]\s*)?([A-Da-d])[\.．、]\s*(.+)$')
ANS_LINE = re.compile(r'^\s*(?:正确答案|答案|参考答案)\s*[:：]\s*(.+)$')
EXP_LINE = re.compile(r'^\s*解析\s*[:：]\s*(.+)$')
Q_HEAD = re.compile(r'^\s*(?:\d+[\.、)]|【\d+】|第\s*\d+\s*题|Q(?:uestion)?\s*\d+)\s*')


def _is_question_start(line):
    return bool(Q_HEAD.match(line)) and len(line.strip()) > 3


def split_blocks(text):
    lines = [ln.rstrip() for ln in text.splitlines()]
    blocks, cur = [], []
    for ln in lines:
        s = ln.strip()
        if not s:
            if cur:
                cur.append('')
            continue
        if _is_question_start(ln) and cur:
            # 只有当前块已经出现答案，才当成新题
            if any(ANS_LINE.match(x) for x in cur) or any('【①】' in x for x in cur):
                blocks.append('\n'.join(cur).strip())
                cur = []
        cur.append(ln)
    if cur:
        blocks.append('\n'.join(cur).strip())
    return [b for b in blocks if len(b.strip()) > 5]


def parse_block(block, qid, chapter):
    lines = block.splitlines()
    stem_lines, opts, answer, exp = [], [], '', ''
    in_opts = False
    for ln in lines:
        m = OPT_LINE.match(ln)
        m_ans = ANS_LINE.match(ln)
        m_exp = EXP_LINE.match(ln)
        if m_ans:
            answer = m_ans.group(1).strip()
            in_opts = False
            continue
        if m_exp:
            exp = m_exp.group(1).strip()
            continue
        if re.match(r'^\s*(?:正确答案|答案)\s*[:：]', ln) and not answer:
            continue
        if m and (in_opts or not stem_lines or len(opts) < 6):
            opts.append(ln.strip())
            in_opts = True
            continue
        if not answer:
            stem_lines.append(Q_HEAD.sub('', ln) if not stem_lines else ln)
    stem = '\n'.join(stem_lines).strip()
    if not stem:
        return None
    stem = Q_HEAD.sub('', stem, count=1)
    bare = re.sub(r'^\s*(正确答案|答案|参考答案)\s*[:：].*$', '', stem, flags=re.M).strip()

    if opts and answer:
        letters = re.findall(r'[A-D]', answer.upper())
        return {'id': qid, 'number': '', 'label': '', 'question': bare,
                'options': [o for o in opts], 'answer': answer + (('\n解析：' + exp) if exp else ''),
                'type': 'choice', 'points': 0, 'source': '', 'answer_source': '',
                'chapter': chapter, 'figures': [], 'answer_figures': []}

    n_mark = len(MARK.findall(bare))
    if n_mark and answer:
        return {'id': qid, 'number': '', 'label': '', 'question': bare, 'options': [],
                'answer': answer + (('\n解析：' + exp) if exp else ''), 'type': 'fill_blank',
                'points': 0, 'source': '', 'answer_source': '', 'chapter': chapter,
                'figures': [], 'answer_figures': []}

    return {'id': qid, 'number': '', 'label': '', 'question': bare, 'options': [],
            'answer': (answer or '') + (('\n' + exp) if exp else ''), 'type': 'subjective',
            'points': 0, 'source': '', 'answer_source': '', 'chapter': chapter,
            'figures': [], 'answer_figures': []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('-o', '--out', default='quiz_bank.json')
    ap.add_argument('--style', default='auto', choices=['auto', 'pta', 'md'])
    ap.add_argument('--start-id', type=int, default=1)
    ap.add_argument('--chapter', type=int, default=1)
    ap.add_argument('--prefix', default='q')
    a = ap.parse_args()

    text = open(a.src, encoding='utf-8', errors='replace').read()
    blocks = split_blocks(text)
    out = []
    for i, b in enumerate(blocks):
        qid = '%s%03d' % (a.prefix, a.start_id + i)
        item = parse_block(b, qid, a.chapter)
        if item:
            out.append(item)
    json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    kinds = {}
    for it in out:
        kinds[it['type']] = kinds.get(it['type'], 0) + 1
    print('blocks', len(blocks), '-> questions', len(out), kinds, '->', a.out)


if __name__ == '__main__':
    main()
