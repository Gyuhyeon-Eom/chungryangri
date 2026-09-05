/* 청량리 마켓 — 정적 커머스 프런트.
   data.json 은 분석 파이프라인(src/build_site_data.py)이 만든다.
   채널(도매/소매)이 1차 축이라, 채널을 바꾸면 시장 목록과 상품 단위가 함께 바뀐다. */

const KRW = new Intl.NumberFormat('ko-KR');
const won = (n) => KRW.format(n) + '원';

const state = {
  data: null,
  channel: localStorage.getItem('cl-channel') || 'b2c',
  category: '전체',
  market: '전체',
  cart: JSON.parse(localStorage.getItem('cl-cart') || '{}'),
};

const $ = (id) => document.getElementById(id);

/* ---------------- 렌더 ---------------- */

function renderHero() {
  const s = state.data.summary;
  $('s-markets').textContent = s.markets;
  $('s-stores').textContent = KRW.format(s.stores);
  $('s-merchants').textContent = KRW.format(s.merchants);
  $('s-products').textContent = new Set(state.data.products.map((p) => p.name)).size;
}

function renderMarkets() {
  const grid = $('market-grid');
  grid.innerHTML = '';
  for (const m of state.data.markets) {
    const both = m.channels.length === 2;
    const cls = both ? 'both' : m.channels[0];
    const label = both ? '도매 · 소매' : (m.channels[0] === 'b2b' ? '도매' : '소매');
    const el = document.createElement('article');
    el.className = 'market';
    el.innerHTML = `
      <span class="tag tag--${cls}">${label}</span>
      <h3>${m.name}</h3>
      <p style="font-size:13px;color:var(--muted);margin-bottom:14px">${m.kind}</p>
      <div class="market-meta">
        <div><dt>주 거래 시간</dt><dd>${m.peak}시</dd></div>
        <div><dt>주말 매출 비중</dt><dd>${m.weekendShare}%</dd></div>
        <div><dt>60대 이상 비중</dt><dd>${m.seniorShare ?? '—'}%</dd></div>
      </div>
      <div class="goods">${m.goods.map((g) => `<span>${g}</span>`).join('')}</div>`;
    grid.appendChild(el);
  }
  $('footer-markets').innerHTML = state.data.markets
    .map((m) => `<li>${m.name}</li>`).join('');
}

function visibleProducts() {
  return state.data.products.filter((p) =>
    p.channel === state.channel &&
    (state.category === '전체' || p.category === state.category) &&
    (state.market === '전체' || p.market === state.market));
}

function renderFilters() {
  const pool = state.data.products.filter((p) => p.channel === state.channel);
  const cats = ['전체', ...new Set(pool.map((p) => p.category))];
  const bar = $('filters');
  bar.innerHTML = '';
  for (const c of cats) {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.textContent = c;
    b.setAttribute('aria-pressed', String(c === state.category));
    b.onclick = () => { state.category = c; render(); };
    bar.appendChild(b);
  }
  const count = document.createElement('span');
  count.className = 'count';
  count.id = 'count';
  bar.appendChild(count);
}

function renderProducts() {
  const list = visibleProducts();
  const grid = $('products');
  grid.innerHTML = '';
  $('empty').hidden = list.length > 0;
  const c = $('count');
  if (c) c.textContent = `${list.length}개 상품`;

  for (const p of list) {
    const el = document.createElement('article');
    el.className = 'product';
    el.innerHTML = `
      <span class="cat">${p.category}</span>
      <h4>${p.name}</h4>
      <span class="from">${p.market} · ${p.origin}</span>
      <div class="price">${won(p.price)} <small>/ ${p.unit}</small></div>`;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn--ghost btn--sm';
    btn.textContent = state.channel === 'b2b' ? '견적 담기' : '장바구니';
    btn.onclick = () => addToCart(p);
    el.appendChild(btn);
    grid.appendChild(el);
  }
}

