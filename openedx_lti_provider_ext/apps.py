"""
openedx_lti_provider_ext Django application initialization.
"""
from django.conf import settings
from edx_django_utils.plugins import PluginURLs, PluginSettings
from django.apps import AppConfig
from waffle import switch_is_active
import logging

from .views import _wrap

logger = logging.getLogger(__name__)

class OpenedxLtiProviderExtConfig(AppConfig):
    """
    Configuration for the openedx_lti_provider_ext Django application.
    """

    name = 'openedx_lti_provider_ext'
    label = "openedx_lti_provider_ext"
    verbose_name = "LTI Provider Extensions"

    def ready(self):
        """
        Application initialization code.
        """
        logger.info("openedx_lti_provider_ext application is ready.")

        if settings.FEATURES.get('ENABLE_LTI_PROVIDER'):
            # Avoid double-patching on autoreload
            if getattr(self, "_patched", False):
                return
            
            # Define a wrapper around the original lti_launch view
            # This will allow us to add custom behavior after the original view is executed
            # without modifying the original source code.
            # This is useful for adding logging, error handling, or other side effects.
            # We only want to do this if the LTI Provider feature is enabled.

            # Useful to enroll the user in the course if they have the appropriate role.
            # This is helpful for reporting purposes for enrollment but LTI users doing 
            # typically get added into the course when accessing the lti_launch URL.
            # We do this after the original launch so that we don't interfere with any
            # errors that might occur during the launch itself.
            from lms.djangoapps.lti_provider import views as lti_views
            lti_views.lti_launch = _wrap(lti_views.lti_launch)
            
            self._patched = True
            
