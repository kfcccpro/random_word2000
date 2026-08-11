from pathlib import Path

P = Path('index.html')
s = P.read_text(encoding='utf-8')


def section(start, end, new):
    global s
    a = s.find(start)
    if a < 0:
        raise SystemExit(f'missing start marker: {start[:80]}')
    b = s.find(end, a)
    if b < 0:
        raise SystemExit(f'missing end marker: {end[:80]}')
    s = s[:a] + new.rstrip() + '\n' + s[b:]


def once(old, new):
    global s
    if old not in s:
        raise SystemExit(f'missing replacement marker: {old[:100]}')
    s = s.replace(old, new, 1)


# ---- visible version / iPad interaction ----
s = s.replace('WORD MASTER Auto Sync v7', 'WORD MASTER Auto Sync v8')
s = s.replace('Auto Sync v7', 'Auto Sync v8')
s = s.replace("s.meta.build='v7'", "s.meta.build='v8'")
s = s.replace("meta:{legacyImported:false,updatedAt:new Date().toISOString(),build:'wm-v7-20260806'}", "meta:{legacyImported:false,updatedAt:new Date().toISOString(),build:'wm-v8-20260811'}")
s = s.replace('appVersion:7', 'appVersion:8')
s = s.replace('schemaVersion:7', 'schemaVersion:8')

css = """
/* v8: iPad/Safari double-tap zoom suppression. Panning and pinch zoom remain available. */
html,body,button,.btn,.option,.prompt-card,.nav-btn,.hero,.card{touch-action:manipulation}
.wrong-memory{max-width:680px;margin:0 auto;padding:18px 0;text-align:center}
.wrong-memory .memory-label{font-size:13px;font-weight:800;letter-spacing:.12em;color:var(--red-2);margin:16px 0}
.wrong-memory .memory-word{font-family:var(--display);font-size:clamp(42px,8vw,72px);font-weight:800;letter-spacing:-.04em;margin:28px 0 12px}
.wrong-memory .memory-mean{font-size:clamp(20px,4vw,30px);font-weight:800;line-height:1.55;color:var(--text);padding:22px;background:var(--panel);border:1px solid var(--line);border-radius:var(--radius-lg)}
.wrong-memory .memory-hint{margin-top:18px;color:var(--muted);font-size:13px}
"""
if '/* v8: iPad/Safari double-tap zoom suppression.' not in s:
    s = s.replace('</style>', css + '\n</style>', 1)

# ---- state schema: preserve historical wrongDb, add active reviewDb ----
section('function defaultState(){', 'function normalizeState(s){', """
function defaultState(){return{version:8,createdAt:new Date().toISOString(),settings:{dailyCount:80,enKoPercent:100},meta:{legacyImported:false,updatedAt:new Date().toISOString(),build:'wm-v8-20260811'},wrongDb:{},reviewDb:{},wordStats:{},dailySets:{},dailyResults:{},startReviewDone:{},startReviewedSources:{},endReviewDone:{},history:[]}}
""")

