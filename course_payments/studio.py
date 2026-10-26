"""
Studio half of deleting a course: its content. Runs in the CMS, which owns the
modulestore; learner data is deleted by the LMS (see ``cleanup.py``).
"""
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from cms.djangoapps.contentstore.utils import delete_course
from xmodule.contentstore.django import contentstore
from xmodule.modulestore.django import modulestore


class StudioCourseView(APIView):
    """
    DELETE /campus/api/v1/courses/{course_id}/  (Studio)

    Staff only. Same as ``./manage.py cms delete_course --remove-assets``:
    deletes the content, its files (images, handouts) and the staff and
    instructor roles. The ``course_deleted`` signal then removes the course
    overview and the search index entries.
    """

    authentication_classes = (JwtAuthentication, SessionAuthenticationAllowInactiveUser)
    permission_classes = (permissions.IsAdminUser,)

    def delete(self, request, course_id):
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            return Response({"detail": "Invalid course id."}, status=400)
        if not modulestore().get_course(course_key):
            return Response({"detail": "Course not found."}, status=404)

        delete_course(course_key, request.user.id)
        contentstore().delete_all_course_assets(course_key)
        return Response(status=204)
