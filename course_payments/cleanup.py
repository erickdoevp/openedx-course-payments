"""
LMS half of deleting a course: everything learners and staff left behind.

The course content itself lives in the modulestore and is deleted by Studio
(see ``studio.py``). Orders and Stripe events are kept on purpose: they are
the payment history and only reference the course id as text.
"""
from django.db import transaction

from common.djangoapps.course_modes.models import CourseMode
from common.djangoapps.student.models import CourseAccessRole, CourseEnrollment, FBEEnrollmentExclusion
from lms.djangoapps.certificates.models import GeneratedCertificate
from lms.djangoapps.courseware.models import StudentModule
from lms.djangoapps.grades.models import PersistentCourseGrade, PersistentSubsectionGrade
from lms.djangoapps.support.models import CourseResetAudit


def delete_course_learner_data(course_key):
    """
    Delete enrollments, progress, grades, certificates, course modes (the
    price) and course roles. Returns how many rows of each kind went away.
    """
    with transaction.atomic():
        enrollments = CourseEnrollment.objects.filter(course_id=course_key)
        # Both point at enrollments with on_delete=DO_NOTHING: the database
        # refuses to delete an enrollment they still reference.
        FBEEnrollmentExclusion.objects.filter(enrollment__in=enrollments).delete()
        CourseResetAudit.objects.filter(course_enrollment__in=enrollments).delete()

        deleted = {}
        for name, queryset in (
            ("enrollments", enrollments),
            ("progress", StudentModule.objects.filter(course_id=course_key)),
            ("subsection_grades", PersistentSubsectionGrade.objects.filter(course_id=course_key)),
            ("course_grades", PersistentCourseGrade.objects.filter(course_id=course_key)),
            ("certificates", GeneratedCertificate.objects.filter(course_id=course_key)),
            ("course_modes", CourseMode.objects.filter(course_id=course_key)),
            ("roles", CourseAccessRole.objects.filter(course_id=course_key)),
        ):
            deleted[name] = queryset.count()
            queryset.delete()
    return deleted