section('function normalizeState(s){', 'function loadState(){', """
function normalizeState(s){
  const d=defaultState();if(!s||typeof s!=='object')s=d;
  for(const k of Object.keys(d))if(s[k]===undefined)s[k]=d[k];
  if(!s.settings||typeof s.settings!=='object')s.settings={dailyCount:80,enKoPercent:100};
  s.settings.dailyCount=clamp(parseInt(s.settings.dailyCount,10)||0,0,150);
  s.settings.enKoPercent=clamp(parseInt(s.settings.enKoPercent,10),0,100);if(Number.isNaN(s.settings.enKoPercent))s.settings.enKoPercent=100;
  if(!s.meta)s.meta={legacyImported:false,updatedAt:new Date().toISOString(),build:'v8'};
  if(!s.meta.updatedAt)s.meta.updatedAt=s.createdAt||new Date().toISOString();
  s.meta.build='v8';
  if(!Array.isArray(s.history))s.history=[];
  for(const k of ['wrongDb','reviewDb','wordStats','dailySets','dailyResults','startReviewDone','startReviewedSources','endReviewDone'])if(!s[k]||typeof s[k]!=='object')s[k]={};
  // v7 -> v8: historical wrongs enter the review queue once. Daily cap prevents overload.
  for(const [id,r] of Object.entries(s.wrongDb||{}))if(BY_ID[id]&&(r?.count||0)>0&&!s.reviewDb[id]){
    const base=/^\\d{4}-\\d{2}-\\d{2}$/.test(String(r.lastWrong||''))?r.lastWrong:localDate();
    s.reviewDb[id]={active:true,stage:0,dueDate:localDate(),baseDate:base,lastWrong:r.lastWrong||base,lastReview:'',reviewCount:r.reviewCount||0,stableAt:'',updatedAt:new Date().toISOString()};
  }
  for(const [id,r] of Object.entries(s.reviewDb||{})){
    if(!BY_ID[id]||!r){delete s.reviewDb[id];continue}
    r.active=r.active!==false;r.stage=clamp(parseInt(r.stage,10)||0,0,2);r.dueDate=r.active?(r.dueDate||localDate()):'';r.baseDate=r.baseDate||r.lastWrong||localDate();r.lastReview=r.lastReview||'';r.reviewCount=parseInt(r.reviewCount,10)||0;r.stableAt=r.stableAt||'';r.updatedAt=r.updatedAt||s.meta.updatedAt||new Date().toISOString();
  }
  for(const [date,set] of Object.entries(s.dailySets)){if(!set)continue;set.date=set.date||date;set.sessionId=set.sessionId||('set:'+date+':'+(set.createdAt||'legacy'));if(!Array.isArray(set.reviewIds))set.reviewIds=[]}
  for(const [date,res] of Object.entries(s.dailyResults)){if(!res)continue;res.date=res.date||date;res.sessionId=res.sessionId||('session:'+date+':'+(res.startedAt||res.finishedAt||'legacy'))}
  s.history=s.history.filter(Boolean).map((h,i)=>({...h,sessionId:h.sessionId||('history:'+(h.date||'unknown')+':'+(h.startedAt||h.finishedAt||i))}));
  repairStateDates(s);s.version=8;return s;
}
""")

