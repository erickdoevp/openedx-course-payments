from django.conf import settings
from django.urls import re_path

from .studio import StudioCourseView

# Mounted under /campus/ in Studio by the plugin config in apps.py.
urlpatterns = [
    re_path(
        rf"^api/v1/courses/{settings.COURSE_ID_PATTERN}/$",
        StudioCourseView.as_view(),
        name="studio-course",
    ),
]
