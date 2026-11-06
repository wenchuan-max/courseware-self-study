#!/usr/bin/env python3
"""Offline courseware starter: init, prepare, build, validate, pack, serve."""
import argparse
import copy
import io
import posixpath
import uuid
from html.parser import HTMLParser
import hashlib
import html
import json
import mimetypes
import re
import shutil
import sys
import zipfile
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ("index.html", "style.css", "app.js", "models.js", "course-data.js")
DATA_FOLDERS = ("pages", "sources", "reference", "content", "assets")

def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def local_path(project, url):
    parsed = urlsplit(url)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    p = (project / unquote(parsed.path)).resolve()
    if not p.is_relative_to(project.resolve()):
        raise ValueError("资源超出项目目录: " + url)
    return p

def init_project(args):
    target = Path(args.output).resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError("目标目录非空；请直接编辑已有项目或选择空目录。")
    target.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "assets/starter", target, dirs_exist_ok=True)
    for name in DATA_FOLDERS:
        (target / name).mkdir(exist_ok=True)
    data = {
        "schemaVersion": 1, "id": "course-" + uuid.uuid4().hex[:12],
        "title": args.title, "intro": "选择一个知识点，从问题开始。",
        "scope": {"mode": "demo", "sourceIds": [], "excludedPages": []},
        "chapters": [], "questions": [], "review": {"status": "pending", "notes": []}, "corrections": []
    }
    write_json(target / "content/course.json", data)
    (target / "打开网页.cmd").write_bytes(b'@echo off\r\nstart "" "%~dp0index.html"\r\n')
    (target / "使用说明.txt").write_text(
        "先完整解压到一个文件夹，再双击“打开网页.cmd”或 index.html。\n"
        "无需安装软件，首次打开即可学习；学习记录保存在当前浏览器本机。\n"
        "换浏览器、清除浏览数据或更换文件位置可能影响记录。\n", encoding="utf-8")
    build_project(argparse.Namespace(project=str(target)))
    print("已初始化: " + str(target))

def pptx_text(path):
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main",
          "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    relns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    def resolve(base, rel):
        parts = []
        for part in (PurePosixPath(base).parent / rel).parts:
            if part == "..":
                if parts: parts.pop()
            elif part != ".": parts.append(part)
        return "/".join(parts)
    with zipfile.ZipFile(path) as z:
        rels = {r.attrib["Id"]: r.attrib["Target"] for r in
                ET.fromstring(z.read("ppt/_rels/presentation.xml.rels")).findall(relns + "Relationship")}
        order = ET.fromstring(z.read("ppt/presentation.xml")).findall("p:sldIdLst/p:sldId", ns)
        slides = []
        for n, item in enumerate(order, 1):
            slide = resolve("ppt/presentation.xml", rels[item.attrib["{" + ns["r"] + "}id"]])
            text = [x.text or "" for x in ET.fromstring(z.read(slide)).findall(".//a:t", ns)]
            notes = []
            rp = str(PurePosixPath(slide).parent / "_rels" / (PurePosixPath(slide).name + ".rels"))
            if rp in z.namelist():
                for rel in ET.fromstring(z.read(rp)).findall(relns + "Relationship"):
                    if rel.attrib.get("Type", "").endswith("/notesSlide"):
                        note = resolve(slide, rel.attrib["Target"])
                        notes += [x.text or "" for x in ET.fromstring(z.read(note)).findall(".//a:t", ns)]
            slides.append({"page": n, "text": "\n".join(text), "notes": "\n".join(notes)})
        return slides

