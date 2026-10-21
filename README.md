# 课件转互动自学网站 · Courseware Self Study

把 PPT/PDF 课件做成可以**选择知识点、逐步拆解、操作实验、回答自测、回看原页**的自学网站。

这是一个给 **Codex** 使用的 Skill，附带可复用网页模板和课件处理工具。适用于一章 demo、整学期课程和已有自学网站的持续改进。

[立即下载技能包](https://github.com/wenchuan-max/courseware-self-study/releases/latest/download/courseware-self-study.zip) · [查看技能完整指令](skills/courseware-self-study/SKILL.md) · [查看发行版本](https://github.com/wenchuan-max/courseware-self-study/releases)

## 安装：推荐把网址交给 Codex

复制下面这段话，发给 Codex：

~~~text
使用 $skill-installer，安装这个 GitHub 仓库里的技能：
https://github.com/wenchuan-max/courseware-self-study/tree/main/skills/courseware-self-study
~~~

安装完成后，在下一次对话中使用 $courseware-self-study。若没有识别到，重新打开 Codex。安装器发现同名技能已存在时会停止；更新前先备份原目录，不要把新旧两个同名副本同时放入扫描目录。

完整仓库网址适合浏览和分享；上面的 **/tree/main/skills/courseware-self-study** 链接精确定位到可安装的 Skill 文件夹。

## 安装：下载 ZIP 手动放置

1. 点击 [下载最新版 Skill ZIP](https://github.com/wenchuan-max/courseware-self-study/releases/latest/download/courseware-self-study.zip)。
2. 完整解压，得到 courseware-self-study 文件夹，确认其中直接包含 SKILL.md、agents、scripts、references 和 assets。
3. 放到当前 Codex 的技能目录。当前官方文档的用户目录为：
   - Windows：%USERPROFILE%\.agents\skills\courseware-self-study
   - macOS / Linux：~/.agents/skills/courseware-self-study
4. 某些现有桌面环境或安装器仍使用 ~/.codex/skills；以你的实际环境为准，优先使用上面的自动安装方式。选一个目录即可，不要重复安装。
5. 开始下一次对话；没有识别到时重新打开 Codex。

也可以把技能放到某个项目的 .agents/skills/courseware-self-study，供该项目使用。

GitHub 的 **Code → Download ZIP** 下载的是完整仓库：其中应复制 **skills/courseware-self-study** 这一层，不是整个仓库文件夹。

安装与发现机制参考 [OpenAI 官方 Skills 文档](https://learn.chatgpt.com/docs/build-skills)。

## 直接开始用

### 先做一个 demo

~~~text
使用 $courseware-self-study。

课件在 D:\课程资料\生物化学\课件，包含 PPTX 和 PDF。
项目全部放在 D:\课程资料\生物化学\自学网站。
先选择一段适合展示完整学习闭环的内容，做成高互动、强引导的 demo。
要求逐知识点拆解、相关实验、足够的可视化和自测，文字简短，能回看原页。
~~~

### 扩展整学期

~~~text
使用 $courseware-self-study，把已经确认的 demo 扩展到全部课件。

按来源建立覆盖清单，每个主题列出全部关键知识点供选择。
为不同知识点配置真正相关的实验，不复用不相干模型。
补齐自测，最后做内容审查、独立数值复算、桌面和手机浏览器验收，
交付可完整解压后直接打开的 ZIP，并告诉我打开哪个文件。
~~~

### 修订已有网站

~~~text
使用 $courseware-self-study，检查这个已有的课件自学网站。

修复主题切换后实验没有更新的问题；把每个主题拆成可选的关键知识点；
补充有出处的考研真题练习，区分原题、改编和同知识点拓展。
保留现有学习进度与原课件，最后核查所有呈现位置的一致性。
~~~

将路径替换成自己的实际位置。D 盘是示例，不是技能的运行限制；文件工具可以在有权限的 Windows、macOS 或 Linux 目录中制作网站。

## 它会做什么

| 学习环节 | 结果 |
|---|---|
| 盘点课件 | 清单、来源 ID、内容哈希、真实页码和未解决项 |
| 建立证据 | PDF 全页图、文本、PPTX 正文及备注、原页引用 |
| 编排内容 | 课程 → 主题 → 可选择的知识点，概览串起知识关系 |
| 逐点引导 | 具体问题、逐步推理、结论、原页依据 |
| 对应实验 | 明确 ID 绑定，预测、改条件、看过程和比较解释 |
| 自测与真题 | 选择题、开放题自评、错题回看、真实出处 |
| 内容审查 | 对照课件，核查条件、机制、公式、数值和图示 |
| 网页验收 | 跨主题状态、进度、刷新恢复、桌面和窄屏 |
| 离线分享 | 本地图片和脚本、资源校验、ZIP 完整性检查 |

~~~mermaid
flowchart LR
  A[课件] --> B[原页图与文本]
  B --> C[主题与知识点]
  C --> D[逐步引导与实验]
  D --> E[自测与回看]
  E --> F[内容审查和网页验收]
  F --> G[离线分享包]
~~~

## 输入与输出范围

### 输入

- **PDF**：工具可提取文本并逐页渲染为 WebP。
- **PPTX**：工具可按演示顺序提取正文和备注；整页图片需先由演示文稿软件导出 PDF。相同目录、相同名称的 PDF 可作为配套视觉来源。
- **旧版 PPT**：需先导出 PDF，或用可靠转换工具处理。
- **扫描件、复杂公式、动画**：无文本层时需要 OCR 或人工辨读；动画和阶段信息要通过备注、导出帧或原文件进一步核查。工具不会假装完成未读取的内容。

### 输出

静态 HTML/CSS/JavaScript 网站、知识点数据、原页图片、课件副本、校验记录和离线 ZIP。原课件保持只读；原页错误采用讲解层注释更正。

接收学习网站的人，完整解压后双击 **打开网页.cmd（Windows）** 或 **index.html**。网页运行不需要 Python、Node、构建服务器或外部 CDN。Skill 安装包与生成的学习网站 ZIP 是两个不同产物。

**处理脚本不直接把 PDF 自动“变成教学内容”。** Codex 仍需对照课件编写知识点、题目和机制，构建有意义的可视化，再做审查。

## 工具使用（可选）

普通使用只需把需求告诉 Codex。需要手动操作工具时：

### 环境

- Python 3.10+
- PDF 提取和渲染：pypdfium2、Pillow
- 制作课程需要能使用本地文件的 Codex 环境
- 真题检索或资料核验需要相应网络能力
- 网页运行无需 Python；PPTX XML 文本提取只用标准库

在克隆后的仓库根目录运行：

~~~text
python -m pip install -r requirements.txt
python skills/courseware-self-study/scripts/courseware.py init --output ./my-course --title "我的课程"
python skills/courseware-self-study/scripts/courseware.py prepare --input ./courseware --project ./my-course
~~~

随后由 Codex 对照来源编写 my-course/content/course.json，并为关键机制扩展 my-course/models.js：

~~~text
python skills/courseware-self-study/scripts/courseware.py build --project ./my-course
python skills/courseware-self-study/scripts/courseware.py validate --project ./my-course
python skills/courseware-self-study/scripts/courseware.py serve --project ./my-course --port 0
python skills/courseware-self-study/scripts/courseware.py pack --project ./my-course --zip ./my-course.zip
~~~

serve 仅绑定本机 127.0.0.1，并打印实际端口。检查后关闭自己的测试服务。init 拒绝覆盖非空目录；pack 拒绝覆盖已有 ZIP。修改内容或运行文件后重新 build。

### 命令速查

| 命令 | 作用 |
|---|---|
| init | 创建离线模板、作者数据与打开入口 |
| prepare | 来源清单、PDF 逐页提取/渲染、PPTX 正文/备注、缓存 |
| build | 将作者数据与来源打包为本地脚本，更新资源版本 |
| validate | 检查 ID、引用、图片、知识点、实验、答案和覆盖 |
| serve | 启动临时本机预览 |
| pack | 检查结构、相对依赖，生成并验证离线 ZIP |

只有明确登记的自定义模型才会加载；缺失时显示配置缺失。不会根据标题随意套用模型。模板提供一个独立概率面积模型作为接口示例，其他课程的机制需要按内容制作。

## 维护者文档

- [技能入口与工作流](skills/courseware-self-study/SKILL.md)
- [数据结构、字段示例及模型接口](skills/courseware-self-study/references/content-schema.md)
- [真题来源与内容审查](skills/courseware-self-study/references/review-and-exams.md)
- [浏览器验收与离线交付](skills/courseware-self-study/references/qa-and-delivery.md)
- [本次遗传学项目的复盘](skills/courseware-self-study/references/lessons-from-genetics.md)

目录：

~~~text
courseware-self-study/
├── README.md
├── LICENSE
├── requirements.txt
├── tests/                           轻量回归检查
└── skills/courseware-self-study/
    ├── SKILL.md                     Codex 工作指令
    ├── agents/openai.yaml           技能元数据
    ├── scripts/courseware.py        处理、构建、校验和打包
    ├── references/                  内容、审查、交付与项目经验
    └── assets/starter/              可复用网页模板
~~~

## 验证与边界

结构检查不证明科学内容正确，浏览器截图也不证明原页内容全部覆盖。技能要求把来源覆盖、语义审查、独立复算和真实浏览器验收分开记录。

初始版本使用隔离的概率课件验证过初始化、防覆盖、PDF 页面渲染、PPTX 顺序/备注、缓存、模型绑定、漏页拦截、答案索引、真题出处字段、过期构建和 ZIP 完整性；也在真实浏览器检查过知识点切换、参数计算、错题、进度、原页图与手机布局。浏览器工具若不支持 file://，应如实记录直接文件入口尚未实测，不能把本地服务检查冒充为文件入口检查。

运行仓库回归检查：

~~~text
python -m unittest discover -s tests -v
~~~

这些检查是发布时验证过的行为，不代表所有课程都已获得相同质量。新课程仍须对照自己的原始课件完成审查。

## 常见问题

**安装后为什么没有直接出现我的课程？**

安装的是工作方法、模板和工具。还要告诉 Codex 课件位置、输出目录及课程目标，才会生成你自己的学习网站。

**是否包含遗传学原课件或整套网站？**

不包含。这里只发布通用技能和项目经验；课程 PDF、原网页、试卷全文及个人学习记录不在仓库中。

**自测题都是真题吗？**

只有核验过原卷出处的题目才能标记为真题原文或真题改编。同知识点拓展和出处待核验材料分别标记，不混计。

**full 校验通过，就代表内容全部讲完了吗？**

不代表。它检查原页归属与结构完整性；仍需逐项核查原页中的概念、例题、条件、图示是否已被讲解。

**能换视觉风格和交互方式吗？**

可以。模板是起点，知识点与来源接口保持稳定即可。历史、方法、计算和机制类知识点可以使用不同交互。

**分享者需要保留什么？**

完整保留生成网站的相对目录，包括脚本、数据、原页图与被引用的来源副本。不要仅发送 index.html。

## English quick start

A Codex skill for turning PPT/PDF courseware into guided, interactive, offline self-study websites. It includes point-level navigation, explicit experiment binding, quizzes, source-slide references, review guidance, a static starter, and Python helpers.

Ask Codex:

~~~text
Use $skill-installer to install:
https://github.com/wenchuan-max/courseware-self-study/tree/main/skills/courseware-self-study
~~~

Then ask $courseware-self-study to build a demo from your local courseware. PDF rendering requires pypdfium2 and Pillow. PPTX text and notes are supported; export slides to PDF for full-page visuals. Generated websites require no Python or Node at runtime.

## 许可证

[MIT License](LICENSE)。可使用、修改和再分发本仓库的技能、脚本和模板，保留许可声明。用户输入的课件、第三方试卷和由其衍生的材料不因使用本技能而改变原有权利。
