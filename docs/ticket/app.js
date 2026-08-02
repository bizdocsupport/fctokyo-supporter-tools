const state={data:null,side:'ALL',competition:'ALL',hideFinished:true,newsOpen:true};
const $=(s)=>document.querySelector(s);
const esc=(v='')=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeUrl=(v='')=>/^https?:\/\//i.test(String(v).trim())?String(v).trim():'';
const parseDate=(v='')=>{if(!v)return null;const d=new Date(v);return Number.isNaN(d.getTime())?null:d};
const pad=n=>String(n).padStart(2,'0');
const jpDate=(d,withTime=true)=>{if(!d)return '未発表';const parts=new Intl.DateTimeFormat('ja-JP',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit',hour:withTime?'2-digit':undefined,minute:withTime?'2-digit':undefined,hour12:false}).formatToParts(d);const map=Object.fromEntries(parts.map(x=>[x.type,x.value]));return withTime?`${map.year}/${map.month}/${map.day} ${map.hour}:${map.minute}`:`${map.year}/${map.month}/${map.day}`};
const formatSale=v=>parseDate(v)?jpDate(parseDate(v),true):'未発表';
const matchDate=r=>{const d=parseDate(r.kickoff);if(d)return jpDate(d,true);return r.date_text||'未定'};
const isUpcoming=r=>{const d=parseDate(r.kickoff||r.sort_date);if(!d)return true;const now=new Date();const today=new Date(now.getFullYear(),now.getMonth(),now.getDate());return d>=today};
const hasConfirmedTime=v=>!!(v&&/(?:T|\s)\d{1,2}:\d{2}/.test(v)&&parseDate(v));
const isMufgNationalHome=r=>r.side==='HOME'&&String(r.stadium||'').replace(/\s/g,'').toUpperCase().includes('MUFG国立');
function calendarSpec(r){
  if(r.side==='AWAY'&&hasConfirmedTime(r.general_at)){
    return{
      start:parseDate(r.general_at),
      titlePrefix:'【チケット一般発売】',
      detailTitle:'FC東京 アウェイゲーム チケット一般発売'
    };
  }
  if(isMufgNationalHome(r)&&hasConfirmedTime(r.socio_at)){
    return{
      start:parseDate(r.socio_at),
      titlePrefix:'【SOCIO販売開始】',
      detailTitle:'FC東京 ホームゲーム SOCIOチケット販売開始'
    };
  }
  return null;
}
function calendarUrl(r){
  const spec=calendarSpec(r);
  if(!spec)return'';
  const start=spec.start,end=new Date(start.getTime()+30*60000);
  const utc=d=>`${d.getUTCFullYear()}${pad(d.getUTCMonth()+1)}${pad(d.getUTCDate())}T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`;
  const home=r.home||'未定',away=r.away||'FC東京',stadium=r.stadium||'未定';
  const source=safeUrl(r.ticket_source_url||r.match_url);
  const details=[spec.detailTitle,'',`試合日：${matchDate(r)}`,`対戦：${home} vs ${away}`,`会場：${stadium}`];
  if(source)details.push('','公式情報：',source);
  details.push('','※購入前に必ず公式情報をご確認ください。');
  const p=new URLSearchParams({action:'TEMPLATE',text:`${spec.titlePrefix}${home} vs ${away}`,dates:`${utc(start)}/${utc(end)}`,details:details.join('\n'),location:stadium,ctz:'Asia/Tokyo'});
  return`https://calendar.google.com/calendar/render?${p}`;
}
function filteredMatches(){let rows=[...(state.data?.matches||[])];rows.sort((a,b)=>(a.sort_date||'9999').localeCompare(b.sort_date||'9999'));if(state.side!=='ALL')rows=rows.filter(r=>r.side===state.side);if(state.competition!=='ALL')rows=rows.filter(r=>r.competition_group===state.competition);if(state.hideFinished)rows=rows.filter(isUpcoming);return rows}
function tableHtml(rows){const showHomeCols=state.side!=='AWAY';const showCompetition=state.competition==='ALL';return`<table class="matches-table"><thead><tr>${showCompetition?'<th>大会</th>':''}<th>試合日</th><th>区分</th><th>節</th><th>対戦カード</th><th>会場</th>${showHomeCols?'<th>SOCIO</th><th>MEMBERSHIP</th>':''}<th>一般発売</th><th>公式</th><th>カレンダー</th></tr></thead><tbody>${rows.map(r=>{const home=r.side==='HOME',official=safeUrl(r.ticket_source_url||r.match_url),cal=calendarUrl(r);return`<tr class="${home?'home':'away'}">${showCompetition?`<td>${esc(r.competition_name||'—')}</td>`:''}<td>${esc(matchDate(r))}</td><td><span class="side-badge ${home?'home':'away'}">${home?'H':'A'}</span></td><td>${esc(r.round_name||'—')}</td><td><strong>${esc(r.home||'未定')} vs ${esc(r.away||'未定')}</strong></td><td>${esc(r.stadium||'未定')}</td>${showHomeCols?`<td>${home?esc(formatSale(r.socio_at)):'<span class="muted-dash">—</span>'}</td><td>${home?esc(formatSale(r.membership_at)):'<span class="muted-dash">—</span>'}</td>`:''}<td class="${!home&&parseDate(r.general_at)?'sale-away':''}">${esc(formatSale(r.general_at))}</td><td>${official?`<a class="table-link" href="${esc(official)}" target="_blank" rel="noreferrer">確認 ↗</a>`:'<span class="muted-dash">—</span>'}</td><td>${cal?`<a class="table-link calendar-link" href="${esc(cal)}" target="_blank" rel="noreferrer">追加</a>`:'<span class="muted-dash">—</span>'}</td></tr>`}).join('')}</tbody></table>`}
function cardsHtml(rows){return rows.map(r=>{const home=r.side==='HOME',official=safeUrl(r.ticket_source_url||r.match_url),cal=calendarUrl(r),useSocio=isMufgNationalHome(r)&&hasConfirmedTime(r.socio_at),saleLabel=useSocio?'SOCIO':'一般発売',saleValue=useSocio?r.socio_at:r.general_at;return`<article class="match-card ${home?'home':'away'}"><div class="match-card-top"><span class="side-badge ${home?'home':'away'}">${home?'H':'A'}</span><span class="match-card-opponent">${esc(r.opponent||'未定')}</span><span class="match-card-date">${esc(matchDate(r))}</span></div><div class="match-card-details"><div class="match-card-detail"><small>${saleLabel}</small><strong class="${!home&&parseDate(r.general_at)?'sale-away':''}">${esc(formatSale(saleValue))}</strong></div><div class="match-card-detail"><small>会場</small><strong>${esc(r.stadium||'未定')}</strong></div></div><div class="match-card-actions">${official?`<a href="${esc(official)}" target="_blank" rel="noreferrer">公式情報 ↗</a>`:''}${cal?`<a class="calendar-link" href="${esc(cal)}" target="_blank" rel="noreferrer">カレンダーに追加</a>`:''}</div></article>`}).join('')}
function renderMatches(){const rows=filteredMatches();$('#result-count').textContent=rows.length;$('#empty-state').hidden=rows.length>0;$('#desktop-table').innerHTML=rows.length?tableHtml(rows):'';$('#mobile-cards').innerHTML=rows.length?cardsHtml(rows):''}
function renderNews(){const box=$('#news-list');if(!state.newsOpen){box.hidden=true;return}box.hidden=false;const rows=[...(state.data?.news||[])].sort((a,b)=>(b.published_at||'').localeCompare(a.published_at||'')).slice(0,20);box.innerHTML=rows.length?rows.map(n=>`<div class="news-row"><time>${esc(n.published_at||'')}</time><a href="${esc(safeUrl(n.url)||'#')}" target="_blank" rel="noreferrer">${esc(n.title||'タイトルなし')}</a><span>↗</span></div>`).join(''):'<div class="empty-state">ニュースデータはありません。</div>'}
function initControls(){document.querySelectorAll('#side-filter button').forEach(btn=>btn.addEventListener('click',()=>{document.querySelectorAll('#side-filter button').forEach(b=>b.classList.remove('active'));btn.classList.add('active');state.side=btn.dataset.value;renderMatches()}));$('#competition-filter').addEventListener('change',e=>{state.competition=e.target.value;renderMatches()});$('#hide-finished').addEventListener('change',e=>{state.hideFinished=e.target.checked;renderMatches()});$('#news-toggle').addEventListener('click',()=>{state.newsOpen=!state.newsOpen;$('#news-toggle').setAttribute('aria-expanded',String(state.newsOpen));$('#news-toggle').innerHTML=state.newsOpen?'取得済みニュースを閉じる <span>−</span>':'取得済みニュースを表示 <span>＋</span>';renderNews()})}
async function boot(){initControls();try{const res=await fetch('../data/ticket-data.json',{cache:'no-store'});if(!res.ok)throw new Error(`HTTP ${res.status}`);state.data=await res.json();const team=state.data.team||{},meta=state.data.metadata||{};$('#subtitle').textContent=`${team.subtitle||'FC東京の試合日とチケット発売日を、ひとつの一覧で。'}｜${team.season_label||''}・非公式`;$('#last-updated').textContent=meta.last_updated?jpDate(parseDate(meta.last_updated),true):'更新待ち';$('#data-status').textContent=meta.status==='success'?'DATA READY':'CHECK DATA';if(team.ticket_news_url)$('#official-news-link').href=team.ticket_news_url;if(team.disclaimer)$('#disclaimer-text').textContent=team.disclaimer;renderMatches();renderNews()}catch(err){console.error(err);$('#data-status').textContent='LOAD ERROR';$('#last-updated').textContent='データを読み込めません';$('#empty-state').hidden=false;$('#empty-state').textContent='ticket-data.jsonを読み込めません。GitHub Actionsまたはbuild_static_site.pyを実行してください。'}}
boot();
