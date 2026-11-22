from html.parser import HTMLParser
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from apps.academics.models import Course, CourseOffering
from apps.students.models import StudentClass
from apps.reports.forms import ModuleRecordSelectionForm


class ExportBarParser(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.in_bar = False
        self.in_form = False
        self.buttons = []
        self.forms = set()
        self.bar_in_form = None
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.in_form = True
            self.forms.add(attrs.get("id"))
        if tag == "section" and "report-export-bar" in attrs.get("class", "").split():
            self.in_bar = True
            self.bar_in_form = self.in_form
        if tag == "button" and self.in_bar:
            self.buttons.append(attrs)

    def handle_endtag(self, tag):
        if tag == "form":
            self.in_form = False
        if tag == "section":
            self.in_bar = False


class ReportActionTests(TestCase):
    def setUp(self):
        course = Course.objects.create(course_id="SCI", name="Science")
        self.period = CourseOffering.objects.create(course=course, academic_year="2569", semester="1")
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        self.period.classrooms.add(group)
        self.request = RequestFactory().get("/reports/module-record/")

    def render_bar(self, template, **context):
        context.setdefault("selection", ModuleRecordSelectionForm(initial={"offering": self.period.pk}))
        return ExportBarParser(render_to_string(template, context, request=self.request))

    def test_word_bar_submits_the_existing_preview_form_with_its_token(self):
        bar = self.render_bar("reports/module_record.html", selected=True, preview_token="valid-preview", entries=[])
        self.assertFalse(bar.bar_in_form)
        self.assertIn("module-record-form", bar.forms)
        self.assertEqual([button["value"] for button in bar.buttons], ["preview", "export"])
        self.assertTrue(all(button["form"] == "module-record-form" for button in bar.buttons))

    def test_word_bar_does_not_offer_export_when_preview_is_not_ready(self):
        bar = self.render_bar("reports/module_record.html", selected=True, preview_token="", entries=[])
        self.assertEqual([button["value"] for button in bar.buttons], ["preview"])

    def test_word_page_does_not_offer_a_bar_before_selection(self):
        self.assertEqual(self.render_bar("reports/module_record.html", selected=False).buttons, [])

    def test_excel_bar_submits_its_selection_form(self):
        bar = self.render_bar("reports/student_scores.html")
        self.assertFalse(bar.bar_in_form)
        self.assertIn("student-scores-form", bar.forms)
        self.assertEqual([button["value"] for button in bar.buttons], ["preview", "export"])
        self.assertTrue(all(button["form"] == "student-scores-form" for button in bar.buttons))

    def test_excel_bar_is_hidden_until_a_course_has_available_classrooms(self):
        bar = self.render_bar("reports/student_scores.html", selection=ModuleRecordSelectionForm())
        self.assertEqual(bar.buttons, [])
