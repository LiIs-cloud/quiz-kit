# -*- coding: utf-8 -*-
"""把生成好的 PWA 目录发布到 GitHub Pages（走 Contents API，因为 git push 到 github.com 常被墙）。

用法：
  python publish.py subjects/c.json                # 仓库名默认 <id>-quiz
  python publish.py subjects/c.json --repo my-name # 指定仓库名
  python publish.py subjects/c.json --pages-only   # 只重开 Pages

依赖 gh 已登录且 token 有 repo 权限（gh auth status）。
"""
import base64, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
OWNER_DEFAULT = 'auto'


def gh(args, stdin=None):
    p = subprocess.run(['gh'] + args, capture_output=True, text=True, encoding='utf-8', input=stdin)
    return p.returncode, p.stdout, p.stderr


def gh_json(args, payload=None):
    cmd = ['gh', 'api'] + args + (['--input', '-'] if payload is not None else [])
    p = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                       input=(json.dumps(payload) if payload is not None else None))
    try:
        return json.loads(p.stdout)
    except Exception:
        return {'_err': (p.stderr or p.stdout)[:400]}


def ensure_repo(owner, repo):
    r = gh_json(['repos/%s/%s' % (owner, repo)])
    if '_err' in r or r.get('message') == 'Not Found':
        print('create repo', repo)
        gh_json(['--method', 'POST', 'user/repos'], {'name': repo, 'private': False,
                                                     'description': repo + ' - quiz site'})
        time.sleep(2)


def upload_file(owner, repo, branch, path, content_bytes, sha=None, msg=None):
    payload = {
        'message': msg or ('update ' + os.path.basename(path)),
        'content': base64.b64encode(content_bytes).decode(),
        'branch': branch,
    }
    if sha:
        payload['sha'] = sha
    return gh_json(['--method', 'PUT', 'repos/%s/%s/contents/%s' % (owner, repo, path)], payload)


def get_sha(owner, repo, path, branch='main'):
    r = gh_json(['repos/%s/%s/contents/%s?ref=%s' % (owner, repo, path, branch)])
    return r.get('sha') if isinstance(r, dict) else None


def upload_dir(owner, repo, folder, branch='main'):
    ok = []
    for fn in sorted(os.listdir(folder)):
        fp = os.path.join(folder, fn)
        if not os.path.isfile(fp):
            continue
        sha = get_sha(owner, repo, fn, branch)
        res = upload_file(owner, repo, branch, fn, open(fp, 'rb').read(), sha)
        state = 'ok' if isinstance(res, dict) and 'content' in res else 'FAIL'
        ok.append((fn, state))
        print(' ', fn, state)
    return ok


def enable_pages(owner, repo):
    cur = gh_json(['repos/%s/%s/pages' % (owner, repo)])
    if isinstance(cur, dict) and cur.get('html_url'):
        return cur['html_url']
    r = gh_json(['--method', 'POST', 'repos/%s/%s/pages' % (owner, repo)],
                {'source': {'branch': 'main', 'path': '/'}})
    if isinstance(r, dict) and r.get('html_url'):
        return r['html_url']
    cur = gh_json(['repos/%s/%s/pages' % (owner, repo)])
    if isinstance(cur, dict) and cur.get('html_url'):
        return cur['html_url']
    print('  pages error:', str(r)[:300])
    return None


def wait_up(url, tries=8):
    for i in range(tries):
        code = subprocess.run(['curl', '-s', '-o', 'NUL', '-w', '%{http_code}', '--max-time', '20', url],
                              capture_output=True, text=True).stdout.strip()
        print('  probe', i + 1, url, code)
        if code == '200':
            return True
        time.sleep(12)
    return False


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    flags = {a for a in sys.argv[1:] if a.startswith('--')}
    cfg = json.load(open(args[0] if os.path.isabs(args[0]) else os.path.join(HERE, args[0]), encoding='utf-8'))
    owner = cfg.get('owner') or os.environ.get('GH_OWNER') or OWNER_DEFAULT
    if owner == 'auto':
        owner = (gh_json(['user']).get('login') or OWNER_DEFAULT)
    repo = cfg.get('repo') or (cfg['id'] + '-quiz')

    pwa_dir = os.path.join(cfg['dir'], cfg.get('pwa_dir') or ('pwa_' + cfg['id']))
    if not os.path.isdir(pwa_dir):
        raise SystemExit('run build_site.py --pwa first, missing ' + pwa_dir)

    if '--pages-only' not in flags:
        ensure_repo(owner, repo)
        print('upload', pwa_dir, '->', owner + '/' + repo)
        upload_dir(owner, repo, pwa_dir)
    url = enable_pages(owner, repo)
    print('pages url', url)
    if url and wait_up(url):
        print('LIVE', url)
    return 0


if __name__ == '__main__':
    sys.exit(main())
