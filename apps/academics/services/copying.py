"""Copy teaching definitions into fresh records. Student results are never cloned."""
from copy import deepcopy
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _
from config.identifiers import assignment_identifier
from ..models import CourseOffering, CourseUnit
from .enrollment import sync_roster


def next_year(year):
    return str(int(year) + 1) if str(year).isascii() and str(year).isdigit() and len(str(year)) == 4 and 1000 <= int(year) < 9999 else ""


@transaction.atomic
def create_period(course, year, semester, classrooms):
    # Revalidate at the write boundary, including classroom/year constraints.
    from ..forms import OfferingForm
    form = OfferingForm({'academic_year': year, 'semester': semester, 'classrooms': [group.pk for group in classrooms]}, course=course)
    if not form.is_valid():
        raise ValidationError([message for errors in form.errors.values() for message in errors])
    period = form.save()
    sync_roster(period)
    return period


@transaction.atomic
def copy_modules(sources, destination, *, unit_override=None, renumber=False):
    from apps.assessments.models import Assignment
    from apps.assessments.services.schemes import export_scheme, replace_scheme
    from apps.assessments.services.evaluation import validate_evaluation_rubric
    destination = CourseOffering.objects.select_for_update().select_related('course').get(pk=destination.pk)
    ids = [module.pk for module in sources]
    modules = list(Assignment.objects.filter(pk__in=ids).select_related('unit', 'offering').prefetch_related('categories__criteria'))
    if len(modules) != len(set(ids)):
        raise ValidationError(_("Some source modules changed or were removed. Reload before copying."))
    modules.sort(key=lambda item: (item.assignment_number is None, item.assignment_number or 0, item.pk))
    used = set(Assignment.objects.filter(offering__course=destination.course, offering__academic_year=destination.academic_year).values_list('assignment_number', flat=True))
    copied = []
    for source in modules:
        number = source.assignment_number
        if number is None or number in used:
            if number is not None and not renumber:
                raise ValidationError(_("Module number %(number)s is already used in the destination course and academic year. Enable renumbering or copy this module individually with another number.") % {'number': number})
            number = next((value for value in range(1, 100) if value not in used), None)
        if number is None:
            raise ValidationError(_("The destination course and academic year has no available module numbers from 1 to 99."))
        used.add(number)
        key = assignment_identifier(destination.academic_year, destination.course.course_id, number)
        if Assignment.objects.filter(assignment_id=key).exists():
            raise ValidationError(_("The generated module ID %(id)s is already used. Choose another module number.") % {'id': key})
        if unit_override is not None:
            unit = unit_override
        else:
            if source.unit is None or source.unit.course_id != source.offering.course_id:
                raise ValidationError(_("Module %(module)s needs a valid unit before bulk copying. Edit it first or copy it individually and choose a destination unit.") % {'module': source.assignment_id})
            unit, created = CourseUnit.objects.get_or_create(course=destination.course, unit_id=source.unit.unit_id, defaults={'name': source.unit.name})
            if not created and unit.name != source.unit.name:
                raise ValidationError(_("Destination unit %(unit)s has a different name. Copy the module individually to choose its unit.") % {'unit': source.unit.unit_id})
        if unit.course_id != destination.course_id:
            raise ValidationError(_("Choose a unit belonging to the destination course."))
        module = Assignment.objects.create(
            assignment_number=number, name=source.name, information=source.information,
            offering=destination, unit=unit, calculation_mode=source.calculation_mode,
            evaluation_rubric=deepcopy(validate_evaluation_rubric(source.evaluation_rubric)))
        replace_scheme(module, deepcopy(export_scheme(source)))
        copied.append(module)
    return copied
