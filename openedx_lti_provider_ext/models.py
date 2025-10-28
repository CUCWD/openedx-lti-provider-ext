"""
Database models for openedx_lti_provider_ext.
"""

from django.db import models
from lms.djangoapps.lti_provider.models import GradedAssignment

class GradedAssignmentExtra(models.Model):
    # One-to-one relation to the LMS GradedAssignment: this attaches extra fields
    # to the GradedAssignment row; if the GradedAssignment is deleted, the
    # corresponding GradedAssignmentExtra row is also deleted.
    gradedassignment = models.OneToOneField(
        GradedAssignment,
        on_delete=models.CASCADE,
        related_name="extra",
        primary_key=True,
    )
    # Long version of lis_result_sourcedid with no 255 limit
    # Handles longer lis_result_sourcedid values from some LMSs that
    # the original GradedAssignment model cannot store.
    lis_result_sourcedid_long = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "lti_provider_gradedassignment_extra"
