"""Minimal database boundary for standalone extension checks, not integration tests."""

from django.db import models


class GradedAssignment(models.Model):
    """Synthetic assignment containing no real learner data.

    .. no_pii:
    """

    lis_result_sourcedid = models.CharField(max_length=255)

    class Meta:
        app_label = "lti_provider"


class OutcomeService(models.Model):
    """Synthetic outcome endpoint containing no real learner data.

    .. no_pii:
    """

    lis_outcome_service_url = models.URLField()

    class Meta:
        app_label = "lti_provider"