def prepare(args):
    inp, project = Path(args.input).resolve(), Path(args.project).resolve()
    if not inp.is_dir() or not (project / "content/course.json").exists():
        raise ValueError("需要有效的课件目录和已初始化的网站。")
    if inp == project or inp.is_relative_to(project):
        raise ValueError("来源不得放在生成的网站中。")
    files = sorted(p for p in inp.rglob("*") if p.is_file() and p.suffix.lower() in (".pdf", ".pptx", ".ppt")
                   and not p.is_relative_to(project))
    if not files:
        raise ValueError("未找到 PDF / PPTX / PPT。")
    old_manifest = read_json(project / "reference/source-manifest.json", {"sources": []})
    old = {s["id"]: s for s in old_manifest["sources"]}
    old_slides = read_json(project / "reference/slides.json", {})
    sources, pages, notes, warnings = [], {}, {}, []
    pdf_ids = {}
    for p in files:
        if p.suffix.lower() == ".pdf":
            rel = p.relative_to(inp).as_posix()
            pdf_ids[str(PurePosixPath(rel).with_suffix("")).casefold()] = "src-" + hashlib.sha256(rel.encode()).hexdigest()[:10]
    try:
        import pypdfium2 as pdfium
    except ImportError:
        if any(p.suffix.lower() == ".pdf" for p in files):
            raise ValueError("PDF 提取需要 pypdfium2 与 Pillow；请使用环境内可用的依赖运行时。")
    for p in files:
        rel = p.relative_to(inp).as_posix()
        sid = "src-" + hashlib.sha256(rel.encode()).hexdigest()[:10]
        sha = digest(p)
        dest = project / "sources" / sid / p.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or digest(dest) != sha:
            shutil.copy2(p, dest)
        s = {"id": sid, "title": p.stem, "relativeInput": rel, "file": dest.relative_to(project).as_posix(),
             "type": p.suffix.lower()[1:], "sha256": sha, "pageCount": 0, "rendered": False}
        if p.suffix.lower() == ".pdf":
            cached = old.get(sid, {})
            cached_pages = old_slides.get(sid, [])
            if (not args.force and cached.get("sha256") == sha and cached.get("width") == args.width
                and cached_pages and all((project / page["image"]).is_file() for page in cached_pages)):
                pages[sid] = cached_pages
                s.update(pageCount=len(cached_pages), rendered=True, width=args.width)
            else:
                doc = pdfium.PdfDocument(str(p))
                extracted = []
                try:
                    for i in range(len(doc)):
                        page = doc[i]
                        tp = page.get_textpage()
                        text = tp.get_text_range()
                        tp.close()
                        bitmap = page.render(scale=args.width / page.get_width())
                        image = bitmap.to_pil()
                        if image.mode != "RGB": image = image.convert("RGB")
                        out = project / "pages" / sid / ("%04d.webp" % (i + 1))
                        out.parent.mkdir(parents=True, exist_ok=True)
                        image.save(out, "WEBP", quality=84)
                        image.close()
                        bitmap.close()
                        page.close()
                        extracted.append({"page": i + 1, "text": text, "image": out.relative_to(project).as_posix()})
                finally:
                    doc.close()
                pages[sid] = extracted
                s.update(pageCount=len(extracted), rendered=True, width=args.width)
            blanks = sum(not x["text"].strip() for x in pages[sid])
            if blanks: warnings.append(sid + ": %d 页没有文本层，需 OCR / 人工核查" % blanks)
        elif p.suffix.lower() == ".pptx":
            notes[sid] = pptx_text(p)
            s["pageCount"] = len(notes[sid])
            paired = pdf_ids.get(str(PurePosixPath(rel).with_suffix("")).casefold())
            if paired: s["companionOf"] = paired
            else: warnings.append(sid + ": PPTX 已提取文字和备注，尚需导出 PDF 获取整页图")
        else:
            warnings.append(sid + ": 旧版 PPT 需用可靠演示工具转换 PDF")
        sources.append(s)
        print("已处理: " + rel, flush=True)
    write_json(project / "reference/source-manifest.json", {"sources": sources})
    write_json(project / "reference/slides.json", pages)
    write_json(project / "reference/pptx-text.json", notes)
    write_json(project / "reference/prepare-report.json", {
        "sources": len(sources), "renderedPages": sum(map(len, pages.values())), "warnings": warnings})
    for w in warnings: print("待核查: " + w)
    print("完成；请对照 reference/ 编写 content/course.json。")

def build_version(project, raw):
    h = hashlib.sha256(raw.encode("utf-8"))
    for name in ("app.js", "models.js", "style.css"):
        path = project / name
        if path.exists():
            h.update(name.encode("utf-8"))
            h.update(path.read_bytes())
    return h.hexdigest()[:12]

def authored_data(project):
    data = read_json(project / "content/course.json")
    if data is None: raise ValueError("缺少 content/course.json")
    return data

