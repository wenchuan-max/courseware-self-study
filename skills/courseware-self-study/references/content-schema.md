# 内容结构与模板接口

适用于新项目的快速起步。现有网站保留兼容结构，只迁移确有必要的字段。

## 来源与覆盖

prepare 写入 reference/source-manifest.json 和 reference/slides.json。source ID 由相对文件路径生成，内容 SHA 单独记录。使用 PDF 物理页码，第一页为 1；印刷页码可另记。全文索引包括原页文本。

scope.sourceIds 是本次交付所选的来源；空数组由工具解释为全部已导入来源。demo 可只讲部分页；full 要让所选来源每页都有 topic.refs 或 excludedPages 的具体归属。排除页只适用于封面、目录、重复页等明确理由，不能用来隐藏未讲解的知识。

## 作者数据示例

content/course.json 是作者入口，build 生成 course-data.js。下面仅示范接口，实际内容必须来自用户课件：

~~~json
{
  "schemaVersion": 1,
  "id": "probability-intro",
  "title": "概率入门",
  "intro": "从一个判断到可解释的计算",
  "scope": {"mode": "demo", "sourceIds": [], "excludedPages": []},
  "chapters": [{
    "id": "chapter-events", "title": "事件",
    "topics": [{
      "id": "topic-independent", "title": "独立事件",
      "summary": "先判断条件，再决定能否相乘。",
      "refs": [{"sourceId": "替换为清单中的ID", "pages": [1]}],
      "overview": ["独立性决定联合概率能否由边缘概率直接相乘。"],
      "points": [{
        "id": "point-product", "title": "独立事件的联合概率",
        "question": "两个独立事件同时发生的概率是多少？",
        "steps": ["确认 P(B|A)=P(B)。", "使用 P(A且B)=P(A)P(B)。"],
        "takeaway": "先核验独立条件，再相乘。",
        "refs": [{"sourceId": "替换为清单中的ID", "pages": [1]}],
        "lab": {
          "kind": "compare", "title": "改变一个事件的概率",
          "instruction": "预测联合概率如何变化，再展开解释。",
          "cases": [
            {"label": "基准", "change": "独立；P(A)=1/2，P(B)=1/2",
             "chain": ["独立条件成立", "相乘：1/2 × 1/2"], "result": "1/4",
             "why": "这里可以使用乘法公式的独立情形。"},
            {"label": "改变 B", "change": "独立；P(A)=1/2，P(B)=1/4",
             "chain": ["独立条件仍成立", "相乘：1/2 × 1/4"], "result": "1/8",
             "why": "B 的概率减半使联合概率减半。"}
          ]
        }
      }]
    }]
  }],
  "questions": [{
    "id": "q-independent-01",
    "topicIds": ["topic-independent"], "pointIds": ["point-product"],
    "kind": "single", "question": "P(A)=1/2、P(B)=1/4，且相互独立，P(A且B)为多少？",
    "choices": ["1/8", "3/4", "1/2"], "answer": 0,
    "explanation": ["独立时联合概率为边缘概率之积：1/2 × 1/4=1/8。"],
    "source": {"kind": "coursework"}
  }],
  "review": {"status": "pending", "notes": []},
  "corrections": []
}
~~~

ID 稳定、全局唯一，不用数组下标表示持久身份。知识点可跨页、跨来源；不要为满足校验强行截断真实引用。overview 展示关系，steps 展示推理，takeaway 收束结论，避免原句重复占满屏幕。

corrections 项使用 sourceId、page、text；只改变说明层，原图片和课件不改动。review.status 的 reviewed 只是审查记录，工具不会因此证明内容正确。

## 专门实验

对于连续参数、过程动画或可操作图，使用：

~~~json
{"kind": "custom", "modelId": "independent-product", "title": "独立概率实验", "parameters": {"a": 0.5, "b": 0.25}}
~~~

在 models.js 注册 STUDY_MODELS["independent-product"] = function(host, parameters, changed) { ...; return cleanup; }。

模型只能修改传入的 host；用 textContent 填充来源文本。changed 可记录当前实验参数；跨知识点切换时 app 会调用 cleanup，清除模型创建的监听器、定时器等。缺失 modelId 显示配置缺失，不能回退到其他主题的模型。

普通 compare 原生支持多条件对照和“先想后展开”。关键任务应扩展专门模型；模板不限制模型种类或视觉风格。

## 题目

kind 支持 single 和 written。single 的 answer 是从 0 开始的选项下标；written 的 answer 是参考答案或评分点字符串。explanation 是推理数组。可附 pitfall。topicIds 和 pointIds 用于筛选与回看。

source.kind：
- coursework：依据课件编写的自测。
- past-exam-original：核验过的真题原文。
- past-exam-adapted：核验过的真题改编。
- past-exam-extension：同知识点拓展，不称作真题。
- unverified：出处尚待核验，不计入已核验真题。

前三种含 past-exam 的类型保留 institution、year、exam、item、url；可加 page、accessed。真题原文须遵守使用范围；优先用有出处的简短改编，并清楚标记。
