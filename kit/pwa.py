# -*- coding: utf-8 -*-
"""把 build_site.py 生成的单文件页面包成可安装 PWA：index.html + manifest + sw.js + 图标。"""
import os
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [r'C:\Windows\Fonts\msyhbd.ttc', r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\simhei.ttf']


def _font(size):
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make_icon(size, label, accent=(56, 189, 248), maskable=False):
    img = Image.new('RGBA', (size, size), (15, 17, 21, 255))
    d = ImageDraw.Draw(img)
    pad = size * (0.14 if maskable else 0.09)
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=size * 0.2,
                        fill=(28, 38, 52, 255), outline=accent + (140,), width=max(2, size // 96))
    f = _font(int(size * 0.44))
    bbox = d.textbbox((0, 0), label, font=f)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), label, font=f, fill=(236, 242, 248, 255))
    return img


def build(cfg, html_path):
    out = os.path.join(cfg['dir'], cfg.get('pwa_dir') or ('pwa_' + cfg['id']))
    os.makedirs(out, exist_ok=True)
    label = cfg.get('icon_label') or cfg.get('short', 'Q')[:1]
    accent = tuple(cfg.get('icon_color') or (56, 189, 248))

    for s, mask in ((192, False), (512, False), (512, True), (180, False)):
        icon = make_icon(s, label, accent, maskable=mask)
        if s == 180:
            icon.save(os.path.join(out, 'apple-touch-icon.png'))
        elif mask:
            icon.save(os.path.join(out, 'icon-maskable-512.png'))
        else:
            icon.save(os.path.join(out, 'icon-%d.png' % s))

    name = cfg['name']
    short = cfg.get('short') or name
    theme = cfg.get('theme', '#0f1115')
    cache = cfg.get('cache') or (cfg['id'] + '-v1')
    n = cfg.get('count') or ''
    manifest = {
        'name': '%s · %s 题' % (name, n) if n else name,
        'short_name': short,
        'start_url': './index.html',
        'scope': './',
        'display': 'standalone',
        'orientation': 'portrait',
        'background_color': theme,
        'theme_color': theme,
        'lang': 'zh-CN',
        'description': cfg.get('description', name),
        'icons': [
            {'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png'},
            {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png'},
            {'src': 'icon-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }
    open(os.path.join(out, 'manifest.webmanifest'), 'w', encoding='utf-8').write(
        json_dumps(manifest))

    sw = '''const CACHE = '%s';
const ASSETS = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './apple-touch-icon.png'];
self.addEventListener('install', e => {
  self.skipWaiting();
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).catch(() => {}));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  if (req.mode === 'navigate' || (req.headers.get('accept') || '').indexOf('text/html') >= 0) {
    e.respondWith(fetch(req).then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put('./index.html', cp)); return r; })
      .catch(() => caches.match('./index.html').then(r => r || caches.match('./'))));
    return;
  }
  e.respondWith(caches.match(req).then(r => r || fetch(req).then(resp => {
    const cp = resp.clone(); caches.open(CACHE).then(c => c.put(req, cp)); return resp;
  }).catch(() => r)));
});
''' % cache
    open(os.path.join(out, 'sw.js'), 'w', encoding='utf-8').write(sw)

    html = open(html_path, encoding='utf-8').read()
    head_add = ('<link rel="manifest" href="manifest.webmanifest">\n'
                '<meta name="theme-color" content="%s">\n'
                '<meta name="mobile-web-app-capable" content="yes">\n'
                '<meta name="apple-mobile-web-app-capable" content="yes">\n'
                '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">\n'
                '<meta name="apple-mobile-web-app-title" content="%s">\n'
                '<link rel="apple-touch-icon" href="apple-touch-icon.png">\n') % (theme, short)
    if 'manifest.webmanifest' not in html:
        html = html.replace('</head>', head_add + '</head>', 1)
    reg = ('<script>\nif (\'serviceWorker\' in navigator && (location.protocol === \'https:\' || '
           'location.hostname === \'localhost\' || location.hostname === \'127.0.0.1\')) {\n'
           '  window.addEventListener(\'load\', () => navigator.serviceWorker.register(\'sw.js\').catch(() => {}));\n}\n'
           '</script>\n</body>')
    if 'navigator.serviceWorker.register' not in html:
        html = html.replace('</body>', reg, 1)
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(html)
    return out


def json_dumps(obj):
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)
