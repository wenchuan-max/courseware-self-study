"""Isolated regression checks. No user courseware is bundled."""
import copy
import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills/courseware-self-study"
SCRIPT = SKILL / "scripts/courseware.py"
spec = importlib.util.spec_from_file_location("courseware", SCRIPT)
cw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cw)

def make_pdf(path):
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] /Resources << /Font << /F1 7 0 R >> >> /Contents 4 0 R >>",
        None,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] /Resources << /Font << /F1 7 0 R >> >> /Contents 6 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    for index, text in [(3, b"Independent events: product rule."), (5, b"Check independence before multiplying marginals.")]:
        content = b"BT /F1 16 Tf 25 300 Td (" + text + b") Tj ET"
        objects[index] = b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
    result = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(str(i).encode() + b" 0 obj\n" + obj + b"\nendobj\n")
    start = len(result)
    result.extend(b"xref\n0 8\n0000000000 65535 f \n")
    for off in offsets: result.extend(("%010d 00000 n \n" % off).encode())
    result.extend(b"trailer\n<< /Size 8 /Root 1 0 R >>\nstartxref\n" + str(start).encode() + b"\n%%EOF\n")
    path.write_bytes(result)

class WorkflowTests(unittest.TestCase):
    @staticmethod
    def run_cli(*args, expected=0):
        r = subprocess.run([sys.executable, "-B", "-X", "utf8", str(SCRIPT), *map(str, args)],
                           capture_output=True, text=True, encoding="utf-8")
        if r.returncode != expected: raise AssertionError(r.stdout + r.stderr)
        return r

    @classmethod
    def setUpClass(cls):
        cls.base = tempfile.TemporaryDirectory(prefix="courseware-test-")
        cls.root = Path(cls.base.name)
        cls.inputs = cls.root / "inputs"
        cls.inputs.mkdir()
        make_pdf(cls.inputs / "probability.pdf")
        cls.original_hash = cw.digest(cls.inputs / "probability.pdf")
        cls.prototype = cls.root / "prototype"
        cls.run_cli("init", "--output", cls.prototype, "--title", "Probability")
        cls.run_cli("prepare", "--input", cls.inputs, "--project", cls.prototype, "--width", 600)
        sid = cw.read_json(cls.prototype / "reference/source-manifest.json")["sources"][0]["id"]
        refs = [{"sourceId": sid, "pages": [1, 2]}]
        point = {
            "id": "point-product", "title": "Independent product",
            "question": "When may we multiply marginals?",
            "steps": ["Check independence.", "Multiply only under that condition."],
            "takeaway": "Conditions come first.", "refs": refs,
            "lab": {"kind": "compare", "title": "Compare conditions", "cases": [
                {"label": "Independent", "change": "Independence is given.",
                 "chain": ["Condition holds", "Multiply marginals"], "result": "Product applies",
                 "why": "Conditional probability equals its marginal."},
                {"label": "Unknown", "change": "Only marginals are known.",
                 "chain": ["Independence is unknown", "Joint distribution is unspecified"],
                 "result": "Insufficient information", "why": "Dependence information is needed."}]}}
        area = copy.deepcopy(point)
        area.update(id="point-area", title="Area model")
        area["lab"] = {"kind": "custom", "title": "Joint area", "modelId": "independent-product",
                       "parameters": {"a": 0.5, "b": 0.25}}
        cls.data = {
            "schemaVersion": 1, "id": "test-course", "title": "Probability",
            "scope": {"mode": "full", "sourceIds": [sid], "excludedPages": []},
            "chapters": [{"id": "ch-1", "title": "Events", "topics": [{
                "id": "topic-1", "title": "Independence", "refs": refs, "points": [point, area]}]}],
            "questions": [{"id": "q-1", "topicIds": ["topic-1"], "pointIds": ["point-product"],
                "kind": "single", "question": "Do marginals imply independence?",
                "choices": ["No", "Yes"], "answer": 0, "explanation": ["The joint distribution is needed."],
                "source": {"kind": "coursework"}}],
            "review": {"status": "reviewed", "notes": ["Synthetic fixture."]}, "corrections": []}

    @classmethod
    def tearDownClass(cls): cls.base.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="courseware-case-")
        self.project = Path(self.work.name) / "site"
        shutil.copytree(self.prototype, self.project)
        self.write_data(copy.deepcopy(self.data))

    def tearDown(self): self.work.cleanup()

    def write_data(self, data):
        cw.write_json(self.project / "content/course.json", data)
        self.run_cli("build", "--project", self.project)

    def errors(self): return cw.check(self.project)["errors"]

    def test_end_to_end_and_zip_dependencies(self):
        self.assertEqual([], self.errors())
        index = self.project / "index.html"
        index.write_text(index.read_text(encoding="utf-8").replace(
            "</head>", '<script src="extra.js?v=1" defer></script></head>'), encoding="utf-8")
        (self.project / "extra.js").write_text("// runtime\n", encoding="utf-8")
        target = Path(self.work.name) / "share.zip"
        self.run_cli("validate", "--project", self.project)
        self.run_cli("pack", "--project", self.project, "--zip", target)
        with zipfile.ZipFile(target) as z:
            self.assertIsNone(z.testzip())
            self.assertIn("site/extra.js", z.namelist())
            self.assertIn("site/打开网页.cmd", z.namelist())
            self.assertFalse(any("__pycache__" in x for x in z.namelist()))

    def test_nonempty_directory_is_not_overwritten(self):
        before = cw.digest(self.project / "content/course.json")
        self.run_cli("init", "--output", self.project, "--title", "Overwrite", expected=1)
        self.assertEqual(before, cw.digest(self.project / "content/course.json"))

    def test_source_unchanged_and_cache_reused(self):
        sid = self.data["scope"]["sourceIds"][0]
        image = self.project / "pages" / sid / "0001.webp"
        stamp = image.stat().st_mtime_ns
        self.run_cli("prepare", "--input", self.inputs, "--project", self.project, "--width", 600)
        self.assertEqual(stamp, image.stat().st_mtime_ns)
        self.assertEqual(self.original_hash, cw.digest(self.inputs / "probability.pdf"))

    def test_missing_coverage(self):
        data = copy.deepcopy(self.data)
        data["chapters"][0]["topics"][0]["refs"][0]["pages"] = [1]
        self.write_data(data)
        self.assertTrue(any("未覆盖" in x for x in self.errors()))

    def test_missing_model(self):
        data = copy.deepcopy(self.data)
        data["chapters"][0]["topics"][0]["points"][1]["lab"]["modelId"] = "missing"
        self.write_data(data)
        self.assertTrue(any("未注册" in x for x in self.errors()))

    def test_missing_image(self):
        sid = self.data["scope"]["sourceIds"][0]
        (self.project / "pages" / sid / "0001.webp").unlink()
        self.assertTrue(any("原页" in x for x in self.errors()))

    def test_invalid_answer(self):
        data = copy.deepcopy(self.data)
        data["questions"][0]["answer"] = 9
        self.write_data(data)
        self.assertTrue(any("下标" in x for x in self.errors()))

    def test_exam_requires_metadata(self):
        data = copy.deepcopy(self.data)
        data["questions"][0]["source"] = {"kind": "past-exam-original"}
        self.write_data(data)
        self.assertTrue(any("出处不完整" in x for x in self.errors()))

    def test_authored_content_requires_build(self):
        path = self.project / "content/course.json"
        data = cw.read_json(path)
        data["title"] = "Changed"
        cw.write_json(path, data)
        self.assertTrue(any("build" in x for x in self.errors()))

    def test_runtime_requires_build(self):
        path = self.project / "style.css"
        path.write_text(path.read_text(encoding="utf-8") + "\n/* changed */", encoding="utf-8")
        self.assertTrue(any("build" in x for x in self.errors()))

    def test_pptx_order_and_notes(self):
        path = Path(self.work.name) / "notes.pptx"
        pns = "http://schemas.openxmlformats.org/presentationml/2006/main"
        rns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
        ans = "http://schemas.openxmlformats.org/drawingml/2006/main"
        relns = "http://schemas.openxmlformats.org/package/2006/relationships"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("ppt/presentation.xml", '<p:presentation xmlns:p="' + pns + '" xmlns:r="' + rns +
                '"><p:sldIdLst><p:sldId id="2" r:id="r2"/><p:sldId id="1" r:id="r1"/></p:sldIdLst></p:presentation>')
            z.writestr("ppt/_rels/presentation.xml.rels", '<Relationships xmlns="' + relns +
                '"><Relationship Id="r1" Target="slides/slide1.xml"/><Relationship Id="r2" Target="slides/slide2.xml"/></Relationships>')
            for n in (1, 2):
                z.writestr("ppt/slides/slide%d.xml" % n,
                    '<p:sld xmlns:p="' + pns + '" xmlns:a="' + ans + '"><a:t>Slide ' + str(n) + '</a:t></p:sld>')
            z.writestr("ppt/slides/_rels/slide2.xml.rels", '<Relationships xmlns="' + relns +
                '"><Relationship Id="n" Type="' + rns + '/notesSlide" Target="../notesSlides/notesSlide1.xml"/></Relationships>')
            z.writestr("ppt/notesSlides/notesSlide1.xml",
                '<p:notes xmlns:p="' + pns + '" xmlns:a="' + ans + '"><a:t>Teacher notes</a:t></p:notes>')
        slides = cw.pptx_text(path)
        self.assertEqual(["Slide 2", "Slide 1"], [p["text"] for p in slides])
        self.assertEqual("Teacher notes", slides[0]["notes"])

if __name__ == "__main__":
    unittest.main()
