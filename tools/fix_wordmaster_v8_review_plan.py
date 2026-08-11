from pathlib import Path
p=Path('index.html')
s=p.read_text(encoding='utf-8')
old="for(const [date,set] of Object.entries(s.dailySets)){if(!set)continue;set.date=set.date||date;set.sessionId=set.sessionId||('set:'+date+':'+(set.createdAt||'legacy'));if(!Array.isArray(set.reviewIds))set.reviewIds=[]}"
new="for(const [date,set] of Object.entries(s.dailySets)){if(!set)continue;set.date=set.date||date;set.sessionId=set.sessionId||('set:'+date+':'+(set.createdAt||'legacy'));if(!Array.isArray(set.reviewIds))set.reviewIds=[];if(set.reviewPlanVersion===undefined)set.reviewPlanVersion=0}"
if old not in s: raise SystemExit('normalize dailySets marker missing')
s=s.replace(old,new,1)
old="const needsV8=date===localDate()&&unstarted&&!Array.isArray(set.reviewIds);"
new="const needsV8=date===localDate()&&unstarted&&set.reviewPlanVersion!==8;"
if old not in s: raise SystemExit('needsV8 marker missing')
s=s.replace(old,new,1)
s=s.replace("mode:'off',target:0,ids:[],reviewIds:[],groups:[]", "mode:'off',target:0,ids:[],reviewIds:[],reviewPlanVersion:8,groups:[]",1)
old="S.dailySets[date]={date,sessionId,mode:'mixed',target:ids.length,requestedTarget:target,ids,reviewIds,groups:[{label:'오늘 학습',ids:ids.slice()}]"
new="S.dailySets[date]={date,sessionId,mode:'mixed',target:ids.length,requestedTarget:target,ids,reviewIds,reviewPlanVersion:8,groups:[{label:'오늘 학습',ids:ids.slice()}]"
if old not in s: raise SystemExit('new daily set marker missing')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')
print('v8 review-plan refresh fix applied')
