import json
from decimal import Decimal
from django.test import TestCase, SimpleTestCase
from django.utils.translation import override
from apps.academics.models import Course, CourseOffering, CourseUnit
from apps.assessments.models import Assignment, MarkingSchemeCategory
from apps.assessments.marking_library_forms import MarkingLibraryForm
from apps.assessments.services.marking_library import category_catalog
from apps.assessments.services.presets import default_scheme
from apps.assessments.services.schemes import replace_scheme, export_scheme
from config.numbers import compact_number
from apps.reports.services.context import percentage, infer_category


class CompactNumberTests(SimpleTestCase):
    def test_display_keeps_meaningful_digits_and_zero(self):
        for value, expected in [('10.00', '10'), ('10.50', '10.5'), ('10.25', '10.25'),
                                ('0.00', '0'), ('3.335', '3.34'), ('-0.001', '0')]:
            self.assertEqual(compact_number(Decimal(value)), expected)
        self.assertEqual(percentage(2, 3), '66.67')
        self.assertEqual(percentage(3, 3), '100')
        self.assertEqual(percentage(0, 0), '0')


class MarkingLibraryTests(TestCase):
    def payload(self, **changes):
        return {'name_th': 'ด้านทดสอบ', 'name_en': 'Example',
                'subcategories_json': json.dumps([{'name_th': 'งาน', 'name_en': 'Work', 'maximum': '10.50', 'weight': '1.00'}]), **changes}

    def test_seed_and_bilingual_fallback(self):
        self.assertEqual(MarkingSchemeCategory.objects.count(), 4)
        self.assertEqual(sum(len(c.subcategories) for c in MarkingSchemeCategory.objects.all()), 15)
        with override('th'):
            self.assertEqual(default_scheme()[0]['name'], 'ด้านความรู้ (K)')
            self.assertEqual(default_scheme()[-1]['name'], 'ด้านสมรรถนะของผู้เรียน (C)')
        with override('en'):
            self.assertEqual(default_scheme()[0]['name'], 'Knowledge (K)')
        MarkingSchemeCategory.objects.create(name_th='ชื่อไทยเท่านั้น')
        with override('en'):
            self.assertEqual(category_catalog()[-1]['name'], 'ชื่อไทยเท่านั้น')

    def test_create_edit_delete_and_stale_changes(self):
        self.assertEqual(self.client.post('/modules/marking-library/add/', self.payload()).status_code, 302)
        record = MarkingSchemeCategory.objects.get(name_en='Example')
        self.assertEqual(record.subcategories[0]['maximum'], '10.5')
        self.assertEqual(record.subcategories[0]['weight'], '1')
        url = f'/modules/marking-library/{record.pk}/edit/'
        self.assertEqual(self.client.post(url, self.payload(name_en='Changed', revision=1)).status_code, 302)
        self.assertEqual(self.client.post(url, self.payload(name_en='Stale', revision=1)).status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.name_en, 'Changed')
        delete = f'/modules/marking-library/{record.pk}/delete/'
        self.assertEqual(self.client.post(delete, {'revision': 1}).status_code, 200)
        self.assertTrue(MarkingSchemeCategory.objects.filter(pk=record.pk).exists())
        self.assertEqual(self.client.post(delete, {'revision': 2}).status_code, 302)
        self.assertFalse(MarkingSchemeCategory.objects.filter(pk=record.pk).exists())

    def test_invalid_names_scores_and_weights(self):
        for item in [{'name_th': '', 'weight': 1}, {'name_en': 'Work', 'weight': 0},
                     {'name_en': 'Work', 'weight': True}, {'name_en': 'Work', 'maximum': 'NaN', 'weight': 1},
                     {'name_en': 'Work', 'maximum': '0', 'weight': 1},
                     {'name_en': 'Work', 'maximum': '1.234', 'weight': 1}]:
            form = MarkingLibraryForm(self.payload(subcategories_json=json.dumps([item])))
            self.assertFalse(form.is_valid(), item)
        form = MarkingLibraryForm(self.payload(subcategories_json=json.dumps([{'name_en': 'Work', 'weight': 1}])))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['subcategories_json'][0]['maximum'], '')

    def test_module_copies_survive_library_changes(self):
        course = Course.objects.create(course_id='LIB', name='Library check')
        period = CourseOffering.objects.create(course=course, academic_year='2569', semester='1')
        unit = CourseUnit.objects.create(course=course, unit_id='01', name='Unit')
        with override('en'):
            category = category_catalog()[0]
            scheme = [{'name': category['name'], 'items': [{'name': category['items'][0]['name'], 'maximum': '10'}]}]
        data = {'assignment_number': 1, 'name': 'Copied module', 'offering': period.pk, 'unit': unit.pk,
                'calculation_mode': 'points', 'scheme_json': json.dumps(scheme)}
        self.assertEqual(self.client.post('/modules/add/', data).status_code, 302)
        module = Assignment.objects.get(offering=period)
        before = export_scheme(module)
        library = MarkingSchemeCategory.objects.get(pk=category['id'])
        library.name_en = 'Renamed'; library.subcategories = []; library.save()
        self.assertEqual(export_scheme(module), before)
        library.delete()
        self.assertEqual(export_scheme(module), before)
        self.assertEqual(before[0]['items'][0]['maximum'], '10')

    def test_empty_library_stays_empty_and_custom_modules_still_work(self):
        MarkingSchemeCategory.objects.all().delete()
        self.assertEqual(default_scheme(), [])
        self.assertEqual(self.client.get('/modules/add/').status_code, 200)
        self.assertEqual(MarkingSchemeCategory.objects.count(), 0)

    def test_report_category_matching_supports_both_library_languages(self):
        for language in ['th', 'en']:
            with override(language):
                categories = category_catalog()
                for key in ['knowledge', 'skills', 'attitudes', 'competencies']:
                    self.assertIsNotNone(infer_category(categories, key), (language, key))