def browser_data(project, mode="share"):
    """Separate private authoring records from the public teaching schema."""
    data = authored_data(project)
    manifest = read_json(project / "reference/source-manifest.json", {"sources": []})["sources"]
    slides = read_json(project / "reference/slides.json", {})
    if mode == "archive":
        return dict(data, sources=manifest, slides=slides, exportMode="archive")
    if mode != "share": raise ValueError("未知导出模式")
    def fields(obj, names):
        return {k: copy.deepcopy(obj[k]) for k in names if k in obj}
    sources = {s["id"]: s for s in manifest}
    allowed = set(data.get("scope", {}).get("sourceIds") or
                  [s["id"] for s in manifest if not s.get("companionOf")])
    excluded = {}
    for ex in data.get("scope", {}).get("excludedPages", []):
        excluded.setdefault(ex["sourceId"], set()).update(ex.get("pages", []))
    selected = {}
    def refs(values):
        result = []
        for ref in values or []:
            sid = ref["sourceId"]
            if sid not in sources or sid not in allowed:
                raise ValueError("引用来源不在交付范围；请调整 scope.sourceIds")
            pages = sorted(set(ref.get("pages", [])))
            if any(type(n) is not int or not 1 <= n <= sources[sid]["pageCount"] for n in pages):
                raise ValueError("引用页码无效")
            if set(pages) & excluded.get(sid, set()):
                raise ValueError("同一页不能同时被引用与排除")
            selected.setdefault(sid, set()).update(pages)
            result.append({"sourceId": sid, "pages": pages})
        return result
    public = fields(data, ("schemaVersion", "id", "title", "intro"))
    public["chapters"] = []
    for chapter in data.get("chapters", []):
        ch = fields(chapter, ("id", "title")); ch["topics"] = []
        for topic in chapter.get("topics", []):
            t = fields(topic, ("id", "title", "summary", "overview"))
            t["refs"] = refs(topic.get("refs")); t["points"] = []
            for point in topic.get("points", []):
                p = fields(point, ("id", "title", "question", "steps", "takeaway"))
                p["refs"] = refs(point.get("refs"))
                lab = point.get("lab", {})
                p["lab"] = fields(lab, ("kind", "title", "instruction", "modelId", "parameters"))
                if lab.get("kind") == "compare":
                    p["lab"]["cases"] = [fields(c, ("label", "change", "chain", "result", "why"))
                                         for c in lab.get("cases", [])]
                t["points"].append(p)
            ch["topics"].append(t)
        public["chapters"].append(ch)
    public["questions"] = []
    for question in data.get("questions", []):
        q = fields(question, ("id", "topicIds", "pointIds", "kind", "question", "choices", "answer", "explanation", "pitfall"))
        q["source"] = fields(question.get("source", {}), ("kind", "institution", "year", "exam", "item", "url", "page", "accessed"))
        public["questions"].append(q)
    public["sources"], public["slides"] = [], {}
    aliases = data.get("share", {}).get("sourceTitles", {})
    for sid, numbers in selected.items():
        if not numbers: continue
        title = aliases.get(sid) or ("课件 " + str(len(public["sources"]) + 1))
        if not isinstance(title, str): raise ValueError("share.sourceTitles 必须使用文字")
        public["sources"].append({"id": sid, "title": title, "pageCount": len(numbers),
                                  "availablePages": sorted(numbers), "file": "handouts/" + sid + ".pdf"})
        found = {x["page"]: x for x in slides.get(sid, [])}
        public["slides"][sid] = []
        for n in sorted(numbers):
            if n not in found: raise ValueError("所选原页尚未渲染")
            image = found[n]["image"]
            checked_file(project, image)
            public["slides"][sid].append({"page": n, "text": found[n].get("text", ""), "image": image})
    public["scope"] = {"mode": data.get("scope", {}).get("mode", "demo"),
                       "sourceIds": [s["id"] for s in public["sources"]]}
    public["corrections"] = [fields(c, ("sourceId", "page", "text")) for c in data.get("corrections", [])
                             if c.get("page") in selected.get(c.get("sourceId"), set())]
    public["exportMode"] = "share"
    return public

def checked_file(project, relative):
    path = PurePosixPath(str(relative).replace("\\", "/"))
    if (path.is_absolute() or ".." in path.parts or not path.parts or
        any(x.startswith(".") for x in path.parts) or re.match(r"^[A-Za-z]:", str(path))):
        raise ValueError("不允许的资源路径")
    target = (project / str(path)).resolve()
    if not target.is_relative_to(project.resolve()) or not target.is_file():
        raise ValueError("资源丢失或超出工程目录: " + str(path))
    # Reject links even when their current target happens to be inside the project.
    walk = project
    for part in path.parts:
        walk = walk / part
        if walk.is_symlink(): raise ValueError("分享资源不允许符号链接")
    return target

