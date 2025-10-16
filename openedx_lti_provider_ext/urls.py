"""
URLs for openedx_lti_provider_ext.
"""
from django.conf import settings
from django.urls import path, re_path  # pylint: disable=unused-import
from django.views.generic import TemplateView  # pylint: disable=unused-import

from . import views

# At the moment we're not overriding the lti_launch view, but if we did, it might look like this:
# if settings.FEATURES.get('ENABLE_LTI_PROVIDER'):
    # urlpatterns = [
    #     # TODO: Fill in URL patterns and views here.
    #     re_path(r'', TemplateView.as_view(template_name="openedx_lti_provider_ext/base.html")),
    # ]
    # urlpatterns = [
    #     path("launch", views.custom_lti_launch, name="custom_lti_launch"),
    # ]
    # re_path(
    #     r'^courses/{course_id}/{usage_id}$'.format(
    #         course_id=settings.COURSE_ID_PATTERN,
    #         usage_id=settings.USAGE_ID_PATTERN
    #     ),
    #     views.custom_lti_launch, name="custom_lti_launch"),