# ---- cloud merge: add reviewDb merge while retaining historical wrongDb ----
section('function mergeStateSnapshots(remoteState,localState){', 'function applyRemoteEnvelope(env,force=false){', """
function mergeStateSnapshots(remoteState,localState){
  const R=normalizeState(JSON.parse(JSON.stringify(remoteState||defaultState()))),L=normalizeState(JSON.parse(JSON.stringify(localState||defaultState()))),out=normalizeState(JSON.parse(JSON.stringify(R)));
  const rAct=stateActivityScore(R),lAct=stateActivityScore(L),rTime=Date.parse(R.meta?.updatedAt||'')||0,lTime=Date.parse(L.meta?.updatedAt||'')||0;
  out.settings=(lAct>rAct&&lTime>=rTime)?{...L.settings}:{...R.settings};
  for(const id of new Set([...Object.keys(R.wordStats||{}),...Object.keys(L.wordStats||{})])){
    const a=R.wordStats?.[id]||{},b=L.wordStats?.[id]||{};
    out.wordStats[id]={served:Math.max(a.served||0,b.served||0),correct:Math.max(a.correct||0,b.correct||0),wrong:Math.max(a.wrong||0,b.wrong||0),lastServed:String(a.lastServed||'')>=String(b.lastServed||'')?(a.lastServed||''):(b.lastServed||'')};
  }
  for(const id of new Set([...Object.keys(R.wrongDb||{}),...Object.keys(L.wrongDb||{})])){
    const a=R.wrongDb?.[id]||{},b=L.wrongDb?.[id]||{};
    out.wrongDb[id]={count:Math.max(a.count||0,b.count||0),firstWrong:earlierIso(a.firstWrong,b.firstWrong),lastWrong:laterIso(a.lastWrong,b.lastWrong),reviewCount:Math.max(a.reviewCount||0,b.reviewCount||0),lastFocusDate:String(a.lastFocusDate||'')>=String(b.lastFocusDate||'')?(a.lastFocusDate||''):(b.lastFocusDate||'')};
  }
  for(const id of new Set([...Object.keys(R.reviewDb||{}),...Object.keys(L.reviewDb||{})])){
    const a=R.reviewDb?.[id],b=L.reviewDb?.[id];
    if(!a){out.reviewDb[id]=JSON.parse(JSON.stringify(b));continue}if(!b){out.reviewDb[id]=JSON.parse(JSON.stringify(a));continue}
    const at=Date.parse(a.updatedAt||'')||0,bt=Date.parse(b.updatedAt||'')||0;
    let chosen;if(at!==bt)chosen=at>bt?a:b;else if(!!a.active!==!!b.active)chosen=a.active?a:b;else chosen=(a.stage||0)>=(b.stage||0)?a:b;
    out.reviewDb[id]=JSON.parse(JSON.stringify(chosen));
  }
  const dates=new Set([...Object.keys(R.dailyResults||{}),...Object.keys(L.dailyResults||{}),...Object.keys(R.dailySets||{}),...Object.keys(L.dailySets||{})]);
  for(const d of dates){
    const rr=R.dailyResults?.[d],lr=L.dailyResults?.[d],side=chooseResultSide(rr,lr),chosen=side==='local'?lr:rr;
    if(chosen)out.dailyResults[d]=JSON.parse(JSON.stringify(chosen));else delete out.dailyResults[d];
    const set=(side==='local'?L.dailySets?.[d]:R.dailySets?.[d])||R.dailySets?.[d]||L.dailySets?.[d];
    if(set)out.dailySets[d]=JSON.parse(JSON.stringify(set));else delete out.dailySets[d];
  }
  for(const k of ['startReviewDone','startReviewedSources','endReviewDone'])out[k]={...(R[k]||{}),...(L[k]||{})};
  const hm=new Map();
  for(const h of [...(R.history||[]),...(L.history||[])]){if(!h?.date)continue;const key=h.sessionId||('history:'+h.date+':'+(h.startedAt||h.finishedAt||'')),prev=hm.get(key);if(!prev||String(h.finishedAt||'')>String(prev.finishedAt||''))hm.set(key,JSON.parse(JSON.stringify({...h,sessionId:key})))}
  out.history=[...hm.values()].sort((a,b)=>String(b.finishedAt||b.date).localeCompare(String(a.finishedAt||a.date))).slice(0,1200);
  out.createdAt=earlierIso(R.createdAt,L.createdAt)||new Date().toISOString();
  out.meta={...(R.meta||{}),...(L.meta||{}),updatedAt:new Date(Math.max(rTime,lTime)||Date.now()).toISOString(),build:'v8'};
  repairStateDates(out);return normalizeState(out);
}
""")