def browser_script(project, data):
    data = copy.deepcopy(data)
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    data["build"] = build_version(project, raw)
    return "window.COURSE_DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n", data["build"]

def versioned_entry(text, version, title):
    for name in RUNTIME[1:]:
        text = re.sub(r'(?P<q>["\'])' + re.escape(name) + r'(?:\?[^"\']*)?(?P=q)',
                      lambda m: m["q"] + name + "?v=" + version + m["q"], text)
    return re.sub(r"<title>.*?</title>", lambda m: "<title>" + html.escape(title) + "</title>", text, flags=re.S)

def public_media(project, data):
    """Re-encode selected images and make image-only PDFs without source metadata."""
    from PIL import Image
    media = {}
    for source in data["sources"]:
        images = []
        try:
            for page in data["slides"][source["id"]]:
                with Image.open(checked_file(project, page["image"])) as original:
                    image = original.convert("RGB")
                # A new pixel-only image discards EXIF, XMP and ICC metadata.
                clean = Image.new("RGB", image.size); clean.paste(image); image.close()
                encoded = io.BytesIO(); clean.save(encoded, "WEBP", lossless=True)
                media[page["image"]] = encoded.getvalue()
                images.append(clean)
            if images:
                pdf = io.BytesIO()
                images[0].save(pdf, "PDF", save_all=True, append_images=images[1:], resolution=144,
                               title=source["title"], author="", creator="", producer="",
                               creationDate="D:20000101000000Z", modDate="D:20000101000000Z")
                media[source["file"]] = pdf.getvalue()
        finally:
            for image in images: image.close()
    return media

def runtime_payload(project):
    payload = {name: checked_file(project, name).read_bytes() for name in RUNTIME if name != "course-data.js"}
    allowed_suffixes = {".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".avif",
                        ".gif", ".ico", ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".wav", ".ogg", ".mp4", ".webm"}
    for name in authored_data(project).get("share", {}).get("files", []):
        path = PurePosixPath(str(name).replace("\\", "/"))
        if path.parts and path.parts[0] in ("reference", "content", "sources", "pages", "handouts"):
            raise ValueError("share.files 不能加入私有备课目录")
        if path.suffix.lower() not in allowed_suffixes: raise ValueError("share.files 只能声明网页运行资源")
        target = checked_file(project, str(path))
        payload[str(path)] = target.read_bytes()
    return payload

def check_payload_dependencies(payload):
    class Links(HTMLParser):
        def __init__(self):
            super().__init__(); self.urls = []
        def handle_starttag(self, tag, attrs):
            for key, value in attrs:
                if value and (key in ("src", "poster", "data") or (key in ("href", "xlink:href") and tag != "a")):
                    self.urls.append(value)
    for name, raw in payload.items():
        urls = []
        if name.endswith((".html", ".svg")):
            parsed = Links(); parsed.feed(raw.decode("utf-8")); urls = parsed.urls
        elif name.endswith(".css"):
            urls = re.findall(r'url\(["\']?([^)"\']+)', raw.decode("utf-8"))
            urls += re.findall(r'@import\s+["\']([^"\']+)', raw.decode("utf-8"))
        for url in urls:
            url = url.strip()
            if url.startswith("#") or url.startswith("data:image/"): continue
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc:
                raise ValueError("离线分享包不允许外部运行资源: " + url)
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), unquote(parsed.path)))
            if target not in payload:
                raise ValueError("运行依赖未进入分享清单；请声明 share.files: " + target)

def build_project(args):
    project = Path(args.project).resolve()
    data = browser_data(project, getattr(args, "mode", "share"))
    text, version = browser_script(project, data)
    if data["exportMode"] == "share":
        for name, raw in public_media(project, data).items():
            if not name.startswith("handouts/"): continue
            target = project / name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(raw)
    (project / "course-data.js").write_text(text, encoding="utf-8")
    entry = project / "index.html"
    if entry.exists():
        entry.write_text(versioned_entry(entry.read_text(encoding="utf-8"), version, data.get("title", "自学课程")), encoding="utf-8")
    print("已构建: " + version + " (" + data["exportMode"] + ")")

