import io
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

import launcher


class LocalAppTests(TestCase):
    def test_navigation_works_without_any_account(self):
        self.assertEqual(get_user_model().objects.count(), 0)
        for name in ["home", "students:index", "academics:index", "assessments:index", "reports:index"]:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'aria-label="Main navigation"')
                self.assertNotContains(response, "Sign in")
                self.assertNotContains(response, "Sign out")

    def test_account_and_admin_routes_are_removed(self):
        for url in ["/login/", "/logout/", "/admin/", "/admin/login/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)

    def test_anonymous_forms_still_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("academics:add"), {"course-course_id": "UNSAFE"})
        self.assertEqual(response.status_code, 403)
        from apps.academics.models import Course
        self.assertFalse(Course.objects.exists())
        self.assertEqual(client.get(reverse("students:add")).status_code, 200)
        from apps.students.models import Student, StudentClass
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        response = client.post(reverse("students:add"), {
            "roll_number": "1", "student_class": group.pk, "full_name": "Example Student",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)
        from apps.students.models import Student
        self.assertEqual(Student.objects.get().student_number, "256940101")

    def test_launcher_starts_server_without_account_prompt(self):
        server = Mock()
        with patch("django.setup"), patch("django.core.management.call_command") as command, patch("django.core.wsgi.get_wsgi_application", return_value=object()), patch("waitress.create_server", return_value=server) as create, patch("builtins.input", side_effect=AssertionError("Startup must not ask for an account")), patch("launcher.threading.Timer") as timer, redirect_stdout(io.StringIO()):
            launcher.serve(8000, True)
        self.assertEqual([call.args[0] for call in command.call_args_list], ["check", "migrate", "collectstatic"])
        self.assertEqual(create.call_args.kwargs, {"host": "127.0.0.1", "port": 8000})
        server.run.assert_called_once()
        server.close.assert_called_once()
        timer.return_value.start.assert_called_once()
        with patch("launcher.webbrowser.open") as open_browser:
            timer.call_args.args[1]()
        open_browser.assert_called_once_with("http://127.0.0.1:8000/")