# ---- active review helpers ----
section('function wrongIdsFor(state=S){', 'function semanticFamily(w){', """
function wrongIdsFor(state=S){return Object.keys(state.wrongDb||{}).map(Number).filter(id=>BY_ID[id]&&(state.wrongDb[id]?.count||0)>0)}
function wrongIds(){return wrongIdsFor(S)}
function wrongCountFor(state=S){return wrongIdsFor(state).length}
function wrongCount(){return wrongCountFor(S)}
function totalWrongEventsFor(state=S){return Object.values(state.wrongDb||{}).reduce((a,r)=>a+(r.count||0),0)}
function totalWrongEvents(){return totalWrongEventsFor(S)}
function reviewIdsFor(state=S,activeOnly=true){return Object.keys(state.reviewDb||{}).map(Number).filter(id=>BY_ID[id]&&(!activeOnly||state.reviewDb[id]?.active!==false))}
function activeReviewCountFor(state=S){return reviewIdsFor(state,true).length}
function activeReviewCount(){return activeReviewCountFor(S)}
function stableReviewCountFor(state=S){return Object.values(state.reviewDb||{}).filter(r=>r&&r.active===false&&r.stableAt).length}
function dueReviewIds(date=localDate(),limit=20,state=S){
  return reviewIdsFor(state,true).filter(id=>(state.reviewDb[id]?.dueDate||date)<=date).sort((a,b)=>{
    const A=state.reviewDb[a],B=state.reviewDb[b],ad=A.dueDate||'',bd=B.dueDate||'';if(ad!==bd)return ad.localeCompare(bd);
    const ac=state.wrongDb[a]?.count||0,bc=state.wrongDb[b]?.count||0;if(ac!==bc)return bc-ac;
    return String(B.lastWrong||'').localeCompare(String(A.lastWrong||''));
  }).slice(0,Math.max(0,limit));
}
function isScheduledReview(set,id){return Array.isArray(set?.reviewIds)&&set.reviewIds.includes(Number(id))}
function percent(a,b){return b?Math.round(a/b*100):0}
""")

# ---- daily set: scheduled review is included inside the fixed daily total ----
section('function getDailySet(date=localDate()){', 'function peekTodaySet(){', """
function getDailySet(date=localDate()){
  const expected=effectiveDailyCount(date);let existingResult=S.dailyResults[date];
  if(existingResult&&!resultBelongsToDate(existingResult,date)){
    const actual=sessionDateOf(existingResult,'');if(actual&&actual!==date){S.dailyResults[actual]=existingResult;if(S.dailySets[date])S.dailySets[actual]=S.dailySets[date]}
    delete S.dailyResults[date];delete S.dailySets[date];delete S.endReviewDone[date];existingResult=null;save({skipCloud:true});
  }
  if(S.dailySets[date]){
    const set=S.dailySets[date],unstarted=!existingResult||(existingResult.currentIndex||0)===0;
    const needsV8=date===localDate()&&unstarted&&!Array.isArray(set.reviewIds);
    if(date===localDate()&&unstarted&&(set.ids?.length!==expected||needsV8)){delete S.dailySets[date];delete S.dailyResults[date];delete S.endReviewDone[date]}
    else{set.target=set.target??set.ids?.length??expected;set.reviewIds=Array.isArray(set.reviewIds)?set.reviewIds:[];set.sessionId=set.sessionId||existingResult?.sessionId||('set:'+date+':'+(set.createdAt||Date.now()));if(!Array.isArray(set.directions)||set.directions.length!==set.ids.length)set.directions=buildDirections(set.ids.length,date,set.enKoPercent??configuredEnKo());return set}
  }
  const target=expected,createdAt=new Date().toISOString(),sessionId='session:'+date+':'+createdAt+':'+Math.random().toString(36).slice(2,8);
  if(target===0){S.dailySets[date]={date,sessionId,mode:'off',target:0,ids:[],reviewIds:[],groups:[],directions:[],enKoPercent:configuredEnKo(),catchUp:false,createdAt};save();return S.dailySets[date]}
  const reviewIds=dueReviewIds(date,Math.min(20,target));
  const activeSet=new Set(reviewIdsFor(S,true));
  const tieOrder=seededShuffle(WORDS,`${date}:v8-normal-tie:${target}`),rank=new Map(tieOrder.map((w,i)=>[w.id,i]));
  const normalTarget=Math.max(0,target-reviewIds.length);
  const normalIds=WORDS.filter(w=>!activeSet.has(w.id)).sort((a,b)=>{const as=S.wordStats[a.id]?.served||0,bs=S.wordStats[b.id]?.served||0;if(as!==bs)return as-bs;const al=S.wordStats[a.id]?.lastServed||'',bl=S.wordStats[b.id]?.lastServed||'';if(al!==bl)return al.localeCompare(bl);return(rank.get(a.id)||0)-(rank.get(b.id)||0)}).slice(0,normalTarget).map(w=>w.id);
  const ids=seededShuffle([...reviewIds,...normalIds],`${date}:v8-review-mix:${target}`);
  const enKoPercent=configuredEnKo(),directions=buildDirections(ids.length,date,enKoPercent),catchUp=target===160&&catchUpRequiredFor(S,date);
  S.dailySets[date]={date,sessionId,mode:'mixed',target:ids.length,requestedTarget:target,ids,reviewIds,groups:[{label:'오늘 학습',ids:ids.slice()}],directions,enKoPercent,catchUp,createdAt};save();return S.dailySets[date];
}
""")

