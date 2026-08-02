(() => {
  'use strict';

  const STORAGE_KEY = 'tokyoChantsLyricsDraft';
  const data = window.CHANTS_DATA || { chants: [] };
  const published = window.CHANT_LYRICS || {};
  const list = document.querySelector('#editor-list');
  const template = document.querySelector('#editor-card-template');
  const search = document.querySelector('#editor-search');
  const saveState = document.querySelector('#save-state');
  const filledCount = document.querySelector('#filled-count');
  const totalCount = document.querySelector('#total-count');
  let saveTimer;

  function readDraft() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}');
      return { ...published, ...saved };
    } catch (error) {
      console.warn('下書きの読み込みに失敗しました。', error);
      return { ...published };
    }
  }

  let values = readDraft();

  function stableNumber(item, index) {
    return String(item.number || index + 1).padStart(2, '0');
  }

  function lineCount(text) {
    const trimmed = String(text || '').trim();
    return trimmed ? trimmed.split(/\r?\n/).length : 0;
  }

  function setSaveState(text) {
    saveState.textContent = text;
  }

  function persist() {
    const draftOnly = {};
    data.chants.forEach(item => {
      draftOnly[item.id] = String(values[item.id] || '');
    });
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draftOnly));
    setSaveState(`下書き保存済み ${new Date().toLocaleTimeString('ja-JP',{hour:'2-digit',minute:'2-digit'})}`);
  }

  function queueSave() {
    setSaveState('保存中…');
    clearTimeout(saveTimer);
    saveTimer = setTimeout(persist, 250);
  }

  function updateSummary() {
    const filled = data.chants.filter(item => String(values[item.id] || '').trim()).length;
    filledCount.textContent = String(filled);
    totalCount.textContent = String(data.chants.length);
  }

  function updateCard(card, item) {
    const text = String(values[item.id] || '');
    card.classList.toggle('has-text', Boolean(text.trim()));
    card.querySelector('.line-count').textContent = `${lineCount(text)}行 / ${text.length}文字`;
  }

  function render() {
    const query = search.value.trim().toLowerCase();
    list.replaceChildren();
    data.chants.forEach((item, index) => {
      const haystack = [item.title,item.scene,item.status,(item.aliases || []).join(' ')].join(' ').toLowerCase();
      if (query && !haystack.includes(query)) return;
      const card = template.content.firstElementChild.cloneNode(true);
      card.dataset.id = item.id;
      card.querySelector('.card-number').textContent = stableNumber(item,index);
      card.querySelector('.card-scene').textContent = item.scene;
      card.querySelector('.card-title').textContent = item.title;
      card.querySelector('.card-status').textContent = item.status || '—';
      const textarea = card.querySelector('.lyrics-input');
      textarea.value = String(values[item.id] || '');
      textarea.addEventListener('input', () => {
        values[item.id] = textarea.value;
        updateCard(card,item);
        updateSummary();
        queueSave();
      });
      card.querySelector('.clear-one').addEventListener('click', () => {
        if (!confirm(`「${item.title}」の歌詞を消去しますか？`)) return;
        textarea.value = '';
        values[item.id] = '';
        updateCard(card,item);
        updateSummary();
        persist();
      });
      updateCard(card,item);
      list.append(card);
    });
    updateSummary();
  }

  function exportLyrics() {
    persist();
    const ordered = {};
    data.chants.forEach(item => { ordered[item.id] = String(values[item.id] || ''); });
    const body = `// TOKYO CHANTS lyrics data\n// editor.html から書き出したファイルです。\nwindow.CHANT_LYRICS = ${JSON.stringify(ordered,null,2)};\n`;
    const blob = new Blob([body], { type: 'text/javascript;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'lyrics-data.js';
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setSaveState('lyrics-data.jsを書き出しました');
  }

  search.addEventListener('input', render);
  document.querySelector('#preview-button').addEventListener('click', () => {
    persist();
    window.open('./index.html?preview=1', '_blank', 'noopener');
  });
  document.querySelector('#export-button').addEventListener('click', exportLyrics);
  document.querySelector('#reset-button').addEventListener('click', () => {
    if (!confirm('ブラウザに保存した下書きをすべて破棄し、公開中のlyrics-data.jsへ戻しますか？')) return;
    localStorage.removeItem(STORAGE_KEY);
    values = { ...published };
    setSaveState('下書きを破棄しました');
    render();
  });

  setSaveState('下書きを読み込みました');
  render();
})();
