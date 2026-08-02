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

  const weightOf=item=>{
    const lyric=String(lyrics[item.id]||'').trim();
    const lyricLines=lyric?lyric.split(/\r?\n/).length:1;
    const lyricChars=Math.ceil(lyric.length/34);
    const tipChars=Math.ceil(tipFor(item).length/42);
    return 3+Math.max(lyricLines,lyricChars)+Math.max(1,tipChars)*0.75;
  };

  const splitIntoPanels=list=>{
    const panels=[[],[],[],[]];
    if(!list.length)return panels;
    const total=list.reduce((sum,item)=>sum+weightOf(item),0);
    const target=total/4;
    let panelIndex=0;
    let currentWeight=0;
    list.forEach((item,index)=>{
      const remainingItems=list.length-index;
      const remainingPanels=4-panelIndex;
      const itemWeight=weightOf(item);
      if(panelIndex<3 && currentWeight>0 && currentWeight+itemWeight>target && remainingItems>=remainingPanels){
        panelIndex+=1;
        currentWeight=0;
      }
      panels[panelIndex].push(item);
      currentWeight+=itemWeight;
    });
    return panels;
  };

  const panels=splitIntoPanels(items);
  const paper=document.querySelector('#paper');
  if(items.length>=10)paper.classList.add('ultra-compact');

  const cardHtml=(item,index)=>{
    const lyric=String(lyrics[item.id]||'').trim();
    return `<article class="print-chant"><div class="chant-heading"><div class="chant-no">${String(index+1).padStart(2,'0')}</div><div><p class="chant-scene">${esc(sceneFor(item)).toUpperCase()}</p><h2>${esc(item.title)}</h2></div></div><div class="chant-content"><p class="lyrics${lyric?'':' empty'}">${lyric?esc(lyric):'歌詞未入力'}</p><p class="tip"><b>BEGINNER TIP</b>${esc(tipFor(item))}</p></div></article>`;
  };

  let globalIndex=0;
  panels.forEach((panelItems,panelIndex)=>{
    const panel=document.querySelector(`#panel-${panelIndex+1}`);
    const estimated=panelItems.reduce((sum,item)=>sum+weightOf(item),0);
    if(estimated>18)panel.classList.add('dense');
    const isFirst=panelIndex===0;
    const heading=isFirst
      ? `<header class="panel-head panel-head-main"><div><p class="panel-kicker">FC TOKYO / UNOFFICIAL</p><h1 class="panel-title">初心者必須<span>TOKYO CHANTS</span></h1></div><b class="panel-number">${String(items.length).padStart(2,'0')}</b></header><p class="panel-sub">縦・横に半分ずつ折ってA6サイズに。試合中は周囲とコールリーダーに合わせてください。</p>`
      : `<header class="panel-head"><div><p class="panel-kicker">POCKET CHANT GUIDE</p><h2 class="panel-title">TOKYO CHANTS</h2></div><b class="panel-number">0${panelIndex+1}</b></header>`;
    const cards=panelItems.map(item=>cardHtml(item,globalIndex++)).join('');
    panel.innerHTML=`${heading}<div class="panel-list">${cards||'<p class="panel-sub">この面に表示するチャントはありません。</p>'}</div><div class="panel-footer"><span>fctokyo.xyz</span><span>${esc(data.updated||'—')}</span></div>`;
  });

  document.querySelector('#print-button').addEventListener('click',()=>window.print());
})();