function renderChannelCopy() {
  const b2b = state.channel === 'b2b';
  $('hero-title').textContent = b2b
    ? '도매는 도매 시장에서만 보입니다'
    : '시장마다 파는 방식이 다릅니다';
  $('hero-lede').textContent = b2b
    ? '평일 도매 성격이 확인된 시장의 상품만 박스·kg 단위로 보여드립니다. 수량과 납기에 따라 단가가 달라져 견적으로 안내합니다.'
    : '청량리 9개 시장의 5년치 거래 데이터를 분석해 도매 중심 시장과 소매 중심 시장을 나눴습니다. 도매로 사실지 소매로 사실지 고르면, 그에 맞는 시장과 단위만 보입니다.';
  $('shop-title').textContent = b2b ? '도매로 구매하기' : '소매로 구매하기';
  $('shop-lede').textContent = b2b
    ? '박스·kg 단위 도매가입니다. 장바구니에 담으면 견적 요청으로 이어집니다.'
    : '낱개·소포장 단위로 구성했습니다. 시장에서 직접 발송합니다.';
  $('drawer-title').textContent = b2b ? '견적 요청 목록' : '장바구니';
  $('checkout').textContent = b2b ? '견적 요청하기' : '주문하기';
  document.querySelectorAll('.channel button').forEach((b) =>
    b.setAttribute('aria-pressed', String(b.dataset.channel === state.channel)));
}

/* ---------------- 장바구니 ---------------- */

function addToCart(p) {
  const line = state.cart[p.id] || { ...p, qty: 0 };
  line.qty += 1;
  state.cart[p.id] = line;
  persistCart();
  renderCart();
  openDrawer(true);
}

function setQty(id, delta) {
  const line = state.cart[id];
  if (!line) return;
  line.qty += delta;
  if (line.qty <= 0) delete state.cart[id];
  persistCart();
  renderCart();
}

function persistCart() {
  localStorage.setItem('cl-cart', JSON.stringify(state.cart));
}

function renderCart() {
  const lines = Object.values(state.cart);
  const box = $('cart-items');
  box.innerHTML = '';

  if (!lines.length) {
    box.innerHTML = '<p class="empty" style="padding:40px 0">담긴 상품이 없습니다.</p>';
  }
  for (const l of lines) {
    const el = document.createElement('div');
    el.className = 'line';
    el.innerHTML = `
      <div class="line-top">
        <div><strong>${l.name}</strong><div class="sub">${l.market} · ${l.unit}</div></div>
        <div>${won(l.price * l.qty)}</div>
      </div>`;
    const qty = document.createElement('div');
    qty.className = 'qty';
    const minus = document.createElement('button');
    minus.type = 'button'; minus.textContent = '−';
    minus.onclick = () => setQty(l.id, -1);
    const num = document.createElement('span');
    num.textContent = l.qty;
    const plus = document.createElement('button');
    plus.type = 'button'; plus.textContent = '+';
    plus.onclick = () => setQty(l.id, 1);
    qty.append(minus, num, plus);
    el.appendChild(qty);
    box.appendChild(el);
  }

  const total = lines.reduce((s, l) => s + l.price * l.qty, 0);
  const n = lines.reduce((s, l) => s + l.qty, 0);
  $('cart-total').textContent = won(total);
  const badge = $('cart-count');
  badge.textContent = n;
  badge.hidden = n === 0;
}

function openDrawer(open) {
  $('drawer').dataset.open = String(open);
  $('scrim').dataset.open = String(open);
}

/* ---------------- 초기화 ---------------- */

function render() {
  renderChannelCopy();
  renderFilters();
  renderProducts();
}

function bind() {
  document.querySelectorAll('.channel button').forEach((b) => {
    b.onclick = () => {
      state.channel = b.dataset.channel;
      state.category = '전체';
      localStorage.setItem('cl-channel', state.channel);
      render();
    };
  });
  $('cart-open').onclick = () => openDrawer(true);
  $('cart-close').onclick = () => openDrawer(false);
  $('scrim').onclick = () => openDrawer(false);
  $('checkout').onclick = () => {
    const lines = Object.values(state.cart);
    if (!lines.length) return;
    alert(state.channel === 'b2b'
      ? '견적 요청이 접수되었습니다. 담당자가 확인 후 연락드립니다.'
      : '주문이 접수되었습니다. 시장에서 직접 발송됩니다.');
  };
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') openDrawer(false);
  });
}

fetch('data.json')
  .then((r) => r.json())
  .then((data) => {
    state.data = data;
    renderHero();
    renderMarkets();
    render();
    renderCart();
    bind();
  })
  .catch(() => {
    document.getElementById('products').innerHTML =
      '<p class="empty">데이터를 불러오지 못했습니다. 로컬에서 열었다면 웹 서버로 실행해 주세요.</p>';
  });
