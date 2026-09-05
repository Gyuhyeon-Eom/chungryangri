/* 청량리마켓 — 커머스 프런트.
   data.json(분석 파이프라인 산출)을 상품·시장 소스로 쓴다.
   이미지: 카테고리별 이모지 타일. 실제 상품 사진이 준비되면 IMG 맵만 교체하면 된다. */

const KRW = new Intl.NumberFormat('ko-KR');
const won = (n) => KRW.format(n) + '원';

/* 실사 이미지 맵 — img/map.json 이 로드되면 이모지 대신 사진을 쓴다 */
let IMG = {};
let PIMG = {};   // 상품명 → 이미지
/* 카테고리 폴백이 오답이 되는 상품 — 틀린 사진보다 No Image가 낫다 */
const NO_IMG = new Set(['배', '배(박스)', '사과(박스)', '호두', '대추',
                        '오징어', '대파', '다시마', '펌 롯드', '주방 소도구']);

/* 카테고리 → [이모지, 타일 배경] (이미지 없을 때 폴백) */
const TILE = {
  '한약재': ['🌿', '#eef3ec'], '인삼·홍삼': ['🫚', '#f3ece2'], '건약초': ['🍂', '#f1ede2'],
  '밤·견과류': ['🌰', '#f3ede3'], '곡류·참기름': ['🫙', '#f5efe2'], '선물세트': ['🎁', '#f2ece8'],
  '제철 과일': ['🍎', '#fbeeea'], '청과': ['🍅', '#fbf0e8'], '청과 도매': ['📦', '#f0ede6'],
  '채소': ['🥬', '#ecf3ea'], '농산물': ['🥔', '#f3efe6'], '수산물': ['🐟', '#e9f1f5'],
  '활어': ['🐠', '#e7f2f6'], '선어': ['🎣', '#eaf1f4'], '패류': ['🦪', '#edf0ef'],
  '건어물': ['🦑', '#f2efe8'], '정육': ['🥩', '#f9ecec'], '반찬': ['🥘', '#f7efe6'],
  '먹거리': ['🥟', '#f8f0e5'], '통닭': ['🍗', '#f8efe2'], '족발': ['🍖', '#f6ece6'],
  '회': ['🍣', '#eaf2f2'], '분식': ['🍢', '#f9eee7'], '건강식품': ['🍯', '#f6efe0'],
  '미용재료': ['✂️', '#efeff3'], '잡화': ['🧺', '#f1f0ec'],
};
const MARKET_EMOJI = {
  '서울약령시장': '🌿', '경동시장': '🧺', '경동광성상가': '🍯', '청량리종합시장': '🌰',
  '청량리청과물시장': '🍎', '동서시장': '🍅', '청량리농수산물시장': '🥔',
  '청량리수산시장': '🐟', '청량리전통시장': '🍗',
};

const state = {
  data: null,
  channel: localStorage.getItem('cl-channel') || 'b2c',
  category: '전체',
  market: '전체',
  query: '',
  cart: JSON.parse(localStorage.getItem('cl-cart') || '{}'),
};
const $ = (id) => document.getElementById(id);

/* 할인 표시는 상품 id 해시로 고정한다 — 새로고침마다 바뀌면 신뢰가 깨진다 */
function hash(s) { let h = 0; for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0; return h; }
function saleInfo(p) {
  const h = hash(p.id);
  const off = [0, 0, 10, 15, 20, 30][h % 6];        // 1/3은 정가 판매
  if (!off) return { off: 0, was: null };
  const was = Math.round(p.price / (1 - off / 100) / 100) * 100;
  return { off, was };
}
const isNew = (p) => hash(p.id) % 4 === 0;
const freeShip = (p) => p.price >= 20000;

/* ---------------- 상품 카드 ---------------- */
function marketOf(p) { return state.data.markets.find((m) => m.name === p.market); }

