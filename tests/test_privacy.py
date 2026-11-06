"""Privacy regressions use synthetic markers and never read user courseware."""
import copy
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from PIL import Image, ImageChops
import pypdfium2 as pdfium
import test_workflow as base

cw = base.cw
MARKER = "PRIVATE_SENTINEL"

def make_private_pdf(path):
    objects = [b"<< /Type /Catalog /Pages 2 0 R >>", None]
    for n, text in enumerate(("Public first page", MARKER + " second page", "Public third page")):
        page_num = 3 + n * 2
        objects.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 400] /Resources << /Font << /F1 9 0 R >> >> /Contents %d 0 R >>" % (page_num+1)).encode())
        content = ("BT /F1 16 Tf 25 300 Td (%s) Tj ET" % text).encode()
        objects.append(b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream")
    objects[1] = b"<< /Type /Pages /Kids [3 0 R 5 0 R 7 0 R] /Count 3 >>"
    objects += [b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                ("<< /Author (%s AUTHOR) /Title (%s TITLE) >>" % (MARKER, MARKER)).encode()]
    result = bytearray(b"%PDF-1.4\n"); offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(result)); result.extend(str(i).encode()+b" 0 obj\n"+obj+b"\nendobj\n")
    start = len(result); result.extend(b"xref\n0 11\n0000000000 65535 f \n")
    for off in offsets: result.extend(("%010d 00000 n \n" % off).encode())
    result.extend(b"trailer\n<< /Size 11 /Root 1 0 R /Info 10 0 R >>\nstartxref\n"+str(start).encode()+b"\n%%EOF\n")
    path.write_bytes(result)

def make_private_pptx(path):
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    r = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    rel = "http://schemas.openxmlformats.org/package/2006/relationships"
    with zipfile.ZipFile(path,"w") as z:
        z.writestr("ppt/presentation.xml", '<p:presentation xmlns:p="'+p+'" xmlns:r="'+r+'"><p:sldIdLst><p:sldId id="1" r:id="s"/></p:sldIdLst></p:presentation>')
        z.writestr("ppt/_rels/presentation.xml.rels", '<Relationships xmlns="'+rel+'"><Relationship Id="s" Target="slides/slide1.xml"/></Relationships>')
        z.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="'+p+'" xmlns:a="'+a+'"><a:t>Public slide</a:t></p:sld>')
        z.writestr("ppt/slides/_rels/slide1.xml.rels", '<Relationships xmlns="'+rel+'"><Relationship Id="n" Type="'+r+'/notesSlide" Target="../notesSlides/n.xml"/></Relationships>')
        z.writestr("ppt/notesSlides/n.xml", '<p:notes xmlns:p="'+p+'" xmlns:a="'+a+'"><a:t>'+MARKER+' NOTES</a:t></p:notes>')
        z.writestr("docProps/core.xml", "<author>"+MARKER+"</author>")