# ---- attempt / spaced review state machine ----
section('function recordAttempt(id,ok,date){', 'function pendingStartReview(date=localDate()){', """
function recordAttempt(id,ok,date,isReview=false){
  const st=S.wordStats[id]||{served:0,correct:0,wrong:0,lastServed:''};st.served=(st.served||0)+1;st.lastServed=date;if(ok)st.correct=(st.correct||0)+1;else st.wrong=(st.wrong||0)+1;S.wordStats[id]=st;
  if(!ok){
    const r=S.wrongDb[id]||{count:0,firstWrong:date,lastWrong:date,reviewCount:0,lastFocusDate:''};r.count=(r.count||0)+1;r.firstWrong=r.firstWrong||date;r.lastWrong=date;S.wrongDb[id]=r;
    const q=S.reviewDb[id]||{};q.active=true;q.stage=0;q.baseDate=date;q.dueDate=shiftDate(date,1);q.lastWrong=date;q.lastReview=isReview?date:(q.lastReview||'');q.reviewCount=(q.reviewCount||0)+(isReview?1:0);q.stableAt='';q.updatedAt=new Date().toISOString();S.reviewDb[id]=q;return;
  }
  if(isReview){
    const q=S.reviewDb[id]||{active:true,stage:0,dueDate:date,baseDate:date,reviewCount:0};q.reviewCount=(q.reviewCount||0)+1;q.lastReview=date;
    if((q.stage||0)===0){q.stage=1;q.active=true;q.dueDate=shiftDate(date,2)}
    else if(q.stage===1){q.stage=2;q.active=true;q.dueDate=shiftDate(date,3)}
    else{q.stage=2;q.active=false;q.dueDate='';q.stableAt=date}
    q.updatedAt=new Date().toISOString();S.reviewDb[id]=q;if(S.wrongDb[id])S.wrongDb[id].reviewCount=Math.max(S.wrongDb[id].reviewCount||0,q.reviewCount||0);
  }
}
""")