function card(p) {
  const [, bg] = TILE[p.category] || ['', '#f2f2f0'];
  const img = PIMG[p.name] || (NO_IMG.has(p.name) ? null : IMG[p.category]);
  const { off, was } = saleInfo(p);
  const m = marketOf(p);
  const isFlagship = m && (m.flagship || [])[0] === p.category;  // 시장당 간판 1개만
  const el = document.createElement('article');
  el.className = 'card';
  el.innerHTML = `
    <div class="thumb" style="background:${bg}">
      ${off ? `<span class="off">${off}%</span>` : ''}
      ${img ? `<img src="${img}" alt="${p.name}" loading="lazy"
                 onerror="this.parentElement.classList.add('noimg'); this.remove()">`
            : ''}
      <span class="noimg-label">이미지 준비중</span>
    </div>
    <span class="market-name">${p.market}${isFlagship ? ' <b class="mini-top">대표 품목</b>' : ''}</span>
    <p class="name">${p.name} ${p.unit}${p.channel === 'b2b' ? ' (도매)' : ''}</p>
    <div class="price-row">
      ${off ? `<span class="pct">${off}%</span>` : ''}
      <span class="krw">${won(p.price)}</span><span class="unit">/ ${p.unit}</span>
    </div>
    ${was ? `<div class="was">${won(was)}</div>` : ''}
    <div class="badges">
      ${freeShip(p) ? '<span class="badge badge-ship">무료배송</span>' : ''}
      ${isNew(p) ? '<span class="badge badge-new">신상품</span>' : ''}
      ${p.channel === 'b2b' ? '<span class="badge badge-b2b">도매</span>' : ''}
    </div>`;
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'add';
  btn.textContent = p.channel === 'b2b' ? '견적 담기' : '장바구니 담기';
  btn.onclick = () => addToCart(p);
  el.appendChild(btn);
  return el;
}

/* ---------------- 렌더 ---------------- */
function pool() {
  return state.data.products.filter((p) => p.channel === state.channel);
}
function visible() {
  const q = state.query.trim();
  return pool().filter((p) =>
    (state.category === '전체' || p.category === state.category) &&
    (state.market === '전체' || p.market === state.market) &&
    (!q || p.name.includes(q) || p.market.includes(q) || p.category.includes(q)));
}


/* ---------------- 분석 기반: 오늘 발송 마감 ----------------
   시장별 거래 피크가 끝나는 시각을 당일 발송 마감으로 본다.
   (피크가 끝나면 그날 들어온 물건이 소진되기 시작한다는 뜻이므로.)
   온라인 구매자에게는 "언제 주문해야 오늘 준비된 물건을 받는가"로 번역된다. */
const BAND_OF_HOUR = (h) =>
  h < 6 ? '00~06' : h < 11 ? '06~11' : h < 14 ? '11~14' : h < 17 ? '14~17' : h < 21 ? '17~21' : '21~24';

function cutoffHour(m) {
  // 피크 구간(최대 매출 시간대)의 끝 시각 = 발송 마감
  const bands = ['00~06', '06~11', '11~14', '14~17', '17~21', '21~24'];
  const ends = { '00~06': 6, '06~11': 11, '11~14': 14, '14~17': 17, '17~21': 21, '21~24': 24 };
  const peak = bands.reduce((a, b) => (m.timeProfile[b] || 0) > (m.timeProfile[a] || 0) ? b : a);
  return ends[peak];
}

function fmtLeft(hours) {
  const h = Math.floor(hours), mm = Math.round((hours - h) * 60);
  return h > 0 ? `${h}시간 ${mm}분` : `${mm}분`;
}