class PrivacyTests(unittest.TestCase):
    run_cli = staticmethod(base.WorkflowTests.run_cli)
    write_data = base.WorkflowTests.write_data
    errors = base.WorkflowTests.errors

    @classmethod
    def setUpClass(cls):
        base.WorkflowTests.setUpClass.__func__(cls)
        folder = cls.inputs / MARKER
        folder.mkdir()
        make_private_pdf(folder / (MARKER+".pdf"))
        make_private_pptx(folder / (MARKER+".pptx"))
        cls.run_cli("prepare","--input",cls.inputs,"--project",cls.prototype,"--width",600)
        sources = cw.read_json(cls.prototype/"reference/source-manifest.json")["sources"]
        cls.source = next(s for s in sources if s["type"]=="pdf" and MARKER in s["title"])
        cls.data["scope"] = {"mode":"demo","sourceIds":[cls.source["id"]],"excludedPages":[
            {"sourceId":cls.source["id"],"pages":[2],"reason":MARKER}]}
        topic = cls.data["chapters"][0]["topics"][0]
        topic["refs"] = [{"sourceId":cls.source["id"],"pages":[1,3]}]
        for point in topic["points"]: point["refs"] = copy.deepcopy(topic["refs"])
        cls.data["review"]["notes"] = [MARKER]
        cls.data["privateNotes"] = MARKER
        cls.data["drafts"] = {"q-1":MARKER}
        topic["privateNotes"] = MARKER
        topic["points"][0]["lab"]["privateNotes"] = MARKER
        cls.data["questions"][0]["source"]["privateNotes"] = MARKER
        cls.data["corrections"] = [{"sourceId":cls.source["id"],"page":2,"text":MARKER}]

    @classmethod
    def tearDownClass(cls): cls.base.cleanup()

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="privacy-test-")
        self.project = Path(self.work.name)/("site-"+MARKER)
        shutil.copytree(self.prototype,self.project)
        self.write_data(copy.deepcopy(self.data))
        (self.project/"reference/author-notes.txt").write_text(MARKER,encoding="utf-8")
        (self.project/"reference/.private").mkdir()
        (self.project/"reference/.private/notes.txt").write_text(MARKER,encoding="utf-8")
        (self.project/"assets/unused.txt").write_text(MARKER,encoding="utf-8")

    def tearDown(self): self.work.cleanup()

    def package(self,mode="share"):
        target=Path(self.work.name)/(mode+".zip")
        self.run_cli("pack","--project",self.project,"--zip",target,"--mode",mode)
        with zipfile.ZipFile(target) as z:
            return {n:z.read(n) for n in z.namelist()}

    def browser(self):
        text=(self.project/"course-data.js").read_text(encoding="utf-8")
        return json.loads(text.removeprefix("window.COURSE_DATA = ").rstrip().removesuffix(";"))

    def test_browser_data_excludes_private_fields_and_unselected_pages(self):
        public=self.browser()
        self.assertNotIn(MARKER,json.dumps(public))
        self.assertEqual([1,3],public["sources"][0]["availablePages"])
        self.assertEqual([1,3],[p["page"] for p in public["slides"][self.source["id"]]])
        self.assertNotIn("review",public)
        self.assertNotIn("relativeInput",public["sources"][0])
        self.assertEqual("课件 1",public["sources"][0]["title"])

    def test_default_zip_contains_only_public_teaching_material(self):
        files=self.package()
        self.assertTrue(all(n.startswith("self-study/") for n in files))
        self.assertFalse(any(MARKER in n or "/reference/" in n or "/content/" in n or "/sources/" in n for n in files))
        self.assertFalse(any(n.endswith(".pptx") for n in files))
        for name,raw in files.items():
            self.assertNotIn(MARKER.encode(),raw,name)
        self.assertEqual(1,len([n for n in files if n.endswith(".pdf")]))
        self.assertEqual(2,len([n for n in files if n.endswith(".webp")]))

    def test_selected_pdf_has_no_original_metadata_and_only_selected_pages(self):
        files=self.package()
        raw=next(b for n,b in files.items() if n.endswith(".pdf"))
        with pdfium.PdfDocument(raw) as doc:
            self.assertEqual(2,len(doc))
            self.assertNotIn(MARKER,str(doc.get_metadata_dict()))
            self.assertEqual("",doc.get_metadata_value("Author"))
        self.assertNotEqual((self.inputs/self.source["relativeInput"]).read_bytes(),raw)

    def test_visual_pixels_are_preserved_without_metadata(self):
        image_path=cw.read_json(self.project/"reference/slides.json")[self.source["id"]][0]["image"]
        path=self.project/image_path
        with Image.open(path) as im:
            pixels=im.convert("RGB")
            pixels.save(path,"WEBP",lossless=True,xmp=MARKER.encode(),exif=b"Exif\0\0"+MARKER.encode())
        files=self.package()
        with Image.open(io.BytesIO(files["self-study/"+image_path])) as cleaned:
            self.assertFalse(cleaned.info.get("xmp"))
            self.assertFalse(cleaned.info.get("exif"))
            self.assertIsNone(ImageChops.difference(pixels,cleaned.convert("RGB")).getbbox())
        pixels.close()

    def test_archive_retains_originals_for_local_editing(self):
        files=self.package("archive")
        sources=cw.read_json(self.project/"reference/source-manifest.json")["sources"]
        for source in sources:
            self.assertEqual((self.project/source["file"]).read_bytes(),files["self-study-archive/"+source["file"]])
        self.assertIn(MARKER.encode(),files["self-study-archive/reference/pptx-text.json"])
        self.assertIn("self-study-archive/content/course.json",files)

    def test_pack_share_rebuilds_even_after_an_archive_build(self):
        self.run_cli("build","--project",self.project,"--mode","archive")
        self.assertIn(MARKER,(self.project/"course-data.js").read_text(encoding="utf-8"))
        files=self.package()
        self.assertNotIn(MARKER.encode(),files["self-study/course-data.js"])

    def test_unlisted_runtime_dependency_fails_instead_of_being_added(self):
        index=self.project/"index.html"
        index.write_text(index.read_text(encoding="utf-8").replace("</head>",'<script src="extra.js"></script></head>'),encoding="utf-8")
        (self.project/"extra.js").write_text("// safe runtime",encoding="utf-8")
        self.run_cli("pack","--project",self.project,"--zip",Path(self.work.name)/"blocked.zip",expected=1)

    def test_private_directory_cannot_be_declared_as_runtime(self):
        data=copy.deepcopy(self.data)
        data["share"]={"files":["reference/private.js"]}
        (self.project/"reference/private.js").write_text(MARKER,encoding="utf-8")
        self.write_data(data)
        self.run_cli("pack","--project",self.project,"--zip",Path(self.work.name)/"blocked.zip",expected=1)

    def test_hidden_directory_cannot_be_declared_as_runtime(self):
        (self.project/"assets/.hidden").mkdir()
        (self.project/"assets/.hidden/private.js").write_text(MARKER,encoding="utf-8")
        data=copy.deepcopy(self.data);data["share"]={"files":["assets/.hidden/private.js"]}
        self.write_data(data)
        self.run_cli("pack","--project",self.project,"--zip",Path(self.work.name)/"blocked.zip",expected=1)

    def test_external_runtime_dependency_is_rejected(self):
        css=self.project/"style.css"
        css.write_text(css.read_text(encoding="utf-8")+"\n@import 'https://example.com/font.css';",encoding="utf-8")
        self.run_cli("pack","--project",self.project,"--zip",Path(self.work.name)/"blocked.zip",expected=1)

    def test_public_alias_and_custom_parameters_are_preserved(self):
        data=copy.deepcopy(self.data)
        data["share"]={"sourceTitles":{self.source["id"]:"概率示例"}}
        self.write_data(data)
        public=self.browser()
        self.assertEqual("概率示例",public["sources"][0]["title"])
        self.assertEqual(data["chapters"][0]["topics"][0]["points"][1]["lab"]["parameters"],
                         public["chapters"][0]["topics"][0]["points"][1]["lab"]["parameters"])
        self.assertEqual(data["questions"][0]["choices"],public["questions"][0]["choices"])
        self.assertEqual(data["questions"][0]["answer"],public["questions"][0]["answer"])
        self.assertEqual(data["id"],public["id"])

    def test_excluded_page_cannot_be_referenced_accidentally(self):
        data=copy.deepcopy(self.data)
        data["chapters"][0]["topics"][0]["refs"][0]["pages"].append(2)
        cw.write_json(self.project/"content/course.json",data)
        self.run_cli("build","--project",self.project,expected=1)

    def test_zip_metadata_does_not_copy_host_paths_or_timestamps(self):
        files=self.package()
        with zipfile.ZipFile(Path(self.work.name)/"share.zip") as z:
            self.assertTrue(all(i.date_time==(2000,1,1,0,0,0) and not i.extra and not i.comment for i in z.infolist()))

if __name__=="__main__":unittest.main()
