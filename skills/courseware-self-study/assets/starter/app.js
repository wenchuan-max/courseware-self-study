(function(){
"use strict";
var data=window.COURSE_DATA || {chapters:[],questions:[],sources:[],slides:{}};
var flat=[], cleanup=null, current=null, view="learn", sourcePage=1, sourceId=null;
(data.chapters||[]).forEach(function(ch){(ch.topics||[]).forEach(function(t){flat.push({chapter:ch,topic:t});});});
var qa=new URLSearchParams(location.search).has("qa");
var storeKey="self-study:v1:"+data.id+(qa?":qa":":learn");
var saved={read:{},answers:{},drafts:{},models:{}}, query="", wrongOnly=false;
try{Object.assign(saved,JSON.parse(localStorage.getItem(storeKey)||"{}"));}catch(e){}
function persist(){try{localStorage.setItem(storeKey,JSON.stringify(saved));}catch(e){}}
function node(tag,cls,text){var el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=text;return el;}
function button(text,fn,cls){var el=node("button",cls,text);el.type="button";el.onclick=fn;return el;}
function list(items,cls){var el=node("ol",cls);(items||[]).forEach(function(t){el.append(node("li","",t));});return el;}
function card(title){var el=node("section","card");if(title)el.append(node("h2","",title));return el;}
function jump(topic,point,mode){location.hash=new URLSearchParams({topic:topic,point:point||"",view:mode||"learn"}).toString();document.body.classList.remove("nav-open");document.getElementById("menu").setAttribute("aria-expanded","false");}
function progress(){
 var valid=new Set();flat.forEach(function(r){(r.topic.points||[]).forEach(function(p){valid.add(p.id);});});
 var count=Object.keys(saved.read).filter(function(k){return saved.read[k]&&valid.has(k);}).length;
 var total=flat.reduce(function(n,r){return n+(r.topic.points||[]).length;},0);
 document.getElementById("progress").textContent=count+" / "+total+" 已读";
}
function showSource(sid,page){
 var s=(data.sources||[]).find(function(s){return s.id===sid;});
 var slide=(data.slides[sid]||[]).find(function(x){return x.page===page;});
 if(!s||!slide)return;
 sourceId=sid;sourcePage=page;
 document.getElementById("viewer-title").textContent=s.title+" · 第 "+page+" 页";
 var img=document.getElementById("viewer-image");img.src=slide.image;img.alt=s.title+" 第 "+page+" 页";
 document.getElementById("source-file").href=s.file;
 document.getElementById("prev-page").disabled=page<=1;
 document.getElementById("next-page").disabled=page>=s.pageCount;
 document.getElementById("correction").textContent=(data.corrections||[]).filter(function(x){return x.sourceId===sid&&x.page===page;}).map(function(x){return "更正："+x.text;}).join("；");
 var dlg=document.getElementById("viewer");if(!dlg.open)dlg.showModal();
}
function sourceGrid(refs){
 var grid=node("div","image-grid"), seen={};
 (refs||[]).forEach(function(ref){(ref.pages||[]).forEach(function(n){
  var key=ref.sourceId+":"+n;if(seen[key])return;seen[key]=true;
  var s=(data.sources||[]).find(function(s){return s.id===ref.sourceId;});
  var page=(data.slides[ref.sourceId]||[]).find(function(p){return p.page===n;});
  if(!s||!page)return;
  var b=button("",function(){showSource(ref.sourceId,n);},"page-thumb");
  var img=node("img");img.src=page.image;img.alt=s.title+" 第 "+n+" 页";img.loading="lazy";
  b.append(img,node("span","",s.title+" · 第 "+n+" 页"));grid.append(b);
 });});return grid;
}
function nav(){
 var sidebar=document.getElementById("sidebar");sidebar.replaceChildren();
 var search=node("input","search");search.type="search";search.placeholder="搜索知识点 / 原页";search.setAttribute("aria-label","搜索知识点和原页文本");search.value=query;
 var results=node("div","search-results");sidebar.append(search,results);
 function searchNow(){
  results.replaceChildren();var q=query.trim().toLocaleLowerCase();if(!q)return;
  var found=[];
  flat.forEach(function(r){(r.topic.points||[]).forEach(function(p){
   var texts=[r.topic.title,p.title,p.question,(p.steps||[]).join(" "),p.takeaway];
   (p.refs||[]).forEach(function(ref){(ref.pages||[]).forEach(function(n){
    var pg=(data.slides[ref.sourceId]||[]).find(function(x){return x.page===n;});if(pg)texts.push(pg.text);
   });});
   if(texts.join(" ").toLocaleLowerCase().includes(q))found.push({r:r,p:p});
  });});
  results.append(node("p","muted",found.length+" 个知识点"));
  found.slice(0,40).forEach(function(x){results.append(button(x.p.title,function(){jump(x.r.topic.id,x.p.id);}));});
 }
 search.oninput=function(){query=search.value;searchNow();};searchNow();
 (data.chapters||[]).forEach(function(ch){
  var section=node("details");section.open=!!current&&current.chapter.id===ch.id;
  section.append(node("summary","",ch.title));
  (ch.topics||[]).forEach(function(t){
   var b=button(t.title,function(){jump(t.id);},current&&current.topic.id===t.id?"active":"");
   if(current&&current.topic.id===t.id)b.setAttribute("aria-current","page");
   section.append(b);
  });sidebar.append(section);
 });
}
function labFor(point){
 var lab=point.lab||{}, box=card(lab.title||"动手试一试");box.classList.add("lab");
 if(lab.instruction)box.append(node("p","",lab.instruction));
 if(lab.kind==="compare"){
  var tabs=node("div","case-tabs"), body=node("div","case-body"), active=0;
  function choose(i){
   active=i;Array.from(tabs.children).forEach(function(b,n){b.setAttribute("aria-pressed",String(n===i));});
   body.replaceChildren();var c=lab.cases[i];body.append(node("h3","",c.change));
   body.append(node("p","muted","先预测结果，再展开推理。"));
   body.append(button("展开推理",function(){
    body.replaceChildren(node("h3","",c.change),list(c.chain,""),node("p","result",c.result),node("p","",c.why));
   }));
  }
  (lab.cases||[]).forEach(function(c,i){tabs.append(button(c.label,function(){choose(i);}));});
  box.append(tabs,body);if(lab.cases&&lab.cases.length)choose(active);
 } else if(lab.kind==="custom"){
  var host=node("div");box.append(host);
  var model=(window.STUDY_MODELS||{})[lab.modelId];
  if(model){
   try{cleanup=model(host,Object.assign({},lab.parameters,saved.models[point.id]),function(p){saved.models[point.id]=p;persist();});}
   catch(e){host.replaceChildren(node("p","empty","实验加载失败："+e.message));}
  }else host.append(node("p","empty","实验配置缺失："+String(lab.modelId)));
 }else box.append(node("p","empty","此知识点尚未配置实验。"));
 return box;
}
function learn(main,topic,point){
 var overview=card("先建立联系");
 (topic.overview||[]).forEach(function(t){overview.append(node("p","",t));});
 if((topic.overview||[]).length)main.append(overview);
 main.append(node("h2","","选择要拆解的知识点"));
 var picker=node("div","point-picker");
 (topic.points||[]).forEach(function(p){
  var b=button((saved.read[p.id]?"✓ ":"")+p.title,function(){jump(topic.id,p.id);});b.dataset.point=p.id;
  b.setAttribute("aria-pressed",String(p.id===point.id));picker.append(b);
 });main.append(picker);
 if(!point){main.append(node("p","empty","这个主题还没有知识点。"));return;}
 var box=card("");box.append(node("div","eyebrow",point.title),node("div","question",point.question));
 var detail=node("details");detail.append(node("summary","","把这个问题，逐步拆开"),list(point.steps,"steps"));
 box.append(detail,node("p","takeaway",point.takeaway));
 var read=button(saved.read[point.id]?"已读 ✓":"标记已读",function(){
  saved.read[point.id]=!saved.read[point.id];persist();progress();
  read.textContent=saved.read[point.id]?"已读 ✓":"标记已读";read.className=saved.read[point.id]?"":"primary";
  Array.from(document.querySelectorAll(".point-picker button")).forEach(function(b){
   if(b.dataset.point===point.id)b.textContent=(saved.read[point.id]?"✓ ":"")+point.title;
  });
 },saved.read[point.id]?"":"primary");box.append(read);main.append(box,labFor(point));
 var refs=card("回到课件原页");refs.append(sourceGrid(point.refs));main.append(refs);
}
var originLabels={"coursework":"课件自测","past-exam-original":"真题原文","past-exam-adapted":"真题改编","past-exam-extension":"同知识点拓展","unverified":"出处待核验"};
function origin(q){
 var s=q.source||{}, el=node("div","origin",originLabels[s.kind]||"未标注来源");
 if(s.institution)el.append(document.createTextNode(" · "+[s.institution,s.year,s.exam,s.item].filter(Boolean).join(" · ")));
 if(s.url){var a=node("a","","查看原卷");a.href=s.url;a.target="_blank";a.rel="noopener";el.append(document.createTextNode(" · "),a);}
 return el;
}
function quiz(main,topic){
 var filters=node("div","filters"), select=node("select");select.setAttribute("aria-label","按主题筛选自测");
 var all=node("option","","全部主题");all.value="*";select.append(all);
 flat.forEach(function(r){var o=node("option","",r.topic.title);o.value=r.topic.id;select.append(o);});
 var activeFilter=quiz.filter||topic.id;select.value=activeFilter;
 var wrong=button(wrongOnly?"显示全部题":"只看错题",function(){wrongOnly=!wrongOnly;render();});
 wrong.setAttribute("aria-pressed",String(wrongOnly));filters.append(select,wrong);main.append(filters);
 select.onchange=function(){quiz.filter=select.value;render();};
 var qs=(data.questions||[]).filter(function(q){return (activeFilter==="*"||(q.topicIds||[]).includes(activeFilter))&&(!wrongOnly||(saved.answers[q.id]&&saved.answers[q.id].correct===false));});
 main.append(node("p","muted",qs.length+" 道题"));
 qs.forEach(function(q){
  var box=card("");box.classList.add("question-card");box.append(origin(q),node("h3","",q.question));
  var answer=saved.answers[q.id];
  function feedback(){
   var value=saved.answers[q.id];if(!value)return;
   var f=node("div","feedback"+(value.correct===false?" wrong":""));
   f.append(node("strong","",q.kind==="written"?"评分点":value.correct?"回答正确":"再想一步"));
   f.append(list(q.explanation,""));
   if(q.kind==="single")f.append(node("p","","答案："+q.choices[q.answer]));
   else{f.append(node("p","",q.answer));f.append(button("我已掌握",function(){saved.answers[q.id]={correct:true};persist();render();}),document.createTextNode(" "),button("加入错题",function(){saved.answers[q.id]={correct:false};persist();render();}));}
   if(q.pitfall)f.append(node("p","",q.pitfall));
   var point=(q.pointIds||[])[0];var target=flat.find(function(r){return (r.topic.points||[]).some(function(p){return p.id===point;});});
   if(target)f.append(button("回看知识点",function(){jump(target.topic.id,point);}));
   box.append(f);
  }
  if(q.kind==="single"){
   var choices=node("div","answers");(q.choices||[]).forEach(function(text,i){
    var b=button(String.fromCharCode(65+i)+". "+text,function(){saved.answers[q.id]={choice:i,correct:i===q.answer};persist();render();});
    b.setAttribute("aria-pressed",String(!!answer&&answer.choice===i));choices.append(b);
   });box.append(choices);
  }else{
   var input=node("textarea");input.placeholder="先写下你的推理";input.setAttribute("aria-label","你的答案");input.value=saved.drafts[q.id]||"";
   input.oninput=function(){saved.drafts[q.id]=input.value;persist();};box.append(input);
   box.append(button("查看评分点",function(){saved.answers[q.id]={correct:null};persist();render();}));
  }
  feedback();main.append(box);
 });
 if(!qs.length)main.append(node("p","empty","当前筛选下没有题目。"));
}
function render(){
 if(typeof cleanup==="function"){cleanup();cleanup=null;}
 var params=new URLSearchParams(location.hash.slice(1));
 current=flat.find(function(x){return x.topic.id===params.get("topic");})||flat[0];
 view=params.get("view")||"learn";
 if(!["learn","quiz","source"].includes(view))view="learn";
 var main=document.getElementById("main");main.replaceChildren();
 document.title=data.title||"互动自学";document.getElementById("brand").textContent=data.title||"自学工作台";
 progress();nav();
 if(!current){main.append(node("h1","",data.title),node("p","empty","课件已准备好后，编写 content/course.json，再运行 build 生成课程。"));return;}
 var topic=current.topic,points=topic.points||[];
 var point=points.find(function(p){return p.id===params.get("point");})||points[0];
 main.append(node("div","eyebrow",current.chapter.title),node("h1","",topic.title));
 if(topic.summary)main.append(node("p","intro",topic.summary));
 var tabs=node("nav","tabs");tabs.setAttribute("aria-label","学习视图");
 [["learn","引导学习"],["quiz","自测与真题"],["source","课件原页"]].forEach(function(pair){
  var b=button(pair[1],function(){jump(topic.id,point&&point.id,pair[0]);});b.setAttribute("aria-pressed",String(view===pair[0]));tabs.append(b);
 });main.append(tabs);
 if(view==="learn")learn(main,topic,point);
 else if(view==="quiz")quiz(main,topic);
 else main.append(sourceGrid(topic.refs));
 main.append(node("footer","","学习记录保存在本机浏览器"));
}
document.getElementById("menu").onclick=function(){
 var open=document.body.classList.toggle("nav-open");this.setAttribute("aria-expanded",String(open));
};
document.getElementById("close-viewer").onclick=function(){document.getElementById("viewer").close();};
document.getElementById("prev-page").onclick=function(){showSource(sourceId,sourcePage-1);};
document.getElementById("next-page").onclick=function(){showSource(sourceId,sourcePage+1);};
window.addEventListener("hashchange",function(){render();window.scrollTo(0,0);});render();
})();
