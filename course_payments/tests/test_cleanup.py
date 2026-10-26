"""
Run inside the LMS container (see README):
    pytest /mnt/openedx-course-payments/course_payments/tests
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.course_modes.tests.factories import CourseModeFactory
from common.djangoapps.student.models import CourseAccessRole, CourseEnrollment
from common.djangoapps.student.tests.factories import CourseEnrollmentFactory, UserFactory
from lms.djangoapps.certificates.models import GeneratedCertificate
from lms.djangoapps.certificates.tests.factories import GeneratedCertificateFactory
from lms.djangoapps.courseware.models import StudentModule
from lms.djangoapps.courseware.tests.factories import StudentModuleFactory
from openedx.core.djangoapps.content.course_overviews.tests.factories import CourseOverviewFactory

from course_payments.models import Order


class CourseLearnerDataTestCase(TestCase):
    # Saving a StudentModule also writes its history to this database.
    databases = {"default", "student_module_history"}

    def setUp(self):
        self.course = CourseOverviewFactory()
        self.other = CourseOverviewFactory()
        self.learner = UserFactory()
        self.staff = UserFactory(is_staff=True)
        for course in (self.course, self.other):
            CourseModeFactory(course_id=course.id, mode_slug="verified", min_price=499, currency="mxn")
            CourseEnrollmentFactory(user=self.learner, course_id=course.id, mode="verified")
            StudentModuleFactory(student=self.learner, course_id=course.id)
            GeneratedCertificateFactory(user=self.learner, course_id=course.id)
            CourseAccessRole.objects.create(user=self.staff, course_id=course.id, org=course.id.org, role="instructor")
        Order.objects.create(
            user=self.learner, course_key=self.course.id, amount=Decimal("499"), currency="mxn", status=Order.Status.PAID,
        )
        self.url = reverse("course_payments:course-learner-data", args=[str(self.course.id)])
        self.client = APIClient()

    def test_deletes_only_this_course_and_keeps_orders(self):
        self.client.force_authenticate(self.staff)
        response = self.client.delete(self.url)

        assert response.status_code == 200
        assert response.json()["deleted"]["enrollments"] == 1
        for model, field in (
            (CourseEnrollment, "course_id"),
            (StudentModule, "course_id"),
            (GeneratedCertificate, "course_id"),
            (CourseMode, "course_id"),
            (CourseAccessRole, "course_id"),
        ):
            assert not model.objects.filter(**{field: self.course.id}).exists(), model.__name__
            assert model.objects.filter(**{field: self.other.id}).exists(), model.__name__
        assert Order.objects.filter(course_key=self.course.id).count() == 1

    def test_requires_staff(self):
        self.client.force_authenticate(self.learner)
        assert self.client.delete(self.url).status_code == 403
        assert CourseEnrollment.objects.filter(course_id=self.course.id).exists()
