"""Shared GET preview / CSRF-protected POST confirmation for record deletion."""
from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.http import require_http_methods

from .deletion import ROOT_MODELS, build_plan

SALT = 'gradebook-delete-records-v1'


class DeleteConfirmationForm(forms.Form):
    snapshot = forms.CharField(widget=forms.HiddenInput)
    confirmed = forms.BooleanField(label=gettext_lazy('I understand that all listed records will be permanently deleted.'))


def title(kind):
    return {'classroom': _('Delete classroom'), 'student': _('Delete student'),
            'course': _('Delete course'), 'unit': _('Delete unit'), 'module': _('Delete module')}[kind]


def explanation(kind):
    return {
        'classroom': _('This deletes the classroom, its students, and their enrolments, scores, and attendance. Student records shared with other classrooms are also deleted everywhere. Courses and modules are kept.'),
        'student': _('This deletes the student from every classroom and course, including all saved scores and attendance. Classrooms, courses, and modules are kept.'),
        'course': _('This deletes the course across all academic years and semesters, including its units, modules, enrolments, scores, attendance, and classroom module records. Students and classrooms are kept.'),
        'unit': _('This deletes the unit and all its modules across all teaching periods, including their marking schemes, scores, attendance, and classroom module records. The course, students, and classrooms are kept.'),
        'module': _('This deletes the module and its marking scheme, scores, attendance, and classroom records for every enrolled classroom. The course, unit, students, and classrooms are kept.'),
    }[kind]


def destinations(kind, obj):
    if kind == 'classroom':
        return reverse('students:classroom-detail', args=[obj.pk]), reverse('students:index')
    if kind == 'student':
        return reverse('students:edit', args=[obj.pk]), reverse('students:all')
    if kind == 'course':
        return reverse('academics:detail', args=[obj.pk]), reverse('academics:index')
    if kind == 'unit':
        return reverse('academics:unit-detail', args=[obj.course_id, obj.pk]), reverse('academics:detail', args=[obj.course_id])
    return reverse('assessments:detail', args=[obj.pk]), reverse('academics:detail', args=[obj.offering.course_id])


@require_http_methods(['GET', 'POST'])
def delete_record(request, kind, pk, course_pk=None):
    filters = {'pk': pk}
    if kind == 'unit':
        filters['course_id'] = course_pk
    obj = get_object_or_404(ROOT_MODELS[kind], **filters)
    cancel_url, success_url = destinations(kind, obj)
    error = ''
    form = None
    status = 200
    if request.method == 'POST':
        form = DeleteConfirmationForm(request.POST)
        if form.is_valid():
            try:
                fingerprint = signing.loads(form.cleaned_data['snapshot'], salt=SALT, max_age=1800)
                with transaction.atomic():
                    obj = get_object_or_404(ROOT_MODELS[kind].objects.select_for_update(), **filters)
                    plan = build_plan(kind, obj)
                    if not isinstance(fingerprint, str) or not constant_time_compare(fingerprint, plan.fingerprint):
                        raise ValidationError(_('These records changed after the preview. Review the updated list and confirm again.'))
                    plan.delete()
            except signing.BadSignature:
                error = _('This deletion preview is invalid or expired. Review the updated list and confirm again.')
            except ValidationError as issue:
                error = ' '.join(issue.messages)
            except (IntegrityError, OperationalError):
                error = _('Linked records changed or another save is in progress. Nothing was deleted. Review the updated list and try again.')
            else:
                messages.success(request, _('Deletion complete.'))
                return redirect(success_url)
            status = 409
            form = None  # New snapshot and unchecked confirmation after any conflict.
        else:
            status = 400
            error = _('Review the list and check the confirmation box before deleting.')
            form = None
    plan = build_plan(kind, obj)
    if form is None:
        form = DeleteConfirmationForm(initial={'snapshot': signing.dumps(plan.fingerprint, salt=SALT)})
    return render(request, 'delete_confirm.html', {
        'active_page': 'students' if kind in {'classroom', 'student'} else 'assignments' if kind == 'module' else 'courses',
        'title': title(kind), 'target': obj, 'explanation': explanation(kind),
        'groups': plan.summary, 'total': plan.total, 'cancel_url': cancel_url,
        'form': form, 'error': error,
    }, status=status)


def classroom(request, pk):
    return delete_record(request, 'classroom', pk)


def student(request, pk):
    return delete_record(request, 'student', pk)


def course(request, pk):
    return delete_record(request, 'course', pk)


def unit(request, course_pk, pk):
    return delete_record(request, 'unit', pk, course_pk)


def module(request, pk):
    return delete_record(request, 'module', pk)