# ---- student home: no separate review gate, current review count only ----
section('function renderToday(){', 'function startQuiz(){', """
function renderToday(){
  reviewState=null;const root=document.getElementById('viewToday');let existing=peekTodaySet(),res=getResult();
  if(existing&&(!res||(res.currentIndex||0)===0)&&existing.ids?.length!==effectiveDailyCount())existing=getDailySet();
  const target=existing?existing.ids.length:effectiveDailyCount(),catchup=existing?.catchUp??catchUpRequiredFor();
  if(res&&!res.quizFinished&&res.currentIndex>0){renderQuiz();return}
  if(target===0){root.innerHTML=`<div class=\"hero\"><div class=\"hero-inner\"><div class=\"mode-line\"><span class=\"mode-dot\"></span>오늘 배정 없음</div><div class=\"hero-kicker\">TODAY'S SET</div><div class=\"hero-number\">0</div><div class=\"hero-desc\">관리자가 오늘 학습량을 0개로 설정했습니다.</div><button class=\"btn btn-secondary big\" disabled>오늘 학습 없음</button></div></div>`;return}
  const set=existing||getDailySet(),actual=set.ids.length,done=todayCompleted(),progress=res?percent(res.currentIndex,actual):0,dc=directionCounts(actual,set.enKoPercent??configuredEnKo()),reviewN=set.reviewIds?.length||0,activeN=activeReviewCount();
  const cta=done?'오늘 결과 보기':res?'학습 계속하기':`${actual}개 학습 시작`,action=done?'showResult()':'startQuiz()';
  root.innerHTML=`${catchup?`<div class=\"alert danger-note\"><b>매일 학습 보충:</b> 어제 학습을 완료하지 않아 오늘 목표가 자동으로 160개로 조정되었습니다.</div>`:''}<div class=\"hero\"><div class=\"hero-inner\"><div class=\"mode-line\"><span class=\"mode-dot\"></span>오늘 학습 ${actual}개 · 복습 ${reviewN} · 일반 ${actual-reviewN}</div><div class=\"hero-kicker\">TODAY'S SET</div><div class=\"hero-number\">${actual}</div><div class=\"hero-desc\">복습은 별도 학습으로 추가되지 않고 오늘 ${actual}개 안에 자동으로 섞입니다. PC와 아이패드 진도는 자동 공유됩니다.</div><button class=\"btn btn-primary big\" onclick=\"${action}\">${cta}</button>${done?`<div style=\"margin-top:10px\"><button class=\"btn btn-secondary\" onclick=\"startExtraSession()\">새로운 ${actual}개 추가 학습</button></div>`:''}</div></div><div class=\"grid g3\" style=\"margin-bottom:15px\"><div class=\"card\"><div class=\"stat-label\">오늘 진행</div><div class=\"stat-value\">${res?.currentIndex||0}<span style=\"font-size:15px;color:var(--dim)\"> / ${actual}</span></div><div class=\"progress\"><i style=\"width:${progress}%\"></i></div></div><div class=\"card\"><div class=\"stat-label\">현재 복습 필요</div><div class=\"stat-value ${activeN?'red':''}\">${activeN}</div><div class=\"stat-note\">오늘 배정 최대 20개 · 안정화되면 자동 졸업</div></div><div class=\"card\"><div class=\"stat-label\">기기 동기화</div><div class=\"stat-value\" style=\"font-size:22px\">${cloudSignedIn()?'ON':'LOCAL'}</div><div class=\"stat-note\">${cloudSignedIn()?'동일 진도 사용':'연결 시 자동 병합'}</div></div></div>`;
}
""")

section('function startQuiz(){', 'function makeQuestion(index){', """
function startQuiz(){const set=getDailySet();if(!set.ids.length){renderToday();return}ensureResult();renderQuiz()}
""")

# review tag in the normal quiz without a separate review screen
once("const index=res.currentIndex,q=makeQuestion(index),g=groupForIndex(set,index);quizLocked=false;root.innerHTML=", "const index=res.currentIndex,q=makeQuestion(index),g=groupForIndex(set,index),scheduled=isScheduledReview(set,q.w.id);quizLocked=false;root.innerHTML=")
once("<span class=\"tag\">${g.no} · ${escapeHtml(g.label)}</span>", "<span class=\"tag\">${scheduled?'복습':'오늘 단어'}</span>")

