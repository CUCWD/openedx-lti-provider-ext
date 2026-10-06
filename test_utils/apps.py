"""Standalone app configuration without platform startup signals."""

from django.apps import AppConfig


class LtiProviderTestConfig(AppConfig):
    """Register synthetic models without importing platform signals."""

    name = "lms.djangoapps.lti_provider"
    label = "lti_provider"