def check(project, check_build=True):
    errors, warnings = [], []
    data = read_json(project / "content/course.json")
    if data is None: return {"errors": ["缺少作者数据"], "warnings": [], "counts": {}}
    manifest = read_json(project / "reference/source-manifest.json", {"sources": []})
    sources = {s["id"]: s for s in manifest["sources"]}
    slides = read_json(project / "reference/slides.json", {})
    seen, topic_ids, point_ids = set(), set(), set()
    coverage = {sid: set() for sid in sources}
    counts = {"sources": len(sources), "chapters": 0, "topics": 0, "points": 0, "questions": 0, "pages": sum(len(x) for x in slides.values())}
    def unique(obj, label):
        key = obj.get("id")
        if not isinstance(key, str) or not key.strip() or key in seen: errors.append(label + ": ID 缺失或重复: " + str(key))
        seen.add(key)
    def refs(values, label, cover=False):
        if not values: errors.append(label + ": 缺少原页引用")
        for ref in values or []:
            sid = ref.get("sourceId")
            if sid not in sources:
                errors.append(label + ": 未知 sourceId " + str(sid)); continue
            nums = ref.get("pages", [])
            if not nums: errors.append(label + ": 引用页码为空")
            for n in nums:
                if type(n) is not int or not 1 <= n <= sources[sid]["pageCount"]:
                    errors.append(label + ": 无效页码 " + str(n)); continue
                if cover: coverage[sid].add(n)
                found = next((x for x in slides.get(sid, []) if x["page"] == n), None)
                if not found or not (project / found["image"]).is_file():
                    errors.append(label + ": 缺少原页渲染 " + sid + "/" + str(n))
    models = (project / "models.js").read_text(encoding="utf-8") if (project / "models.js").exists() else ""
    registered = set(re.findall(r'STUDY_MODELS\s*\[\s*["\']([^"\']+)["\']\s*\]\s*=', models))
    chapters = data.get("chapters", [])
    if not chapters: errors.append("没有课程章节")
    for chapter in chapters:
        unique(chapter, "章节"); counts["chapters"] += 1
        if not chapter.get("topics"): errors.append(str(chapter.get("id")) + ": 没有主题")
        for topic in chapter.get("topics", []):
            unique(topic, "主题"); topic_ids.add(topic.get("id")); counts["topics"] += 1
            label = str(topic.get("id"))
            refs(topic.get("refs"), label, True)
            if not topic.get("points"): errors.append(label + ": 没有知识点")
            for point in topic.get("points", []):
                unique(point, "知识点"); point_ids.add(point.get("id")); counts["points"] += 1
                label = str(point.get("id"))
                for field in ("title", "question", "takeaway"):
                    if not isinstance(point.get(field), str) or not point[field].strip(): errors.append(label + ": 缺少 " + field)
                if len(point.get("steps", [])) < 2: errors.append(label + ": 推理至少需两个有效步骤")
                refs(point.get("refs"), label)
                lab = point.get("lab", {})
                if lab.get("kind") == "compare":
                    cases = lab.get("cases", [])
                    if len(cases) < 2: errors.append(label + ": 比较实验至少两个条件")
                    labels, conditions = set(), set()
                    for case in cases:
                        if case.get("label") in labels: errors.append(label + ": 案例标签重复")
                        labels.add(case.get("label"))
                        signature = (case.get("change"), tuple(case.get("chain", [])))
                        if signature in conditions: errors.append(label + ": 案例条件和推理完全重复")
                        conditions.add(signature)
                        for field in ("label", "change", "result", "why"):
                            if not case.get(field): errors.append(label + ": 案例缺少 " + field)
                        if len(case.get("chain", [])) < 2: errors.append(label + ": 案例因果链不足")
                elif lab.get("kind") == "custom":
                    if lab.get("modelId") not in registered: errors.append(label + ": 未注册模型 " + str(lab.get("modelId")))
                else: errors.append(label + ": 未明确配置实验")
    for q in data.get("questions", []):
        unique(q, "题目"); counts["questions"] += 1
        label = str(q.get("id"))
        if not q.get("question") or not q.get("explanation"): errors.append(label + ": 缺少题干或解释")
        if not q.get("topicIds"): errors.append(label + ": 未关联主题")
        if any(t not in topic_ids for t in q.get("topicIds", [])): errors.append(label + ": 主题不存在")
        if any(t not in point_ids for t in q.get("pointIds", [])): errors.append(label + ": 知识点不存在")
        if q.get("kind") == "single":
            choices = q.get("choices", [])
            if len(choices) < 2 or len(set(choices)) != len(choices): errors.append(label + ": 选项不足或重复")
            if type(q.get("answer")) is not int or not 0 <= q["answer"] < len(choices): errors.append(label + ": 答案下标无效")
        elif q.get("kind") == "written":
            if not isinstance(q.get("answer"), str) or not q["answer"].strip(): errors.append(label + ": 缺少评分点")
        else: errors.append(label + ": 未知题型")
        origin = q.get("source", {})
        kind = origin.get("kind")
        if kind not in ("coursework", "past-exam-original", "past-exam-adapted", "past-exam-extension", "unverified"):
            errors.append(label + ": 未标明题目来源类型")
        if kind and kind.startswith("past-exam-"):
            if any(not origin.get(k) for k in ("institution", "year", "exam", "item", "url")):
                errors.append(label + ": 真题相关出处不完整")
            if urlsplit(origin.get("url", "")).scheme not in ("http", "https"): errors.append(label + ": 出处网址无效")
        if kind == "unverified": warnings.append(label + ": 真题出处尚未核验")
    if not counts["questions"]: warnings.append("题库为空；不能交付为完整自测工具")
    for t in topic_ids:
        if not any(t in q.get("topicIds", []) for q in data.get("questions", [])):
            warnings.append(str(t) + ": 没有自测题")
    scope = data.get("scope", {})
    if scope.get("mode") not in ("demo", "full"): errors.append("scope.mode 必须为 demo 或 full")
    selected = scope.get("sourceIds") or [s["id"] for s in sources.values() if not s.get("companionOf")]
    for sid in selected:
        if sid not in sources: errors.append("范围包含未知来源: " + sid); continue
        if not sources[sid].get("rendered"): errors.append("范围中来源没有整页图: " + sid)
    for ex in scope.get("excludedPages", []):
        sid = ex.get("sourceId")
        if not ex.get("reason"): errors.append("排除页必须说明原因")
        if sid not in sources: errors.append("排除页来源不存在"); continue
        for n in ex.get("pages", []):
            if type(n) is not int or not 1 <= n <= sources[sid]["pageCount"]: errors.append("排除页码无效")
            else: coverage[sid].add(n)
    if scope.get("mode") == "full":
        for sid in selected:
            if sid in sources:
                missing = set(range(1, sources[sid]["pageCount"] + 1)) - coverage[sid]
                if missing: errors.append(sid + ": 未覆盖原页 " + ",".join(map(str, sorted(missing))))
    if data.get("review", {}).get("status") != "reviewed": warnings.append("内容审查尚未标记完成")
    for source_pages in slides.values():
        for page in source_pages:
            try:
                image = local_path(project, page["image"])
                if image is None or not image.is_file(): errors.append("原页资源丢失: " + page["image"])
            except ValueError as e: errors.append(str(e))
    for s in sources.values():
        try:
            original = local_path(project, s["file"])
            if original is None or not original.is_file(): errors.append("原课件副本丢失: " + s["file"])
        except ValueError as e: errors.append(str(e))
    for corr in data.get("corrections", []):
        if corr.get("sourceId") not in sources or not corr.get("text"): errors.append("原页更正信息无效")
        elif type(corr.get("page")) is not int or not 1 <= corr["page"] <= sources[corr["sourceId"]]["pageCount"]:
            errors.append("原页更正页码无效")
    for name in RUNTIME:
        if not (project / name).is_file(): errors.append("缺少运行文件: " + name)
    for name in ("index.html", "style.css"):
        path = project / name
        if not path.exists(): continue
        text = path.read_text(encoding="utf-8")
        urls = re.findall(r'(?:src|href)=["\']([^"\']+)["\']', text) if name.endswith("html") else re.findall(r'url\(["\']?([^)"\']+)', text)
        for url in urls:
            try:
                dest = local_path(project, url)
                if dest is not None and not dest.is_file(): errors.append("依赖丢失: " + url)
            except ValueError as e: errors.append(str(e))
    built = project / "course-data.js"
    if check_build and built.exists():
        try:
            current = built.read_text(encoding="utf-8")
            decoded = json.loads(current.removeprefix("window.COURSE_DATA = ").rstrip().removesuffix(";"))
            expected, _ = browser_script(project, browser_data(project, decoded.get("exportMode", "share")))
            if current != expected: errors.append("作者数据已更新；请重新 build")
        except (ValueError, KeyError, TypeError) as e:
            errors.append("重新 build 前需修正交付范围或浏览器数据: " + str(e))
    return {"errors": errors, "warnings": warnings, "counts": counts}

