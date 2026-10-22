from django.contrib import messages
from django.db import IntegrityError, OperationalError, transaction
from django.shortcuts import redirect, render
from django.utils.translation import gettext
from .forms import TeacherForm
from .models import TeacherProfile


def index(request):
    profile = TeacherProfile.objects.filter(pk=1).first() or TeacherProfile(pk=1)
    form = TeacherForm(request.POST or None, instance=profile)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                current = TeacherProfile.objects.select_for_update().filter(pk=1).first()
                if form.cleaned_data["revision"] != (current.revision if current else 0):
                    form.add_error(None, gettext("Teacher details changed in another window. Reload before saving."))
                else:
                    current = current or TeacherProfile(pk=1)
                    current.name = form.cleaned_data["name"]
                    current.academic_status = form.cleaned_data["academic_status"]
                    current.revision += 1
                    current.save()
        except (IntegrityError, OperationalError):
            form.add_error(None, gettext("Teacher details could not be saved. Reload and try again."))
        else:
            if not form.errors:
                messages.success(request, gettext("Teacher details saved."))
                return redirect("teachers:index")
    return render(request, "teachers/index.html", {"active_page": "teacher", "form": form})
