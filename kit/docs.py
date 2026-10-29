# -*- coding: utf-8 -*-
"""把资料（md / txt，含表格与代码）切成 docs.json，供答题页的「复习资料」抽屉使用。

支持的切分方式：
  res  —— 教材/讲义：标题为「第 X 章」「x.y」「附录 A」，识别管道表格与代码行
  lab  —— 实验报告：按「实验目的 / 实验内容 / 实验步骤 / 实验结果 …」切块
"""
import json, os, re

CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}

NOISE = re.compile(r'^\[[^\]]+\.(docx|doc|pdf|md)\s+p\.\d+\]\s*$')
LAB_MARK = re.compile(r'^(实验目的|实验内容|实验步骤|预习报告|实验原理|实验结果|实验分析|心得体会|实验总结|二、\s*实验仪器)')


def _is_table(line):
    return line.count(' | ') >= 1


def _is_code(line):
    s = line.strip()
    if not s or s.startswith('```'):
        return False
    if re.match(r'#include|#define|typedef|struct |void |int main|return |printf|scanf|'
                r'for\s*\(|while\s*\(|if\s*\(|else|switch|case |break;|continue;|[\{\}]', s):
        return True
    if s.endswith(';') and ('(' in s or '=' in s):
        return True
    return False


class Doc:
    def __init__(self, did, title):
        self.id, self.title, self.secs = did, title, []
        self.cur = None

    def sec(self, sid, no, title, level):
        self.cur = {'id': sid, 'no': no, 'title': title, 'level': level, 'body': []}
        self.secs.append(self.cur)

    def add_blocks(self, blocks):
        if not blocks:
            return
        if not self.cur:
            self.sec(self.id + '_top', '', self.title, 1)
        self.cur['body'].extend(blocks)


def _flush(blocks, buf, kind):
    if not buf:
        return
    text = '\n'.join(buf).strip('\n')
    if text.strip():
        blocks.append({'t': kind, 's': text})
    buf.clear()


def _read_lines(path):
    raw = open(path, encoding='utf-8', errors='replace').read().splitlines()
    return [ln for ln in raw if not NOISE.match(ln.strip())]


def parse_res(path, did, title):
    lines = _read_lines(path)
    d = Doc(did, title)
    blocks, buf, kind = [], [], 'p'
    started = False
    for line in lines:
        m = re.match(r'^#{0,3}\s*第\s*([一二三四五六七八九十]|\d+)\s*章\s*(.*)$', line.strip())
        if m:
            key = m.group(1)
            n = CN.get(key) or int(key)
            _flush(blocks, buf, kind); kind = 'p'
            d.add_blocks(blocks); blocks = []
            d.sec('ch%d' % n, '第%d章' % n, (m.group(2) or '').strip(), 1)
            started = True
            continue
        m = re.match(r'^#{0,3}\s*(\d+)\.(\d+)\s*(.*)$', line.strip())
        if m:
            _flush(blocks, buf, kind); kind = 'p'
            d.add_blocks(blocks); blocks = []
            d.sec('s%s_%s' % (m.group(1), m.group(2)), '%s.%s' % (m.group(1), m.group(2)), m.group(3).strip(), 2)
            started = True
            continue
        m = re.match(r'^#{0,3}\s*附录\s*([A-Za-z])\s*(.*)$', line.strip())
        if m:
            _flush(blocks, buf, kind); kind = 'p'
            d.add_blocks(blocks); blocks = []
            d.sec('apx' + m.group(1).upper(), '附录 ' + m.group(1).upper(), (m.group(2) or '').strip(), 1)
            continue
        m = re.match(r'^#{0,3}\s*([A-Za-z])\.(\d+)\s*(.*)$', line.strip())
        if m:
            _flush(blocks, buf, kind); kind = 'p'
            d.add_blocks(blocks); blocks = []
            d.sec('apx%s_%s' % (m.group(1).upper(), m.group(2)), '%s.%s' % (m.group(1).upper(), m.group(2)), m.group(3).strip(), 2)
            continue
        if not started and line.strip():
            # 序言（目录、使用说明）并入「开篇」
            if not d.secs:
                d.sec('intro', '', '开篇', 1)
            started = True
        if not line.strip():
            _flush(blocks, buf, kind); kind = 'p'
            continue
        k = 'tbl' if _is_table(line) else ('code' if _is_code(line) else 'p')
        if k != kind:
            _flush(blocks, buf, kind)
            kind = k
        buf.append(line)
    _flush(blocks, buf, kind)
    d.add_blocks(blocks)
    return d


def parse_lab(path, did, title):
    lines = _read_lines(path)
    d = Doc(did, title)
    blocks, buf, kind = [], [], 'p'
    d.sec(did + '_all', '', title, 1)
    seen = 0
    for line in lines:
        s = line.strip()
        if not s or re.match(r'^#\s*\d+\.', s):
            _flush(blocks, buf, kind); kind = 'p'
            continue
        if LAB_MARK.match(s):
            _flush(blocks, buf, kind); kind = 'p'
            d.add_blocks(blocks); blocks = []
            seen += 1
            if seen > 1:
                d.sec('%s_%d' % (did, seen), '', s[:40], 2)
        if s.startswith('```'):
            _flush(blocks, buf, kind)
            kind = 'code'
            continue
        k = 'tbl' if _is_table(line) else ('code' if _is_code(line) else 'p')
        if k != kind:
            _flush(blocks, buf, kind)
            kind = k
        buf.append(line)
    _flush(blocks, buf, kind)
    d.add_blocks(blocks)
    return d


PARSERS = {'res': parse_res, 'lab': parse_lab}


def build(docs_cfg, base_dir):
    """docs_cfg: [{'id','title','file','kind'}] -> docs 列表"""
    out = []
    for ent in docs_cfg:
        path = ent['file'] if os.path.isabs(ent['file']) else os.path.join(base_dir, ent['file'])
        d = PARSERS[ent.get('kind', 'res')](path, ent['id'], ent['title'])
        out.append({'id': d.id, 'title': d.title, 'secs': d.secs})
    return out


if __name__ == '__main__':
    import sys
    cfg = json.load(open(sys.argv[1], encoding='utf-8'))
    docs = build(cfg['docs'], os.path.dirname(cfg.get('_path', '.')))
    n = sum(len(''.join(b['s'] for b in s['body'])) for d in docs for s in d['secs'])
    print('docs', [(d['id'], len(d['secs'])) for d in docs], 'chars', n)
