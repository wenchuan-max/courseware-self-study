window.STUDY_MODELS = window.STUDY_MODELS || {};
// Example only: register course-specific models by explicit ID.
window.STUDY_MODELS["independent-product"] = function(host, parameters, changed) {
  var p = Object.assign({a:0.5,b:0.25},parameters);
  var controls = document.createElement("div");
  controls.className = "model-controls";
  var outputs = {}, inputs = {};
  ["a","b"].forEach(function(key) {
    var label = document.createElement("label");
    var text = document.createElement("span");
    var input = document.createElement("input");
    input.type = "range"; input.min=0; input.max=1; input.step=0.01;
    input.value=p[key]; input.setAttribute("aria-label","P(" + key.toUpperCase() + ")");
    label.append(text,input); controls.append(label); inputs[key]=input; outputs[key]=text;
  });
  var ns="http://www.w3.org/2000/svg";
  var svg=document.createElementNS(ns,"svg");
  svg.setAttribute("viewBox","0 0 100 100"); svg.setAttribute("role","img");
  svg.setAttribute("aria-label","独立事件联合概率的面积示意");
  svg.classList.add("model-diagram");
  var a=document.createElementNS(ns,"rect"), ab=document.createElementNS(ns,"rect");
  a.setAttribute("fill","#ddd5fa"); ab.setAttribute("fill","#6c45db");
  svg.append(a,ab);
  var result=document.createElement("div"); result.className="model-output";
  var note=document.createElement("p");
  note.textContent="仅在相互独立时使用 P(A且B)=P(A)P(B)。深色面积表示联合概率。";
  host.append(controls,svg,result,note);
  function update() {
    ["a","b"].forEach(function(k){p[k]=Number(inputs[k].value); outputs[k].textContent="P("+k.toUpperCase()+") = "+p[k].toFixed(2);});
    a.setAttribute("width",p.a*100); a.setAttribute("height",100);
    ab.setAttribute("width",p.a*100); ab.setAttribute("height",p.b*100);
    result.textContent="P(A且B) = "+Number((p.a*p.b).toPrecision(5));
    changed(Object.assign({},p));
  }
  inputs.a.oninput=inputs.b.oninput=update; update();
  return function(){inputs.a.oninput=inputs.b.oninput=null;};
};
