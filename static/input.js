// 「资料总览」页：把学生列表的统计，按学校「高三最高成就奖评审」Google 表格的格式排好，
// 方便复制贴到 Google 表格。数字由系统计算（套用「计入 / 不计」手动调整），这里只显示、不能改。
(function(){
const $=s=>document.querySelector(s);
const A=window.App;if(!A||!$('#tab-input'))return;
const esc=A.esc;
const INFO_W=[40,58,54,76];                 // 序、学号、班级、姓名 的宽度（固定在左边）
const FIELD_DEF=[{k:'role',t:'执委',u:'数量'},{k:'mid',t:'中层管理',u:'数量'},{k:'comm',t:'筹委',u:'数量'},{k:'hours',t:'服务',u:'小时'},{k:'awc',t:'活动/工作/比赛',u:''}];
let CFG=(window.EMBED_INPUT&&window.EMBED_INPUT.config)||null, q='', ROWS=[];

// 年份栏由程序按 Result 里最新的年份自动排（或 config.ini 手动指定）；资料更新时重新取一次
async function loadConfig(force){
  if(CFG&&!force)return;
  if(window.LIVE){for(let n=0;n<5;n++){try{CFG=(await (await fetch('api/input',{cache:'no-store'})).json()).config;break}catch(e){await new Promise(r=>setTimeout(r,1500))}}}
  if(!CFG)CFG={title:'最高成就奖评审',years:[],fields:FIELD_DEF};
}

// 每位学生每一年的数字（该年没有履历 → 放 0，红色标出）
function val(st,f){
  if(f==='awc')return `${st.acts}/${st.work}/${st.extComp+st.intComp}`;   // 活动/工作/比赛（工作的定义在 config/work.json）
  const v={role:st.roles,mid:st.mid,comm:st.comm,hours:st.hours}[f];
  return v==null?'':Math.round(v*100)/100;
}
function build(){
  const seen=new Set();
  ROWS=[...A.students].filter(s=>s.sid).sort((a,b)=>(a.code||'~').localeCompare(b.code||'~')||String(a.sid).localeCompare(String(b.sid)))
    .filter(s=>!seen.has(s.sid)&&seen.add(s.sid))
    .map(s=>{const yrs=new Set((s.years||[]).map(String));
      const miss=CFG.years.map(y=>!yrs.has(String(y.y))&&!y.optional);   // 留级等可选年份：没资料放 0 但不标红
      const cells=CFG.years.flatMap((y,i)=>{if(!yrs.has(String(y.y)))return CFG.fields.map(f=>f.k==='awc'?'0/0/0':0);const st=A.statsFor(s,y.y);return CFG.fields.map(f=>val(st,f.k))});
      return {s,sid:s.sid,cls:s.cls||'',name:s.cn||s.en||'',cells,miss,none:CFG.years.every((y,i)=>y.optional||miss[i])&&CFG.years.some(y=>!y.optional)}});
}
function visible(){
  const t=q.trim().toLowerCase();
  return !t?ROWS:ROWS.filter(r=>[r.sid,r.cls,r.name,r.s.en,r.s.club,r.s.code].some(x=>String(x||'').toLowerCase().includes(t)));
}
function render(){
  if(!CFG)return;
  build();
  $('#intitle').textContent=CFG.title;
  const nf=CFG.fields.length;
  const stk=i=>`style="left:${INFO_W.slice(0,i).reduce((a,b)=>a+b,0)}px;min-width:${INFO_W[i]}px;max-width:${INFO_W[i]}px"`;
  const r1=['序','学号','班级','姓名(中)'].map((t,i)=>`<th rowspan="2" class="fix${i===3?' fixlast':''}" ${stk(i)}>${t}</th>`).join('')
    +CFG.years.map((y,i)=>`<th colspan="${nf}" class="iyh ${i%2?'alt':''}">${esc(y.y)}${y.label?`<span>(${esc(y.label)})</span>`:''}</th>`).join('');
  const r2=CFG.years.map((y,i)=>CFG.fields.map((f,fi)=>`<th class="ifh ${fi===0?'first':''} ${i%2?'alt':''}">${esc(f.t).replace(/\//g,'/<wbr>')}${f.u?`<span>(${esc(f.u)})</span>`:''}</th>`).join('')).join('');
  const vis=visible();
  const body=vis.map((r,n)=>`<tr${r.none?' class="nodata"':''}><td class="fix" ${stk(0)}>${n+1}</td><td class="fix" ${stk(1)}>${esc(r.sid)}</td><td class="fix" ${stk(2)}>${esc(r.cls)}</td><td class="fix fixlast" ${stk(3)}><a href="#" data-open="${esc(r.sid)}" title="${esc(r.s.code||'')} ${esc(r.s.club||'')}${r.miss.some(Boolean)?' · 没有资料的年份：'+esc(CFG.years.filter((y,i)=>r.miss[i]).map(y=>y.y).join('、')):''}">${esc(r.name)}</a></td>`
    +r.cells.map((v,ci)=>{const fi=ci%nf,yi=Math.floor(ci/nf),m=r.miss[yi];return `<td class="in${fi===0?' first':''}${yi%2?' alt':''}${m?' miss':(v===0||v==='0/0/0')?' zero':''}"${m?' title="这一年没有资料"':''}>${esc(v)}</td>`}).join('')+'</tr>').join('');
  $('#intbl').innerHTML=`<thead><tr>${r1}</tr><tr>${r2}</tr></thead><tbody>${body||`<tr><td colspan="${4+nf*CFG.years.length}" class="muted" style="padding:30px;text-align:center">没有符合条件的学生</td></tr>`}</tbody>`;
  const nMiss=ROWS.filter(r=>r.miss.some(Boolean)).length,nNone=ROWS.filter(r=>r.none).length;
  $('#incount').innerHTML=`显示 ${vis.length} / ${ROWS.length} 人`+(nMiss?` · <span class="missnote">红色 = 没有资料（放 0）：${nMiss} 人有年份缺资料${nNone?`，${nNone} 人全部没有`:''}</span>`:'');
}
const isShown=()=>!$('#tab-input').classList.contains('hidden');

// ----- 复制成 Google 表格 / Excel 可直接贴上的格式（Tab 分隔）
async function copy(onlyNums){
  const t=visible().map((r,n)=>(onlyNums?[]:[n+1,r.sid,r.cls,r.name]).concat(r.cells).join('\t')).join('\n');
  try{await navigator.clipboard.writeText(t)}catch(e){const ta=document.createElement('textarea');ta.value=t;document.body.appendChild(ta);ta.select();document.execCommand('copy');ta.remove()}
  A.toast(onlyNums?`已复制 ${visible().length} 位学生的数字：到 Google 表格点第一位学生 ${CFG.years[0]?CFG.years[0].y:''}「执委」那一格，按 Ctrl+V`:`已复制 ${visible().length} 行：到 Google 表格点「序」第一格，按 Ctrl+V`);
}
$('#incopy').onclick=()=>copy(false);
$('#incopy2').onclick=()=>copy(true);
$('#inq').oninput=e=>{q=e.target.value;render()};
$('#intbl').addEventListener('click',e=>{const a=e.target.closest('[data-open]');if(a){e.preventDefault();A.openStudent(a.dataset.open)}});

document.addEventListener('app:data',()=>{(window.LIVE?loadConfig(true):Promise.resolve()).then(()=>{if(isShown())render()})});
document.addEventListener('app:tab',e=>{if(e.detail==='input')render()});
loadConfig().then(()=>{if(isShown())render()});
})();