function renderLive() {
  const now = new Date();
  const nowH = now.getHours() + now.getMinutes() / 60;
  const withCut = state.data.markets.map((m) => ({ m, cut: cutoffHour(m), left: cutoffHour(m) - nowH }));
  const open = withCut.filter((x) => x.left > 0).sort((a, b) => a.left - b.left);

  let tops, why, note;
  if (open.length) {
    tops = open.slice(0, 2);
    why = tops.map(({ m, cut, left }) =>
      `<b>${m.name}</b> 오늘 발송 마감 ${cut}시 · <b class="left">${fmtLeft(left)} 남음</b>`).join(' &nbsp;·&nbsp; ');
    note = '시장별 거래 피크(2021~2025 매출 데이터)가 끝나기 전에 주문하면 당일 준비된 물건으로 발송됩니다.';
  } else {
    // 모든 시장 마감 → 아침 일찍 여는 순서로 내일 예약
    tops = withCut.sort((a, b) => a.cut - b.cut).slice(0, 2);
    why = tops.map(({ m, cut }) => `<b>${m.name}</b> 내일 ${cut}시 발송분 예약`).join(' &nbsp;·&nbsp; ');
    note = '오늘 발송은 마감되었습니다. 지금 주문하면 내일 준비되는 물건으로 가장 먼저 발송됩니다.';
  }
  $('live-why').innerHTML = why;
  $('live-note').textContent = note;

  const names = new Set(tops.map((t) => t.m.name));
  const picks = pool().filter((p) => names.has(p.market)).slice(0, 5);
  const grid = $('live-grid');
  grid.innerHTML = '';
  for (const p of picks) grid.appendChild(card(p));
}


/* ---------------- 시장별 대표 상품 선반 ----------------
   "어느 시장에서 뭘 사야 하는지"를 선반 헤드라인으로 말해준다.
   리포트의 결론(업종 구성·시간대·성장)을 사용자 언어로 옮긴 부분. */
function renderShelves() {
  const wrap = $('shelves');
  if (!wrap) return;
  wrap.innerHTML = '';
  const order = ['서울약령시장', '청량리수산시장', '청량리종합시장', '청량리전통시장', '청량리청과물시장'];
  for (const name of order) {
    const m = state.data.markets.find((x) => x.name === name);
    if (!m || !m.shelf) continue;
    const picks = pool().filter((p) => p.market === name && (m.flagship || []).includes(p.category)).slice(0, 5);
    if (picks.length < 3) continue;
    const sec = document.createElement('div');
    sec.className = 'shelf';
    sec.innerHTML = `<div class="shelf-head"><h3>${m.shelf}</h3>
      <button type="button" class="shelf-more">전체 보기</button></div>`;
    const grid = document.createElement('div');
    grid.className = 'grid grid-deal';
    for (const p of picks) grid.appendChild(card(p));
    sec.appendChild(grid);
    sec.querySelector('.shelf-more').onclick = () => {
      state.market = name; state.category = '전체'; render();
      $('shop').scrollIntoView({ behavior: 'smooth' });
    };
    wrap.appendChild(sec);
  }
}

function renderDeals() {
  const grid = $('deal-grid');
  grid.innerHTML = '';
  // 할인율 높은 순 5개 — 타임세일 구좌
  const deals = pool().map((p) => ({ p, s: saleInfo(p) }))
    .filter((x) => x.s.off >= 15)
    .sort((a, b) => b.s.off - a.s.off).slice(0, 5);
  for (const { p } of deals) grid.appendChild(card(p));
}

function sparkline(profile, band) {
  const bands = ['00~06','06~11','11~14','14~17','17~21','21~24'];
  const max = Math.max(...bands.map((b) => profile[b] || 0)) || 1;
  const bars = bands.map((b, i) => {
    const h = Math.max(2, (profile[b] || 0) / max * 22);
    const hot = b === band;
    return `<rect x="${i * 11}" y="${24 - h}" width="8" height="${h}" rx="1.5"
      fill="${hot ? '#1e4d38' : '#d5d0c6'}"/>`;
  }).join('');
  return `<svg width="63" height="24" viewBox="0 0 63 24" aria-hidden="true">${bars}</svg>`;
}

