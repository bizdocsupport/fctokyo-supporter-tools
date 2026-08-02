(() => {
  'use strict';

  const data = window.CHANTS_DATA;
  if (!data) return;

  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const esc = (value = '') => String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const normalize = value => String(value || '').normalize('NFKC').toLowerCase().replace(/\s+/g, '');
  const youtubeSearch = query => `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;

  const state = { filter: 'all', search: '', sort: 'recommended' };
  const modal = $('#chant-modal');
  let lastFocus = null;

  function levelHtml(level) {
    return `<span class="chant-level" aria-label="覚えやすさ ${level}/3">${[1,2,3].map(n => `<i class="${n <= level ? 'on' : ''}"></i>`).join('')}</span>`;
  }

  function buildStarter() {
    const container = $('#starter-road');
    const chants = data.beginner.map(id => data.chants.find(item => item.id === id)).filter(Boolean);
    container.innerHTML = chants.map((item, index) => `
      <button class="starter-card" type="button" data-id="${esc(item.id)}">
        <span>${String(index + 1).padStart(2, '0')}</span>
        <p class="starter-label">${esc(item.scene).toUpperCase()}</p>
        <h3>${esc(item.title)}</h3>
        <p>${esc(item.tip)}</p>
        <b aria-hidden="true">＋</b>
      </button>`).join('');
  }

  function matches(item) {
    const inFilter = state.filter === 'all' || item.tags.includes(state.filter);
    if (!inFilter) return false;
    if (!state.search) return true;
    const haystack = normalize([item.title, ...(item.aliases || []), item.original, item.scene, item.summary, item.tip, ...item.tags].join(' '));
    return haystack.includes(normalize(state.search));
  }

  function ordered(items) {
    const copy = [...items];
    if (state.sort === 'easy') return copy.sort((a,b) => a.difficulty - b.difficulty || a.title.localeCompare(b.title, 'ja'));
    if (state.sort === 'name') return copy.sort((a,b) => a.title.localeCompare(b.title, 'ja'));
    return copy.sort((a,b) => Number(Boolean(b.featured)) - Number(Boolean(a.featured)) || data.chants.indexOf(a) - data.chants.indexOf(b));
  }

  function buildGrid() {
    const list = ordered(data.chants.filter(matches));
    $('#result-count').textContent = list.length;
    $('#empty-result').hidden = list.length > 0;
    $('#chant-grid').innerHTML = list.map((item, index) => `
      <button class="chant-card" type="button" data-id="${esc(item.id)}">
        <div class="chant-top">
          <span class="chant-index">${String(index + 1).padStart(2, '0')}</span>
          ${levelHtml(item.difficulty)}
        </div>
        <p class="chant-scene">${esc(item.scene).toUpperCase()}</p>
        <h3>${esc(item.title)}</h3>
        ${item.aliases?.length ? `<p class="aliases">別名：${item.aliases.map(esc).join(' / ')}</p>` : '<p class="aliases">&nbsp;</p>'}
        <div class="chant-bottom"><p>原曲：${esc(item.original)}</p><b aria-hidden="true">＋</b></div>
      </button>`).join('');
  }

  function buildAwayTimeline() {
    $('#away-timeline').innerHTML = data.away2019.map(item => `
      <li>
        <div><h3>${esc(item.title)}</h3><p>${esc(item.original)}</p></div>
        <a href="${youtubeSearch(item.query)}" target="_blank" rel="noreferrer" aria-label="${esc(item.title)}の動画を探す">↗</a>
      </li>`).join('');
  }

  function openModal(id, trigger) {
    const item = data.chants.find(chant => chant.id === id);
    if (!item) return;
    lastFocus = trigger || document.activeElement;
    const index = data.chants.indexOf(item) + 1;
    $('#modal-number').textContent = String(index).padStart(2, '0');
    $('#modal-scene').textContent = item.scene.toUpperCase();
    $('#modal-title').textContent = item.title;
    $('#modal-alias').textContent = item.aliases?.length ? `別名：${item.aliases.join(' / ')}` : '';
    $('#modal-level').innerHTML = levelHtml(item.difficulty);
    $('#modal-original').textContent = item.original;
    $('#modal-summary').textContent = item.summary;
    $('#modal-tip').textContent = item.tip;
    $('#modal-chant-link').href = data.sources.chantNavi;
    $('#modal-video-link').href = youtubeSearch(`FC東京 ${item.title} チャント`);
    $('#modal-original-link').href = youtubeSearch(`${item.original} 原曲`);
    modal.showModal();
    $('.modal-close', modal).focus();
  }

  function closeModal() {
    if (modal.open) modal.close();
    lastFocus?.focus?.();
  }

  function bindEvents() {
    $('#filter-row').addEventListener('click', event => {
      const button = event.target.closest('[data-filter]');
      if (!button) return;
      state.filter = button.dataset.filter;
      $$('.filter').forEach(item => item.classList.toggle('active', item === button));
      buildGrid();
    });

    $('#search-input').addEventListener('input', event => {
      state.search = event.target.value;
      buildGrid();
    });

    $('#sort-select').addEventListener('change', event => {
      state.sort = event.target.value;
      buildGrid();
    });

    document.addEventListener('click', event => {
      const card = event.target.closest('[data-id]');
      if (card) openModal(card.dataset.id, card);
    });

    $('.modal-close', modal).addEventListener('click', closeModal);
    modal.addEventListener('click', event => {
      if (event.target === modal) {
        const rect = modal.getBoundingClientRect();
        const inside = event.clientX >= rect.left && event.clientX <= rect.right && event.clientY >= rect.top && event.clientY <= rect.bottom;
        if (!inside) closeModal();
      }
    });
    modal.addEventListener('cancel', event => { event.preventDefault(); closeModal(); });

    document.addEventListener('keydown', event => {
      if (event.key === '/' && !/input|textarea|select/i.test(document.activeElement.tagName)) {
        event.preventDefault();
        $('#search-input').focus();
      }
    });

    const menuButton = $('.menu-button');
    const nav = $('.header-nav');
    menuButton.addEventListener('click', () => {
      const open = nav.classList.toggle('open');
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.setAttribute('aria-label', open ? 'メニューを閉じる' : 'メニューを開く');
    });
    nav.addEventListener('click', event => {
      if (event.target.closest('a')) {
        nav.classList.remove('open');
        menuButton.setAttribute('aria-expanded', 'false');
      }
    });
  }

  $('#updated-label').textContent = data.updated;
  buildStarter();
  buildGrid();
  buildAwayTimeline();
  bindEvents();
})();
