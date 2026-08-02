(() => {
  'use strict';
  const data=window.CHANTS_DATA||{chants:[],beginner:[]};
  const previewMode=new URLSearchParams(location.search).get('preview')==='1';
  let draftLyrics={},draftSettings={};
  if(previewMode){
    try{draftLyrics=JSON.parse(localStorage.getItem('tokyoChantsLyricsDraft')||'{}');}catch(error){console.warn(error);}
    try{draftSettings=JSON.parse(localStorage.getItem('tokyoChantsSettingsDraft')||'{}');}catch(error){console.warn(error);}
  }
  const lyrics={...(window.CHANT_LYRICS||{}),...draftLyrics};
  const settings={...(window.CHANT_SETTINGS||{}),...draftSettings};
  const esc=value=>String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const settingFor=item=>settings[item.id]||{};
  const sceneFor=item=>Object.prototype.hasOwnProperty.call(settingFor(item),'scene')?String(settingFor(item).scene||''):String(item.scene||'');
  const tipFor=item=>Object.prototype.hasOwnProperty.call(settingFor(item),'tip')?String(settingFor(item).tip||''):String(item.tip||'');
  const required=item=>Object.prototype.hasOwnProperty.call(settingFor(item),'beginnerRequired')?Boolean(settingFor(item).beginnerRequired):(data.beginner||[]).includes(item.id);
  const order=item=>{const n=Number(settingFor(item).beginnerOrder);if(n>0)return n;const i=(data.beginner||[]).indexOf(item.id);return i>=0?i+1:data.chants.indexOf(item)+100;};
  const items=data.chants.filter(required).sort((a,b)=>order(a)-order(b)||data.chants.indexOf(a)-data.chants.indexOf(b));
  document.querySelector('#sheet-count').textContent=String(items.length).padStart(2,'0');
  document.querySelector('#updated-label').textContent=data.updated||'—';
  document.querySelector('#print-list').innerHTML=items.length?items.map((item,index)=>{
    const lyric=String(lyrics[item.id]||'').trim();
    return `<article class="print-chant"><div class="chant-heading"><div class="chant-no">${String(index+1).padStart(2,'0')}</div><div><p class="chant-scene">${esc(sceneFor(item)).toUpperCase()}</p><h2>${esc(item.title)}</h2></div></div><div class="chant-content"><p class="lyrics${lyric?'':' empty'}">${lyric?esc(lyric):'歌詞未入力'}</p><p class="tip"><b>BEGINNER TIP</b>${esc(tipFor(item))}</p></div></article>`;
  }).join(''):'<p>「初心者でも必須」に設定されたチャントがありません。</p>';
  document.querySelector('#print-button').addEventListener('click',()=>window.print());
})();