function renderMarkets() {
  const strip = $('market-strip');
  strip.innerHTML = '';
  const all = document.createElement('button');
  for (const m of state.data.markets) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'mcard';
    b.setAttribute('aria-pressed', String(state.market === m.name));
    const band = BAND_OF_HOUR(new Date().getHours());
    b.innerHTML = `<span class="m-emoji">${MARKET_EMOJI[m.name] || '🏪'}</span>
      <b>${m.name.replace('청량리', '청량리 ')}</b><span>${m.humanKind || m.kind}</span>
      ${sparkline(m.timeProfile, band)}
      <em class="m-stat">${m.story || ''}</em>`;
    b.onclick = () => {
      state.market = state.market === m.name ? '전체' : m.name;
      render();
      $('shop').scrollIntoView({ behavior: 'smooth' });
    };
    strip.appendChild(b);
  }
  $('footer-markets').innerHTML = state.data.markets
    .map((m) => `<li><a href="#shop" data-fm="${m.name}">${m.name}</a></li>`).join('');
  document.querySelectorAll('[data-fm]').forEach((a) => a.onclick = () => {
    state.market = a.dataset.fm; state.category = '전체'; render();
  });
}

function renderCats() {
  const cats = ['전체', ...new Set(pool().map((p) => p.category))];
  const quick = $('cat-quick');
  quick.innerHTML = '';
  for (const c of cats.slice(0, 9)) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = c;
    b.setAttribute('aria-pressed', String(c === state.category));
    b.onclick = () => { state.category = c; render(); };
    quick.appendChild(b);
  }
  const panel = $('allcat-grid');
  panel.innerHTML = '';
  for (const c of cats) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = c;
    b.onclick = () => { state.category = c; $('allcat-panel').hidden = true; render(); };
    panel.appendChild(b);
  }
  // 하단 칩
  const chips = $('filters');
  chips.innerHTML = '';
  for (const c of cats) {
    const b = document.createElement('button');
    b.type = 'button';
    b.textContent = c;
    b.setAttribute('aria-pressed', String(c === state.category));
    b.onclick = () => { state.category = c; render(); };
    chips.appendChild(b);
  }
}

function renderProducts() {
  const list = visible();
  const grid = $('products');
  grid.innerHTML = '';
  $('empty').hidden = list.length > 0;
  $('count').textContent = `${list.length}개 상품`;
  for (const p of list) grid.appendChild(card(p));

  const parts = [];
  if (state.market !== '전체') parts.push(state.market);
  if (state.category !== '전체') parts.push(state.category);
  if (state.query.trim()) parts.push(`"${state.query.trim()}" 검색`);
  $('shop-title').textContent = parts.length ? parts.join(' · ') : '전체 상품';
}

function renderChannel() {
  document.querySelectorAll('.channel button').forEach((b) =>
    b.setAttribute('aria-pressed', String(b.dataset.channel === state.channel)));
  $('drawer-title').textContent = state.channel === 'b2b' ? '견적 요청 목록' : '장바구니';
  $('checkout').textContent = state.channel === 'b2b' ? '견적 요청하기' : '주문하기';
}

function render() {
  renderChannel();
  renderCats();
  renderLive();
  renderShelves();
  renderDeals();
  renderProducts();
  // 시장 카드 선택 상태 갱신
  document.querySelectorAll('.mcard').forEach((b, i) => {
    const name = state.data.markets[i]?.name;
    b.setAttribute('aria-pressed', String(state.market === name));
  });
}