# ---- answer flow: 3s correction -> 4s memory card -> next question ----
section('function answerQuestion(optionIndex){', 'function startReview(type){', """
function advanceAfterAnswer(){const res=ensureResult(),set=getDailySet();if(res.currentIndex>=set.ids.length)finishQuiz();else renderQuiz()}
function showWrongMemory(w){
  const root=document.getElementById('viewToday');root.innerHTML=`<div class=\"wrong-memory\"><div class=\"memory-label\">한 번만 기억하기</div><div class=\"memory-word\">${escapeHtml(w.word)}</div><div class=\"memory-mean\">${escapeHtml(w.mean)}</div><div class=\"memory-hint\">잠시 보고 있으면 자동으로 다음 문제로 넘어갑니다.</div></div>`;
  feedbackTimer=setTimeout(advanceAfterAnswer,4000);window.scrollTo({top:0,behavior:'smooth'});
}
function answerQuestion(optionIndex){
  if(quizLocked)return;quizLocked=true;const res=ensureResult(),set=getDailySet(),index=res.currentIndex,q=makeQuestion(index),buttons=[...document.querySelectorAll('.option')],selected=q.options[optionIndex],ok=selected===q.correct,date=localDate(),scheduled=isScheduledReview(set,q.w.id);
  buttons.forEach((b,i)=>{b.disabled=true;if(q.options[i]===q.correct)b.classList.add('correct');if(i===optionIndex&&!ok)b.classList.add('wrong')});
  recordAttempt(q.w.id,ok,date,scheduled);if(ok)res.correct++;else if(!res.wrongIds.includes(q.w.id))res.wrongIds.push(q.w.id);res.answers[index]={id:q.w.id,direction:q.direction,ok,selected,scheduledReview:scheduled,answeredAt:new Date().toISOString()};res.currentIndex=index+1;save();updateChrome();
  const fb=document.getElementById('feedback');fb.className='feedback '+(ok?'ok':'bad');fb.textContent=ok?'정답':`오답 · 정답: ${q.correct}`;
  if(ok)feedbackTimer=setTimeout(advanceAfterAnswer,420);else feedbackTimer=setTimeout(()=>showWrongMemory(q.w),3000);
}
function finishQuiz(){const res=ensureResult();res.quizFinished=true;save();completeSession();showResult()}
""")

# ---- current review page instead of ever-growing wrong DB ----
section('function renderWrong(){', 'function historyRowHtml(h){', """
function renderWrong(){
  const root=document.getElementById('viewWrong'),ids=reviewIdsFor(S,true).sort((a,b)=>String(S.reviewDb[a]?.dueDate||'').localeCompare(String(S.reviewDb[b]?.dueDate||''))||(S.wrongDb[b]?.count||0)-(S.wrongDb[a]?.count||0)),active=ids.length,stable=stableReviewCountFor(),historical=wrongCount();
  root.innerHTML=`<div class=\"grid g3\" style=\"margin-bottom:15px\"><div class=\"card\"><div class=\"stat-label\">현재 복습 필요</div><div class=\"stat-value red\">${active}</div><div class=\"stat-note\">오늘은 최대 20개만 자동 출제</div></div><div class=\"card\"><div class=\"stat-label\">안정화 완료</div><div class=\"stat-value\">${stable}</div><div class=\"stat-note\">D+1 · D+3 · D+6 확인 통과</div></div><div class=\"card\"><div class=\"stat-label\">과거 오답 이력</div><div class=\"stat-value\">${historical}</div><div class=\"stat-note\">현재 실력과 분리해 보관</div></div></div><div class=\"card\"><div class=\"section-head\"><div><div class=\"section-title\">복습이 필요한 단어</div><div class=\"section-sub\">별도 암기 단계 없이 오늘 학습 80개 안에서 자동으로 다시 출제됩니다.</div></div><input class=\"search\" id=\"wrongSearch\" placeholder=\"단어 또는 뜻 검색\" oninput=\"filterWrong()\"></div><div id=\"wrongList\"></div></div>`;wrongPage=1;drawWrongList(ids,'')
}
function filterWrong(){wrongPage=1;const q=document.getElementById('wrongSearch').value.trim().toLowerCase(),ids=reviewIdsFor(S,true).filter(id=>{const w=BY_ID[id];return w.word.toLowerCase().includes(q)||w.mean.toLowerCase().includes(q)}).sort((a,b)=>String(S.reviewDb[a]?.dueDate||'').localeCompare(String(S.reviewDb[b]?.dueDate||''))||(S.wrongDb[b]?.count||0)-(S.wrongDb[a]?.count||0));drawWrongList(ids,q)}
function drawWrongList(ids,q){const per=50,pages=Math.max(1,Math.ceil(ids.length/per));wrongPage=clamp(wrongPage,1,pages);const slice=ids.slice((wrongPage-1)*per,wrongPage*per),box=document.getElementById('wrongList');if(!box)return;if(!slice.length){box.innerHTML=`<div class=\"empty\"><div class=\"empty-icon\">○</div>${q?'검색 결과가 없습니다.':'현재 복습이 필요한 단어가 없습니다.'}</div>`;return}box.innerHTML=`<div class=\"list\">${slice.map(id=>{const w=BY_ID[id],r=S.wrongDb[id]||{},v=S.reviewDb[id]||{},step=(v.stage||0)===0?'D+1':v.stage===1?'D+3':'D+6';return`<div class=\"word-row\"><div class=\"w\">${escapeHtml(w.word)}</div><div class=\"m\">${escapeHtml(w.mean)}</div><div class=\"c\">${step}</div><div class=\"d\">예정 ${escapeHtml(v.dueDate||'-')} · 오답 ${r.count||0}회</div></div>`}).join('')}</div><div class=\"pager\"><button class=\"btn btn-secondary small\" onclick=\"changeWrongPage(-1)\" ${wrongPage===1?'disabled':''}>이전</button><span>${wrongPage} / ${pages}</span><button class=\"btn btn-secondary small\" onclick=\"changeWrongPage(1)\" ${wrongPage===pages?'disabled':''}>다음</button></div>`;box.dataset.ids=ids.join(',')}
function changeWrongPage(delta){const box=document.getElementById('wrongList'),ids=(box.dataset.ids||'').split(',').filter(Boolean).map(Number);wrongPage+=delta;drawWrongList(ids,'')}
""")