def validate(args):
    project = Path(args.project).resolve()
    report = check(project)
    write_json(project / "reference/validation.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0

def pack(args):
    project, output = Path(args.project).resolve(), Path(args.zip).resolve()
    mode = getattr(args, "mode", "share")
    report = check(project, check_build=False)
    if report["errors"]: raise ValueError("打包前校验失败:\n" + "\n".join(report["errors"]))
    if output.is_relative_to(project): raise ValueError("ZIP 请放在网站目录外，避免嵌套打包。")
    if output.exists(): raise ValueError("目标 ZIP 已存在，请选择新文件名。")
    data = browser_data(project, mode)
    script, version = browser_script(project, data)
    payload = runtime_payload(project)
    payload["course-data.js"] = script.encode("utf-8")
    payload["index.html"] = versioned_entry(payload["index.html"].decode("utf-8"), version, data.get("title", "自学课程")).encode("utf-8")
    payload["打开网页.cmd"] = b'@echo off\r\nstart "" "%~dp0index.html"\r\n'
    payload["使用说明.txt"] = "完整解压后，双击“打开网页.cmd”或 index.html。学习记录保存在当前浏览器本机。\n".encode("utf-8")
    if mode == "share":
        payload.update(public_media(project, data))
        root = "self-study"
    else:
        root = "self-study-archive"
        private_files = ["content/course.json", "reference/source-manifest.json", "reference/slides.json",
                         "reference/pptx-text.json", "reference/prepare-report.json"]
        private_files += [s["file"] for s in data["sources"]]
        private_files += [p["image"] for pages in data["slides"].values() for p in pages]
        for name in private_files:
            if (project / name).is_file(): payload[name] = checked_file(project, name).read_bytes()
        payload["本地归档说明.txt"] = "此包用于本地继续编辑，含原文件、文件名及备课备注。对外分享请重新运行 pack --mode share。\n".encode("utf-8")
    check_payload_dependencies(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, raw in sorted(payload.items()):
            info = zipfile.ZipInfo(root + "/" + name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.create_system = 3; info.external_attr = 0o100644 << 16
            z.writestr(info, raw)
    with zipfile.ZipFile(output) as z:
        bad = z.testzip()
        if bad: raise ValueError("ZIP 校验失败: " + bad)
    print(json.dumps({"zip": str(output), "mode": mode, "files": len(payload), "bytes": output.stat().st_size,
                      "sha256": digest(output), "warnings": report["warnings"]}, ensure_ascii=False, indent=2))

def serve(args):
    project = Path(args.project).resolve()
    if not (project / "index.html").is_file(): raise ValueError("缺少网页入口")
    mimetypes.add_type("text/javascript", ".js")
    with ThreadingHTTPServer(("127.0.0.1", args.port), partial(SimpleHTTPRequestHandler, directory=str(project))) as server:
        print("http://127.0.0.1:%d/" % server.server_port, flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init"); p.add_argument("--output", required=True); p.add_argument("--title", required=True)
    p = sub.add_parser("prepare"); p.add_argument("--input", required=True); p.add_argument("--project", required=True)
    p.add_argument("--width", type=int, default=1440); p.add_argument("--force", action="store_true")
    for name in ("build", "validate", "serve", "pack"):
        p = sub.add_parser(name); p.add_argument("--project", required=True)
        if name == "serve": p.add_argument("--port", type=int, default=0)
        if name == "pack": p.add_argument("--zip", required=True)
        if name in ("build", "pack"): p.add_argument("--mode", choices=("share", "archive"), default="share")
    args = parser.parse_args()
    if hasattr(args, "width") and args.width < 300: parser.error("--width 至少为 300")
    try:
        return {"init": init_project, "prepare": prepare, "build": build_project,
                "validate": validate, "pack": pack, "serve": serve}[args.command](args) or 0
    except (ValueError, OSError, KeyError, zipfile.BadZipFile, ET.ParseError) as e:
        print("错误: " + str(e), file=sys.stderr); return 1

if __name__ == "__main__":
    sys.exit(main())