/* ---------------- 카운트다운 (자정 리셋) ---------------- */
function tick() {
  const now = new Date();
  const end = new Date(now); end.setHours(24, 0, 0, 0);
  const s = Math.max(0, Math.floor((end - now) / 1000));
  const hh = String(Math.floor(s / 3600)).padStart(2, '0');
  const mm = String(Math.floor((s % 3600) / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  $('countdown').textContent = `${hh}:${mm}:${ss}`;
}

/* ---------------- 토스트·모달 ---------------- */
let toastTimer;
function toast(msg) {
  const t = $('toast');
  t.textContent = msg;
  t.hidden = false;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { t.classList.remove('show'); t.hidden = true; }, 2600);
}

function openModal(id) {
  $('modal-scrim').hidden = false;
  document.querySelectorAll('.modal').forEach((m) => m.hidden = true);
  $(id).hidden = false;
}
function closeModals() {
  $('modal-scrim').hidden = true;
  document.querySelectorAll('.modal').forEach((m) => m.hidden = true);
}

function renderOrders() {
  const orders = JSON.parse(localStorage.getItem('cl-orders') || '[]');
  const box = $('orders-list');
  if (!orders.length) {
    box.innerHTML = '<p class="modal-note">주문 내역이 없습니다.</p>';
    return;
  }
  box.innerHTML = orders.slice().reverse().map((o) => `
    <div class="order-row">
      <div><b>${o.id}</b> <span class="order-status">${o.channel === 'b2b' ? '견적 확인중' : '발송 준비중'}</span></div>
      <div class="order-items">${o.items.map((i) => `${i.name} ×${i.qty}`).join(', ')}</div>
      <div class="order-total">${won(o.total)} · ${o.date}</div>
    </div>`).join('');
}

/* ---------------- 장바구니 ---------------- */
function addToCart(p) {
  const line = state.cart[p.id] || { ...p, qty: 0 };
  line.qty += 1;
  state.cart[p.id] = line;
  localStorage.setItem('cl-cart', JSON.stringify(state.cart));
  renderCart();
  toast(`${p.name} — ${state.channel === 'b2b' ? '견적 목록' : '장바구니'}에 담았습니다`);
}
function setQty(id, d) {
  const l = state.cart[id];
  if (!l) return;
  l.qty += d;
  if (l.qty <= 0) delete state.cart[id];
  localStorage.setItem('cl-cart', JSON.stringify(state.cart));
  renderCart();
}
function renderCart() {
  const lines = Object.values(state.cart);
  const box = $('cart-items');
  box.innerHTML = lines.length ? '' : '<p class="empty">담긴 상품이 없습니다.</p>';
  for (const l of lines) {
    const el = document.createElement('div');
    el.className = 'line-item';
    el.innerHTML = `<div class="line-top"><div><strong>${l.name}</strong>
      <div class="sub">${l.market} · ${l.unit}</div></div><div>${won(l.price * l.qty)}</div></div>`;
    const qty = document.createElement('div');
    qty.className = 'qty';
    const minus = document.createElement('button'); minus.textContent = '−'; minus.onclick = () => setQty(l.id, -1);
    const n = document.createElement('span'); n.textContent = l.qty;
    const plus = document.createElement('button'); plus.textContent = '+'; plus.onclick = () => setQty(l.id, 1);
    qty.append(minus, n, plus);
    el.appendChild(qty);
    box.appendChild(el);
  }
  const total = lines.reduce((s, l) => s + l.price * l.qty, 0);
  const cnt = lines.reduce((s, l) => s + l.qty, 0);
  $('cart-total').textContent = won(total);
  $('cart-count').textContent = cnt;
  $('cart-count').hidden = cnt === 0;
}
function openDrawer(open) {
  $('drawer').dataset.open = String(open);
  $('scrim').dataset.open = String(open);
}

/* ---------------- 초기화 ---------------- */
function bind() {
  document.querySelectorAll('.channel button').forEach((b) => {
    b.onclick = () => {
      state.channel = b.dataset.channel;
      state.category = '전체';
      localStorage.setItem('cl-channel', state.channel);
      render();
    };
  });
  $('allcat-btn').onclick = () => { const p = $('allcat-panel'); p.hidden = !p.hidden; };
  const doSearch = () => { state.query = $('search').value; render(); $('shop').scrollIntoView({ behavior: 'smooth' }); };
  $('search-btn').onclick = doSearch;
  $('search').addEventListener('keydown', (e) => { if (e.key === 'Enter') doSearch(); });
  $('search').addEventListener('input', () => { state.query = $('search').value; renderProducts(); });
  $('cart-open').onclick = () => openDrawer(true);
  $('cart-close').onclick = () => openDrawer(false);
  $('scrim').onclick = () => openDrawer(false);
  $('checkout').onclick = () => {
    const lines = Object.values(state.cart);
    if (!lines.length) { toast('담긴 상품이 없습니다'); return; }
    const orders = JSON.parse(localStorage.getItem('cl-orders') || '[]');
    const id = 'CL' + String(Date.now()).slice(-8);
    orders.push({ id, channel: state.channel,
      items: lines.map((l) => ({ name: l.name, qty: l.qty })),
      total: lines.reduce((s, l) => s + l.price * l.qty, 0),
      date: new Date().toLocaleDateString('ko-KR') });
    localStorage.setItem('cl-orders', JSON.stringify(orders));
    state.cart = {};
    localStorage.setItem('cl-cart', '{}');
    renderCart();
    openDrawer(false);
    toast(state.channel === 'b2b'
      ? `견적 ${id} 접수 — 담당자가 확인 후 연락드립니다`
      : `주문 ${id} 접수 — 시장에서 직접 발송됩니다`);
  };
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { openDrawer(false); $('allcat-panel').hidden = true; closeModals(); } });
  // 로그인·주문·고객센터
  const user = localStorage.getItem('cl-user');
  if (user) $('nav-login').textContent = user + '님';
  $('nav-login').onclick = (e) => {
    e.preventDefault();
    if (localStorage.getItem('cl-user')) {
      localStorage.removeItem('cl-user');
      $('nav-login').textContent = '로그인';
      toast('로그아웃되었습니다');
    } else openModal('modal-login');
  };
  $('login-submit').onclick = () => {
    const email = $('login-email').value.trim() || 'guest@cl.market';
    const name = email.split('@')[0];
    localStorage.setItem('cl-user', name);
    $('nav-login').textContent = name + '님';
    closeModals();
    toast(`${name}님, 어서 오세요`);
  };
  $('nav-orders').onclick = (e) => { e.preventDefault(); renderOrders(); openModal('modal-orders'); };
  $('nav-support').onclick = (e) => { e.preventDefault(); openModal('modal-support'); };
  $('support-submit').onclick = () => {
    if (!$('support-msg').value.trim()) { toast('문의 내용을 입력해주세요'); return; }
    $('support-msg').value = '';
    closeModals();
    toast('문의가 접수되었습니다 — 영업일 기준 1일 내 답변드립니다');
  };
  $('modal-scrim').onclick = closeModals;

  // 배너 → 실제 필터 동작
  document.querySelectorAll('[data-banner]').forEach((b) => b.onclick = () => {
    const kind = b.dataset.banner;
    if (kind === 'b2b') {
      state.channel = 'b2b'; state.category = '전체';
      localStorage.setItem('cl-channel', 'b2b');
    } else if (kind === 'gift') {
      state.channel = 'b2c'; state.category = '선물세트'; state.market = '전체';
    } else {
      state.channel = 'b2c'; state.category = '제철 과일'; state.market = '전체';
    }
    render();
    $('shop').scrollIntoView({ behavior: 'smooth' });
  });
  setInterval(tick, 1000); tick();
}

fetch('img/p/map.json').then((r) => r.ok ? r.json() : {}).then((m) => { PIMG = m; if (state.data) render(); }).catch(() => {});
fetch('img/map.json').then((r) => r.ok ? r.json() : {}).then((m) => { IMG = m; if (state.data) render(); }).catch(() => {});

fetch('data.json?v=4')
  .then((r) => r.json())
  .then((data) => {
    state.data = data;
    renderMarkets();
    render();
    renderCart();
    bind();
  })
  .catch(() => {
    $('products').innerHTML = '<p class="empty">데이터를 불러오지 못했습니다.</p>';
  });