# nav wording / badge = active review count
s = s.replace("['wrong','×','오답 DB']", "['wrong','↻','복습 단어']")
s = s.replace("${wrongCount()}</span>`:''}", "${activeReviewCount()}</span>`:''}")
s = s.replace("if(badge){badge.textContent=wrongCount();badge.style.display=wrongCount()?'':'none'}", "if(badge){badge.textContent=activeReviewCount();badge.style.display=activeReviewCount()?'':'none'}")
s = s.replace("wrong:['오답 DB','틀린 단어는 삭제하지 않고 누적']", "wrong:['복습 단어','틀린 단어는 D+1 · D+3 · D+6으로 자동 복습']")

# result card: current review count instead of cumulative wrong count
s = s.replace("<div class=\"result-cell\"><b>${wrongCount()}</b><span>누적 오답 DB</span></div>", "<div class=\"result-cell\"><b>${activeReviewCount()}</b><span>현재 복습 필요</span></div>")
s = s.replace("세션 모드: ${set.mode==='wrong-only'?'오답 집중':'전체 DB 순환'} · 목표 ${target}개", "복습 ${set.reviewIds?.length||0}개 포함 · 목표 ${target}개")

# touch-device fallback for dblclick zoom; mouse/desktop behavior is unaffected.
js = """
if(navigator.maxTouchPoints>0){document.addEventListener('dblclick',e=>{if(e.target.closest('button,.option,.prompt-card,.btn,.nav-btn,.hero,.card'))e.preventDefault()},{passive:false})}
"""
if "navigator.maxTouchPoints>0){document.addEventListener('dblclick'" not in s:
    s = s.replace('</script>\n</body>', js + '\n</script>\n</body>', 1)

P.write_text(s, encoding='utf-8')
print('WordMaster v8 patch applied:', P.stat().st_size, 'bytes')
