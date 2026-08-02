(() => {
  'use strict';

  const LYRICS_KEY = 'tokyoChantsLyricsDraft';
  const SETTINGS_KEY = 'tokyoChantsSettingsDraft';
  const data = window.CHANTS_DATA || { chants: [], beginner: [] };
  const publishedLyrics = window.CHANT_LYRICS || {};
  const publishedSettings = window.CHANT_SETTINGS || {};
  const list = document.querySelector('#editor-list');
  const template = document.querySelector('#editor-card-template');
  const search = document.querySelector('#editor-search');
  const saveState = document.querySelector('#save-state');
  const filledCount = document.querySelector('#filled-count');
  const requiredCount = document.querySelector('#required-count');
  const totalCount = document.querySelector('#total-count');
  let saveTimer;

  function loadJson(key) {
    try { return JSON.parse(localStorage.getItem(key) || '{}'); }
    catch (error) { console.warn(`${key}の読み込みに失敗しました。`, error); return {}; }
  }
  const lyrics = { ...publishedLyrics, ...loadJson(LYRICS_KEY) };
  const settings = { ...publishedSettings, ...loadJson(SETTINGS_KEY) };

  function stableNumber(item, index) { return String(item.number || index + 1).padStart(2, '0'); }
  function defaultRequired(item) { return (data.beginner || []).includes(item.id); }
  function defaultOrder(item) {
    const i = (data.beginner || []).indexOf(item.id);
    return i >= 0 ? i + 1 : data.chants.indexOf(item) + 100;
  }
  function resolved(item) {
    const setting = settings[item.id] || {};
    return {
      scene: Object.prototype.hasOwnProperty.call(setting,'scene') ? String(setting.scene || '') : String(item.scene || ''),
      tip: Object.prototype.hasOwnProperty.call(setting,'tip') ? String(setting.tip || '') : String(item.tip || ''),
      beginnerRequired: Object.prototype.hasOwnProperty.call(setting,'beginnerRequired') ? Boolean(setting.beginnerRequired) : defaultRequired(item),
      beginnerOrder: Number(setting.beginnerOrder) > 0 ? Number(setting.beginnerOrder) : defaultOrder(item)
    };
  }
  function lineCount(text) { const t=String(text||'').trim(); return t ? t.split(/\r?\n/).length : 0; }
  function setSaveState(text) { saveState.textContent = text; }
  function persist() {
    localStorage.setItem(LYRICS_KEY, JSON.stringify(lyrics));
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    setSaveState(`下書き保存済み ${new Date().toLocaleTimeString('ja-JP',{hour:'2-digit',minute:'2-digit'})}`);
  }
  function queueSave() { setSaveState('保存中…'); clearTimeout(saveTimer); saveTimer=setTimeout(persist,250); }
  function updateSummary() {
    filledCount.textContent = String(data.chants.filter(item => String(lyrics[item.id] || '').trim()).length);
    requiredCount.textContent = String(data.chants.filter(item => resolved(item).beginnerRequired).length);
    totalCount.textContent = String(data.chants.length);
  }
  function updateCard(card,item) {
    const r=resolved(item), text=String(lyrics[item.id]||'');
    card.classList.toggle('has-text',Boolean(text.trim()));
    card.classList.toggle('is-required',r.beginnerRequired);
    card.querySelector('.card-scene-preview').textContent=r.scene;
    card.querySelector('.line-count').textContent=`${lineCount(text)}行 / ${text.length}文字`;
    card.querySelector('.order-input').disabled=!r.beginnerRequired;
  }
  function ensureSetting(item) {
    const r=resolved(item);
    settings[item.id] = { scene:r.scene, tip:r.tip, beginnerRequired:r.beginnerRequired, beginnerOrder:r.beginnerOrder };
    return settings[item.id];
  }

  function render() {
    const query=search.value.trim().toLowerCase();
    list.replaceChildren();
    data.chants.forEach((item,index) => {
      const r=resolved(item);
      const haystack=[item.title,r.scene,item.status,(item.aliases||[]).join(' ')].join(' ').toLowerCase();
      if(query && !haystack.includes(query)) return;
      const card=template.content.firstElementChild.cloneNode(true);
      card.dataset.id=item.id;
      card.querySelector('.card-number').textContent=stableNumber(item,index);
      card.querySelector('.card-title').textContent=item.title;
      card.querySelector('.card-status').textContent=item.status||'—';
      const scene=card.querySelector('.scene-input');
      const tip=card.querySelector('.tip-input');
      const required=card.querySelector('.required-input');
      const order=card.querySelector('.order-input');
      const lyric=card.querySelector('.lyrics-input');
      scene.value=r.scene; tip.value=r.tip; required.checked=r.beginnerRequired; order.value=String(r.beginnerOrder); lyric.value=String(lyrics[item.id]||'');
      scene.addEventListener('input',()=>{ensureSetting(item).scene=scene.value;updateCard(card,item);queueSave();});
      tip.addEventListener('input',()=>{ensureSetting(item).tip=tip.value;queueSave();});
      required.addEventListener('change',()=>{ensureSetting(item).beginnerRequired=required.checked;updateCard(card,item);updateSummary();queueSave();});
      order.addEventListener('input',()=>{ensureSetting(item).beginnerOrder=Math.max(1,Number(order.value)||defaultOrder(item));queueSave();});
      lyric.addEventListener('input',()=>{lyrics[item.id]=lyric.value;updateCard(card,item);updateSummary();queueSave();});
      card.querySelector('.reset-one').addEventListener('click',()=>{
        if(!confirm(`「${item.title}」を公開中の値へ戻しますか？`)) return;
        if (publishedSettings[item.id]) settings[item.id] = { ...publishedSettings[item.id] };
        else delete settings[item.id];
        lyrics[item.id]=String(publishedLyrics[item.id]||'');
        persist(); render();
      });
      updateCard(card,item); list.append(card);
    });
    updateSummary();
  }

  function download(name,body) {
    const blob=new Blob([body],{type:'text/javascript;charset=utf-8'});
    const url=URL.createObjectURL(blob), a=document.createElement('a');
    a.href=url; a.download=name; document.body.append(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }
  function exportLyrics() {
    persist();
    const ordered={}; data.chants.forEach(item=>{ordered[item.id]=String(lyrics[item.id]||'');});
    download('lyrics-data.js',`// TOKYO CHANTS lyrics data\n// editor.html から書き出したファイルです。\nwindow.CHANT_LYRICS = ${JSON.stringify(ordered,null,2)};\n`);
    setSaveState('lyrics-data.jsを書き出しました');
  }
  function exportSettings() {
    persist();
    const ordered={}; data.chants.forEach(item=>{const r=resolved(item);ordered[item.id]={scene:r.scene,tip:r.tip,beginnerRequired:r.beginnerRequired,beginnerOrder:r.beginnerOrder};});
    download('chant-settings.js',`// TOKYO CHANTS editable settings\n// editor.html から書き出したファイルです。\nwindow.CHANT_SETTINGS = ${JSON.stringify(ordered,null,2)};\n`);
    setSaveState('chant-settings.jsを書き出しました');
  }

  search.addEventListener('input',render);
  document.querySelector('#preview-button').addEventListener('click',()=>{persist();window.open('./index.html?preview=1','_blank','noopener');});
  document.querySelector('#export-settings-button').addEventListener('click',exportSettings);
  document.querySelector('#export-lyrics-button').addEventListener('click',exportLyrics);
  document.querySelector('#reset-button').addEventListener('click',()=>{
    if(!confirm('ブラウザに保存したすべての下書きを破棄し、公開中の値へ戻しますか？')) return;
    localStorage.removeItem(LYRICS_KEY); localStorage.removeItem(SETTINGS_KEY); location.reload();
  });
  setSaveState('下書きを読み込みました'); render();
})();
