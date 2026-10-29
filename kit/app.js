const QUESTIONS = __DATA__;
const KPMETA = __KPMETA__;
const CHTABS = __CHTABS__;
const LS = __LSKEY__;
let S = JSON.parse(localStorage.getItem(LS) || '{}');
if (!S.status) S.status = {};
if (!S.fav) S.fav = {};
if (!S.exfav) S.exfav = {};
if (!S.kpfav) S.kpfav = {};
let filter = 'all';
let list = [];
let idx = 0;
let answered = false;
let mode = 'normal';
let exam = null;
let timerId = null;

function norm(s){
  return (s||'').toLowerCase()
    .replace(/[（(]/g,'(').replace(/[）)]/g,')')
    .replace(/[，,]/g,',').replace(/[。．.]/g,'.').replace(/[：:]/g,':')
    .replace(/[；;]/g,';').replace(/[“”"']/g,'').replace(/[？?]/g,'?')
    .replace(/\s+/g,'').replace(/[－—–]/g,'-');
}

function buildList(){
  if (mode === 'exam'){ list = exam ? exam.items : []; return; }
  if (filter.indexOf('kp:') === 0){ const k = filter.slice(3); list = QUESTIONS.filter(q => (q.kp||[]).indexOf(k) >= 0); }
  else if (filter === 'wrong') list = QUESTIONS.filter(q => (S.status[q.id]||{}).r === 'bad');
  else if (filter === 'fav') list = QUESTIONS.filter(q => S.fav[q.id]);
  else if (filter === 'exfav') list = QUESTIONS.filter(q => S.exfav[q.id]);
  else if (filter === 'kpfav') list = QUESTIONS.filter(q => (q.kp||[]).some(k => S.kpfav[k]));
  else if (filter === 'all') list = QUESTIONS.slice();
  else list = QUESTIONS.filter(q => q.ch === Number(filter.slice(2)));
  idx = Math.min(idx, Math.max(0, list.length-1));
}

function scopeName(){
  if (filter === 'all') return '全部';
  if (filter === 'wrong') return '错题';
  if (filter === 'fav') return '收藏';
  if (filter === 'kpfav') return '收藏知识点';
  if (filter === 'exfav') return '解析收藏';
  if (filter.indexOf('kp:') === 0) return '知识点「' + filter.slice(3) + '」';
  const hit = CHTABS.find(x => x[0] === filter);
  if (hit) return String(hit[1]).split(' · ')[0];
  return '第' + filter.slice(2) + '章';
}

function renderTabs(){
  const tabs = document.getElementById('tabs');
  if (mode === 'exam'){ tabs.innerHTML = ''; tabs.style.display = 'none'; return; }
  tabs.style.display = '';
  const defs = CHTABS;
  tabs.innerHTML = defs.map(([k,t]) => {
    const n = k==='all' ? QUESTIONS.length
      : k==='wrong' ? QUESTIONS.filter(q=>(S.status[q.id]||{}).r==='bad').length
      : k==='fav' ? QUESTIONS.filter(q=>S.fav[q.id]).length
      : k==='kpfav' ? QUESTIONS.filter(q=>(q.kp||[]).some(x=>S.kpfav[x])).length
      : k==='exfav' ? QUESTIONS.filter(q=>S.exfav[q.id]).length
      : QUESTIONS.filter(q=>q.ch===Number(k.slice(2))).length;
    return '<button class="tab' + (filter===k?' on':'') + (k==='wrong'?' wrong':'') + '" data-k="'+k+'">'+t+' <span class="n">'+n+'</span></button>';
  }).join('');
  if (filter.indexOf('kp:') === 0){
    tabs.innerHTML += '<button class="tab on" id="kpchip">知识点：' + esc(filter.slice(3)) + ' ✕</button>';
  }
  tabs.querySelectorAll('.tab').forEach(b => b.onclick = () => { filter = b.dataset.k; idx = 0; buildList(); render(); });
  const chip = document.getElementById('kpchip');
  if (chip) chip.onclick = () => { filter = 'all'; idx = 0; buildList(); render(); };
}

function statHTML(){
  const ok = Object.values(S.status).filter(s=>s.r==='ok').length;
  const bad = Object.values(S.status).filter(s=>s.r==='bad').length;
  const fav = Object.keys(S.fav).length;
  return '已做 <b>'+(ok+bad)+'</b>/'+QUESTIONS.length+'　答对 <b style="color:var(--ok)">'+ok+'</b>　答错 <b style="color:var(--bad)">'+bad+'</b>'+(fav?'　收藏 <b style="color:#f59e0b">'+fav+'</b>':'');
}

function render(skipRestore){
  const card = document.getElementById('card');
  document.getElementById('stat').innerHTML = statHTML();
  renderTabs();
  document.getElementById('examBtn').textContent = mode==='exam' ? '交卷' : '模考 30 题';
  const t = document.getElementById('timer');
  t.classList.toggle('hide', mode!=='exam');
  if (mode === 'exam'){
    if (!exam) return;
    if (exam.done) return renderSummary();
    return renderExamQ();
  }
  if (!list.length){
    card.innerHTML = '<div style="color:var(--dim);padding:30px 0;text-align:center">这个分类下还没有题目</div>';
    document.getElementById('pos').textContent = '0 / 0';
    renderSide(null);
    return;
  }
  idx = Math.max(0, Math.min(idx, list.length-1));
  const q = list[idx];
  answered = false;
  const st = S.status[q.id] || {};
  const typeName = q.type==='choice' ? '选择题' : q.type==='fill' ? '填空题' : '综合应用题';
  let body = '';

  if (q.type === 'choice'){
    body = '<div class="opts">' + q.opts.map(o =>
      '<button class="opt" data-k="'+o.k+'"><span class="k">'+o.k+'</span><span>'+esc(o.t)+'</span></button>')
      .join('') + '</div>';
  } else if (q.type === 'fill'){
    if (q.parts && q.parts.length){
      body = '<div class="fill">' + q.parts.map((p,i) =>
        '<div class="row"><label>第'+(i+1)+'空</label><input type="text" data-i="'+i+'" autocomplete="off"></div>')
        .join('') + '<div><button class="btn primary" id="submit">提交</button></div></div>';
    } else {
      body = '<div class="fill"><div class="row"><label>答案</label><input type="text" data-i="0" autocomplete="off"></div>' +
             '<div><button class="btn primary" id="submit">提交</button></div></div>';
    }
  } else {
    body = '<div class="fill"><textarea id="subj" placeholder="先自己写一遍，再看参考答案对照"></textarea>' +
           '<div><button class="btn primary" id="reveal">显示参考答案</button></div></div>';
  }

  card.innerHTML = '<div class="meta"><span class="badge">第 '+q.ch+' 章</span><span class="badge">'+typeName+'</span>' +
    '<span class="badge">'+esc(q.id)+'</span>' +
    '<button class="star'+(S.fav[q.id]?' on':'')+'" id="star" title="收藏">'+(S.fav[q.id]?'★':'☆')+'</button></div>' +
    '<div class="q">'+esc(q.text)+'</div>' + body + '<div id="ansbox"></div>';

  document.getElementById('pos').innerHTML = (idx+1)+' / '+list.length;
  document.getElementById('bar').style.width = (100*(idx+1)/list.length)+'%';
  document.getElementById('star').onclick = () => { if (S.fav[q.id]) delete S.fav[q.id]; else S.fav[q.id] = 1; save(); render(); };

  if (q.type === 'choice'){
    card.querySelectorAll('.opt').forEach(b => b.onclick = () => pick(b, q));
    if (st.choice && !skipRestore) finishChoice(q, st.choice, true);
  } else if (q.type === 'fill'){
    card.querySelector('#submit').onclick = () => checkFill(q);
    card.querySelectorAll('input[type=text]').forEach(inp => inp.onkeydown = e => { if (e.key==='Enter') checkFill(q); });
    if (st.fill && !skipRestore) checkFill(q, st.fill);
  } else {
    card.querySelector('#reveal').onclick = () => revealSubj(q);
    if (st.r && !skipRestore) revealSubj(q, true);
  }
  if (filter === 'exfav') revealExp(q);
  renderSide(q);
  window.scrollTo({top:0,behavior:'smooth'});
}

function esc(s){ return (s||'').replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function save(){ localStorage.setItem(LS, JSON.stringify(S)); }

function mark(id, ok){
  const st = S.status[id] || (S.status[id] = {});
  if (ok){
    if (st.wrong){
      st.chain = (st.chain || 0) + 1;
      if (st.chain >= 2){ st.r = 'ok'; st.wrong = false; st.chain = 0; }
      else st.r = 'bad';
    } else { st.r = 'ok'; st.wrong = false; }
  } else { st.wrong = true; st.chain = 0; st.r = 'bad'; }
  save();
  return st;
}

function chainNote(q){
  const st = S.status[q.id] || {};
  if (st.r === 'ok') return '';
  if (st.wrong && st.chain) return '<span class="chipx">错题 · 连对 '+st.chain+'/2</span>';
  return '';
}

function showAns(html){
  document.getElementById('ansbox').innerHTML = '<div class="ans">'+html+'</div>';
}

function expHTML(q){
  const on = !!S.exfav[q.id];
  return '<div class="expline"><span class="extext">' + esc(q.exp || '（这条题在题库里没有更多解析）') + '</span>' +
    '<button class="kfstar exstar' + (on ? ' on' : '') + '" data-f="' + q.id + '" title="收藏这条解析">' + (on ? '★' : '☆') + '</button></div>';
}

function bindEx(q){
  const b = document.querySelector('#ansbox .exstar');
  if (!b) return;
  b.onclick = (e) => {
    e.stopPropagation();
    if (S.exfav[q.id]) delete S.exfav[q.id]; else S.exfav[q.id] = 1;
    save();
    b.classList.toggle('on', !!S.exfav[q.id]);
    b.textContent = S.exfav[q.id] ? '★' : '☆';
    renderTabs();
  };
}

function revealExp(q){
  answered = true;
  const want = q.type === 'choice' ? q.correct.join('、')
    : (q.parts && q.parts.length ? q.parts.join('　|　') : q.answer);
  showAns('<h4>参考答案：' + esc(want) + '</h4>' + (q.type === 'subj' ? '' : expHTML(q))
    + (q.type === 'subj' ? '<div class="expline"><span class="extext">' + esc(q.answer || '') + '</span></div>' : ''));
  bindEx(q);
  if (q.type === 'choice'){
    document.querySelectorAll('.opt').forEach(el => {
      el.disabled = true;
      if (q.correct.indexOf(el.dataset.k) >= 0) el.classList.add('ok');
    });
  }
}

function wireRetry(){
  const box = document.getElementById('ansbox');
  const b = document.createElement('button');
  b.className = 'btn'; b.textContent = '重做本题'; b.style.cssText = 'margin-top:10px';
  b.onclick = () => render(true);
  box.querySelector('.ans').appendChild(b);
}

function pick(btn, q){
  if (answered) return;
  finishChoice(q, btn.dataset.k, false);
}

function finishChoice(q, k, restore){
  answered = true;
  const ok = q.correct.indexOf(k) >= 0;
  document.querySelectorAll('.opt').forEach(el => {
    el.disabled = true;
    if (el.dataset.k === k) el.classList.add(ok ? 'ok' : 'bad');
    if (q.correct.indexOf(el.dataset.k) >= 0) el.classList.add('ok');
  });
  if (!restore){
    mark(q.id, ok);
    S.status[q.id].choice = k;
    save();
  }
  showAns('<h4>参考答案：'+q.correct.join('、')+chainNote(q)+'<span class="verdict '+(ok?'ok':'bad')+'">'+(restore ? (ok?'答对过':'答错过') : (ok?'答对了':'答错了'))+'</span></h4>' + expHTML(q));
  bindEx(q);
  if (!ok || (S.status[q.id]||{}).wrong) wireRetry();
  document.getElementById('stat').innerHTML = statHTML();
  renderTabs();
  renderSide(q);
}

function checkFill(q, restoreVals){
  if (answered && !restoreVals) return;
  const inputs = Array.from(document.querySelectorAll('input[type=text]'));
  if (!inputs.length) return;
  const vals = restoreVals ? restoreVals.slice() : inputs.map(i => i.value);
  if (restoreVals) inputs.forEach((inp, i) => { inp.value = vals[i] || ''; });
  let ok, right = 0;
  if (q.parts && q.parts.length){
    q.parts.forEach((p, i) => {
      const good = norm(p) === norm(vals[i]);
      if (good) right++;
      inputs[i].style.borderColor = good ? 'var(--ok)' : 'var(--bad)';
    });
    ok = right === q.parts.length;
  } else {
    ok = norm(q.answer) === norm(vals[0]||'');
    inputs[0].style.borderColor = ok ? 'var(--ok)' : 'var(--bad)';
    right = ok ? 1 : 0;
  }
  answered = true;
  if (!restoreVals){
    mark(q.id, ok);
    S.status[q.id].fill = vals;
    save();
  }
  const want = (q.parts && q.parts.length) ? q.parts.join('　|　') : q.answer;
  const total = (q.parts && q.parts.length) ? q.parts.length : 1;
  const detail = ok ? '' : '　<span class="chipx">'+(total>1 ? right+'/'+total+' 空正确' : '不对')+'</span>';
  let appeal = '';
  if (!ok && !restoreVals){
    appeal = ' <button class="btn" id="appeal" style="font-size:12px;padding:3px 9px;margin-left:8px">算我对</button>';
  }
  showAns('<h4>参考答案：'+esc(want)+chainNote(q)+detail+'<span class="verdict '+(ok?'ok':'bad')+'">'+(restoreVals ? (ok?'答对过':'答错过') : (ok?'填对了':'再想想'))+'</span>'+appeal+'</h4>' + expHTML(q));
  bindEx(q);
  if (!ok || (S.status[q.id]||{}).wrong) wireRetry();
  const ap = document.getElementById('appeal');
  if (ap) ap.onclick = () => {
    const st = S.status[q.id] || (S.status[q.id] = {});
    st.r = 'ok'; st.wrong = false; st.chain = 0; save();
    ap.remove();
    document.getElementById('stat').innerHTML = statHTML();
    renderTabs(); renderSide(q);
  };
  document.getElementById('stat').innerHTML = statHTML();
  renderTabs();
  renderSide(q);
}

function revealSubj(q, restore){
  const box = document.getElementById('ansbox');
  if (box.dataset.open) return;
  box.dataset.open = '1';
  box.innerHTML = '<div class="ans"><h4>参考答案'+chainNote(q)+'</h4>' + esc(q.answer) +
    '<div class="expline" style="margin-top:10px"><span class="extext"></span>' +
    '<button class="kfstar exstar' + (S.exfav[q.id] ? ' on' : '') + '" data-f="' + q.id + '" title="收藏这条解析">' + (S.exfav[q.id] ? '★' : '☆') + '</button></div>' +
    '<div style="margin-top:6px;display:flex;gap:10px;align-items:center">' +
    '<button class="btn ok" id="selfOk">我答对了</button><button class="btn bad" id="selfBad">没答对</button>' +
    '<span class="hint">自评一下，会记进进度和错题</span></div></div>';
  bindEx(q);
  document.getElementById('selfOk').onclick = () => { mark(q.id,true); document.getElementById('stat').innerHTML = statHTML(); renderTabs(); renderSide(q); };
  document.getElementById('selfBad').onclick = () => { mark(q.id,false); document.getElementById('stat').innerHTML = statHTML(); renderTabs(); renderSide(q); };
}

function renderSide(q){
  const kps = document.getElementById('kps');
  if (q){
    kps.innerHTML = (q.kp || ['其他']).map(k => '<button class="chip' + (filter === 'kp:' + k ? ' on' : '') + '" data-k="'+esc(k)+'">'+esc(k)+'</button>' +
      '<button class="kfstar' + (S.kpfav[k] ? ' on' : '') + '" data-f="' + esc(k) + '" title="收藏这个知识点">' + (S.kpfav[k] ? '★' : '☆') + '</button>' +
      '<button class="doclink" data-k="' + esc(k) + '" title="看这部分资料">📖</button>').join('');
    kps.querySelectorAll('.chip').forEach(b => b.onclick = () => { filter = 'kp:' + b.dataset.k; idx = 0; buildList(); render(); });
    kps.querySelectorAll('.doclink').forEach(b => b.onclick = () => openDocFor(b.dataset.k));
  } else {
    kps.innerHTML = '<span style="color:var(--dim);font-size:13px">—</span>';
  }
  const kfav = Object.keys(S.kpfav);
  if (kfav.length){
    kps.innerHTML += '<div class="kfhead">收藏的知识点</div>' + kfav.map(k =>
      '<button class="chip kfchip' + (filter === 'kp:' + k ? ' on' : '') + '" data-k="' + esc(k) + '">★ ' + esc(k) + '</button>').join('');
    kps.querySelectorAll('.kfchip').forEach(b => b.onclick = () => { filter = 'kp:' + b.dataset.k; idx = 0; buildList(); render(); });
  }

  const map = {};
  const base = (filter.indexOf('kp:') === 0 || filter === 'kpfav') ? QUESTIONS : list;
  base.forEach(x => (x.kp || ['其他']).forEach(k => {
    const m = map[k] || (map[k] = { n: 0, ok: 0 });
    m.n++;
    if ((S.status[x.id]||{}).r === 'ok') m.ok++;
  }));

  const groups = [];
  KPMETA.forEach(meta => {
    let g = groups.filter(x => x.g === meta.g)[0];
    if (!g){ g = { g: meta.g, rows: [] }; groups.push(g); }
    const m = map[meta.n] || { n: 0, ok: 0 };
    g.rows.push({ n: meta.n, total: m.n, ok: m.ok });
  });
  groups.forEach(g => g.rows.sort((a,b) => b.total - a.total));

  document.getElementById('scopetitle').textContent = ((filter.indexOf('kp:') === 0 || filter === 'kpfav') ? '全部' : scopeName()) + ' · 知识点';
  document.getElementById('kpstats').innerHTML = groups.map(g => '<div class="kpg">' + esc(g.g) + '</div>' + g.rows.map(r => {
    const pct = r.total ? Math.round(100 * r.ok / r.total) : 0;
    return '<div class="kprow' + (r.total ? '' : ' zero') + (filter === 'kp:' + r.n ? ' on' : '') + '" data-k="' + esc(r.n) + '">' +
      '<span class="kpname">' + esc(r.n) + '</span>' +
      '<span class="kpbar"><i style="width:' + pct + '%"></i></span><span class="kpnum">' + r.ok + '/' + r.total + '</span>' +
      '<button class="doclink" data-d="' + esc(r.n) + '" title="看资料">📖</button>' +
      '<button class="kfstar' + (S.kpfav[r.n] ? ' on' : '') + '" data-f="' + esc(r.n) + '" title="收藏这个知识点">' + (S.kpfav[r.n] ? '★' : '☆') + '</button></div>';
  }).join('')).join('');
  document.querySelectorAll('.kprow').forEach(r => r.onclick = () => {
    if (r.classList.contains('zero')) return;
    filter = 'kp:' + r.dataset.k; idx = 0; buildList(); render();
  });
  document.querySelectorAll('.kprow .doclink').forEach(b => b.onclick = (e) => { e.stopPropagation(); openDocFor(b.dataset.d); });
  document.querySelectorAll('.kfstar:not(.exstar)').forEach(b => b.onclick = (e) => {
    e.stopPropagation();
    const k = b.dataset.f;
    if (S.kpfav[k]) delete S.kpfav[k]; else S.kpfav[k] = 1;
    save(); render();
  });
}

/* ---------- 模考 ---------- */
function shuffle(a){ a = a.slice(); for (let i = a.length-1; i > 0; i--){ const j = Math.floor(Math.random()*(i+1)); const t = a[i]; a[i] = a[j]; a[j] = t; } return a; }

function startExam(){
  const pool = (filter === 'all' || filter.indexOf('kp:') === 0 || filter === 'fav' || filter === 'wrong')
    ? QUESTIONS.slice() : QUESTIONS.filter(q => q.ch === Number(filter.slice(2)));
  const fresh = pool.filter(q => (S.status[q.id]||{}).r !== 'ok');
  const pickFrom = fresh.length >= 30 ? fresh : pool;
  exam = { items: shuffle(pickFrom).slice(0, Math.min(30, pickFrom.length)), ans: {}, t0: Date.now(), limit: 45*60, done: false };
  mode = 'exam'; idx = 0; list = exam.items;
  document.getElementById('tabs').style.display = 'none';
  document.querySelector('aside').style.display = 'none';
  document.querySelector('main').style.gridTemplateColumns = 'minmax(0,1fr)';
  render();
  if (timerId) clearInterval(timerId);
  timerId = setInterval(tick, 1000);
  tick();
}

function fmt(sec){ sec = Math.max(0, sec|0); const m = Math.floor(sec/60), s = sec%60; return (m<10?'0':'')+m+':'+(s<10?'0':'')+s; }

function tick(){
  if (mode !== 'exam' || !exam || exam.done) return;
  const left = exam.limit - Math.floor((Date.now() - exam.t0)/1000);
  const el = document.getElementById('timer');
  if (el) el.textContent = '剩余 ' + fmt(left);
  if (left <= 0) submitExam();
}

function renderExamQ(){
  const card = document.getElementById('card');
  idx = Math.max(0, Math.min(idx, exam.items.length-1));
  const q = exam.items[idx];
  const a = exam.ans[q.id];
  let body = '';
  if (q.type === 'choice'){
    body = '<div class="opts">' + q.opts.map(o =>
      '<button class="opt' + (a===o.k?' sel':'') + '" data-k="'+o.k+'"><span class="k">'+o.k+'</span><span>'+esc(o.t)+'</span></button>').join('') + '</div>';
  } else if (q.type === 'fill'){
    const vals = a || [];
    const n = (q.parts && q.parts.length) ? q.parts.length : 1;
    body = '<div class="fill">' + Array.from({length:n}, (_, i) =>
      '<div class="row"><label>'+(n>1?'第'+(i+1)+'空':'答案')+'</label><input type="text" data-i="'+i+'" autocomplete="off" value="'+esc(vals[i]||'')+'"></div>').join('') + '</div>';
  } else {
    body = '<div class="fill"><textarea id="subj" placeholder="写下你的答案，交卷后可对照参考答案">'+esc(a||'')+'</textarea></div>';
  }
  card.innerHTML = '<div class="meta"><span class="badge">模考</span><span class="badge">第 '+q.ch+' 章</span>' +
    '<span class="badge">'+(q.type==='choice'?'选择题':q.type==='fill'?'填空题':'综合应用题')+'</span>' +
    '<span class="badge">'+esc(q.id)+'</span></div><div class="q">'+esc(q.text)+'</div>' + body;

  document.getElementById('pos').innerHTML = '已答 ' + Object.keys(exam.ans).length + ' / ' + exam.items.length + '　第 ' + (idx+1) + ' 题';
  document.getElementById('bar').style.width = (100*(idx+1)/exam.items.length)+'%';

  if (q.type === 'choice'){
    card.querySelectorAll('.opt').forEach(b => b.onclick = () => { exam.ans[q.id] = b.dataset.k; renderExamQ(); });
  } else if (q.type === 'fill'){
    card.querySelectorAll('input[type=text]').forEach(inp => inp.oninput = () => {
      const arr = exam.ans[q.id] || [];
      arr[Number(inp.dataset.i)] = inp.value;
      exam.ans[q.id] = arr;
      document.getElementById('pos').innerHTML = '已答 ' + Object.keys(exam.ans).length + ' / ' + exam.items.length + '　第 ' + (idx+1) + ' 题';
    });
  } else {
    const ta = card.querySelector('#subj');
    if (ta) ta.oninput = () => { exam.ans[q.id] = ta.value; document.getElementById('pos').innerHTML = '已答 ' + Object.keys(exam.ans).length + ' / ' + exam.items.length + '　第 ' + (idx+1) + ' 题'; };
  }
  window.scrollTo({top:0,behavior:'smooth'});
}

function submitExam(){
  if (!exam || exam.done) return;
  const open = exam.items.length - Object.keys(exam.ans).length;
  if (open > 0 && Date.now() - exam.t0 < exam.limit*1000){
    if (!confirm('还有 ' + open + ' 题没作答，确定交卷？')) return;
  }
  exam.done = true;
  if (timerId){ clearInterval(timerId); timerId = null; }
  let score = 0, total = 0; const wrongs = []; const oks = {};
  exam.items.forEach(q => {
    const a = exam.ans[q.id];
    if (q.type === 'choice'){
      total++;
      const ok = a && q.correct.indexOf(a) >= 0;
      if (ok){ score++; oks[q.id] = 1; } else wrongs.push(q);
    } else if (q.type === 'fill'){
      total++;
      const n = (q.parts && q.parts.length) ? q.parts.length : 1;
      let ok = true;
      for (let i = 0; i < n; i++){
        const want = (q.parts && q.parts.length) ? q.parts[i] : q.answer;
        if (norm(want) !== norm((a||[])[i])) { ok = false; break; }
      }
      if (ok){ score++; oks[q.id] = 1; } else wrongs.push(q);
    }
  });
  exam.score = score; exam.total = total; exam.wrongs = wrongs; exam.oks = oks;
  exam.used = Math.floor((Date.now() - exam.t0)/1000);
  render();
}

function renderSummary(){
  const card = document.getElementById('card');
  const pct = exam.total ? Math.round(100*exam.score/exam.total) : 0;
  const unanswered = exam.items.filter(q => !(q.id in exam.ans)).length;
  card.innerHTML = '<div class="summary"><h2>模考结束</h2>' +
    '<div><span class="score">' + exam.score + '</span><span style="color:var(--dim)"> / ' + exam.total + ' 客观题　正确率 ' + pct + '%</span></div>' +
    '<div style="color:var(--dim);margin-top:8px">用时 ' + fmt(exam.used) + '　未作答 ' + unanswered + ' 题（简答题不计分，需自评）</div>' +
    (exam.wrongs.length ? '<ul class="wronglist">' + exam.wrongs.map(q => '<li>· '+esc(q.id)+'　'+esc(q.text.slice(0,42)) + (q.type==='choice' ? '（正确答案 '+q.correct.join('、')+'）' : '') + '</li>').join('') + '</ul>'
      : '<div style="color:var(--ok);margin-top:10px">客观题全对，厉害。</div>') +
    '<div style="margin-top:16px;display:flex;gap:10px"><button class="btn primary" id="again">再考一次</button><button class="btn" id="back">退出模考</button></div></div>';
  document.getElementById('pos').textContent = '';
  document.getElementById('bar').style.width = '100%';
  document.getElementById('timer').classList.add('hide');
  document.getElementById('examBtn').textContent = '退出模考';
  document.getElementById('prev').disabled = true;
  document.getElementById('next').disabled = true;
  document.getElementById('again').onclick = () => { exitExam(); startExam(); };
  document.getElementById('back').onclick = exitExam;
  renderSide(null);
}

function exitExam(){
  if (timerId){ clearInterval(timerId); timerId = null; }
  mode = 'normal'; exam = null;
  document.getElementById('tabs').style.display = '';
  document.querySelector('aside').style.display = '';
  document.querySelector('main').style.gridTemplateColumns = '';
  document.getElementById('timer').classList.add('hide');
  document.getElementById('prev').disabled = false;
  document.getElementById('next').disabled = false;
  filter = 'all'; idx = 0; buildList(); render();
}

/* ---------- 导航 ---------- */
function next(){ if (idx < list.length-1){ idx++; render(); } }
function prev(){ if (idx > 0){ idx--; render(); } }

document.getElementById('next').onclick = next;
document.getElementById('prev').onclick = prev;
document.getElementById('examBtn').onclick = () => { if (mode === 'exam'){ (exam && exam.done) ? exitExam() : submitExam(); } else startExam(); };
document.getElementById('reset').onclick = () => { if (confirm('清空所有答题记录、收藏？')){ S = {status:{}, fav:{}, kpfav:{}}; save(); buildList(); render(); } };

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowRight') next();
  if (e.key === 'ArrowLeft') prev();
  if (mode === 'normal' && /^[a-dA-D]$/.test(e.key)){
    const b = document.querySelector('.opt[data-k="'+e.key.toUpperCase()+'"]');
    if (b) b.click();
  }
});

window.addEventListener('hashchange', () => {
  const m = (location.hash||'').match(/#(q\d+)/);
  if (!m || mode === 'exam') return;
  const i = QUESTIONS.findIndex(x => x.id === m[1]);
  if (i >= 0){ filter = 'all'; list = QUESTIONS.slice(); idx = i; render(); }
});

buildList();
(function(){
  try {
    const sp = new URLSearchParams(location.search);
    const kp = sp.get('kp');
    if (kp){ filter = 'kp:' + kp; buildList(); }
  } catch (e) {}
})();
(function(){
  const m = (location.hash||'').match(/#(q\d+)/);
  if (m){
    const i = QUESTIONS.findIndex(x => x.id === m[1]);
    if (i >= 0){ filter = 'all'; list = QUESTIONS.slice(); idx = i; }
  }
})();
(function(){
  try {
    if (new URLSearchParams(location.search).get('exam') === '1'){ startExam(); return; }
  } catch (e) {}
  render();
})();

/* ---------- 复习资料抽屉 ---------- */
const DOCS = __DOCS__;
const KPDOC = __KPDOC__;
const SECMAP = {};
DOCS.forEach(d => d.secs.forEach(s => { SECMAP[s.id] = { doc: d, sec: s }; }));
let curDoc = 'res', curSecId = null;

function docObj(id){ return DOCS.find(x => x.id === id) || DOCS[0]; }

function openDrawer(docId, secId){
  const d = docObj(docId || curDoc);
  document.getElementById('drawer').classList.remove('hide');
  const sel = document.getElementById('docSel');
  if (!sel.options.length){
    sel.innerHTML = DOCS.map(x => '<option value="' + x.id + '">' + esc(x.title) + '</option>').join('');
    sel.onchange = () => { curDoc = sel.value; renderToc(docObj(curDoc), null); renderSec(docObj(curDoc).secs[0]); };
  }
  sel.value = d.id; curDoc = d.id;
  document.getElementById('docSearch').value = '';
  const s = (secId && d.secs.find(x => x.id === secId)) || d.secs[0];
  renderToc(d, s ? s.id : null);
  renderSec(s);
}

function renderToc(d, activeId){
  const t = document.getElementById('dtoc');
  t.innerHTML = d.secs.map(s =>
    '<a href="#" data-sid="' + s.id + '" class="' + (s.level === 1 ? 'l1' : '') + (s.id === activeId ? ' on' : '') + '">' +
    esc((s.no ? s.no + ' ' : '') + s.title) + '</a>').join('');
  t.querySelectorAll('a').forEach(a => a.onclick = (e) => {
    e.preventDefault();
    const ref = SECMAP[a.dataset.sid];
    renderSec(ref.sec); curSecId = ref.sec.id;
    t.querySelectorAll('a').forEach(x => x.classList.toggle('on', x === a));
  });
}

function tblHtml(txt){
  const rows = txt.split(String.fromCharCode(10)).map(r => r.trim()).filter(Boolean).map(r => r.split(' | '));
  if (!rows.length) return '';
  const head = rows[0], body = rows.slice(1);
  const tds = (cells, tag) => cells.map(c => '<' + tag + '>' + esc(c) + '</' + tag + '>').join('');
  return '<div class="tblwrap"><table class="tbl"><thead><tr>' + tds(head, 'th') + '</tr></thead><tbody>' +
    body.map(r => '<tr>' + tds(r, 'td') + '</tr>').join('') + '</tbody></table></div>';
}

function renderSec(s){
  const box = document.getElementById('dtext');
  if (!s){ box.innerHTML = '<p class="empty">没有找到内容</p>'; return; }
  curSecId = s.id;
  const h = '<h4>' + esc((s.no ? s.no + '　' : '') + s.title) + '</h4>' + s.body.map(b =>
    b.t === 'code' ? '<pre>' + esc(b.s) + '</pre>' :
    b.t === 'img' ? '<img class="dimg" alt="图" src="' + b.s + '">' :
    b.t === 'tbl' ? tblHtml(b.s) :
    '<p>' + esc(b.s) + '</p>').join('');
  box.innerHTML = h;
  box.scrollTop = 0;
}

function openDocFor(kp){
  const ids = KPDOC[kp] || [];
  const first = ids.map(i => SECMAP[i]).filter(Boolean)[0];
  if (first) openDrawer(first.doc.id, first.sec.id);
  else openDrawer('res', 'tables');
}

function docSearchGo(v){
  v = (v || '').trim();
  const t = document.getElementById('dtoc');
  if (!v){ renderToc(docObj(curDoc), curSecId); return; }
  const hits = [];
  DOCS.forEach(d => d.secs.forEach(s => {
    const title = (s.no ? s.no + ' ' : '') + s.title;
    const body = s.body.map(b => b.s).join('\n');
    let cnt = 0, at = 0;
    while ((at = body.indexOf(v, at)) >= 0){ cnt++; at += v.length; }
    const tc = title.indexOf(v) >= 0 ? 1 : 0;
    if (tc || cnt) hits.push({ d, s, title, score: tc * 1000 + cnt });
  }));
  hits.sort((a, b) => b.score - a.score);
  t.innerHTML = '<div class="dt">匹配 ' + hits.length + ' 节</div>' + hits.map((h, i) =>
    '<a href="#" data-i="' + i + '">' + esc(h.title) + (h.score % 1000 ? ' <span class="hn">' + (h.score % 1000) + '</span>' : '') + '</a>').join('');
  t.querySelectorAll('a').forEach(a => a.onclick = (e) => {
    e.preventDefault();
    const h = hits[Number(a.dataset.i)];
    curDoc = h.d.id;
    document.getElementById('docSel').value = h.d.id;
    renderSec(h.s);
    renderToc(h.d, h.s.id);
  });
}

document.getElementById('docBtn').onclick = () => openDrawer(curDoc, curSecId);
document.getElementById('docClose').onclick = () => document.getElementById('drawer').classList.add('hide');
document.getElementById('docSearch').oninput = (e) => docSearchGo(e.target.value);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') document.getElementById('drawer').classList.add('hide');
});
