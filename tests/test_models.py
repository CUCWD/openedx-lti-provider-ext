"""Standalone checks for the real extension model with a synthetic parent model."""

import pytest
from lms.djangoapps.lti_provider.models import GradedAssignment

from openedx_lti_provider_ext.models import GradedAssignmentExtra


@pytest.mark.django_db
def test_long_result_id_round_trip_and_cascade():
    """Retain a complete ID and delete it with its assignment."""
    result_id = "opaque-result-id-" * 64
    assignment = GradedAssignment.objects.create(lis_result_sourcedid=result_id[:255])
    extra = GradedAssignmentExtra.objects.create(
        gradedassignment=assignment,
        lis_result_sourcedid_long=result_id,
    )
    extra.refresh_from_db()
    assert extra.lis_result_sourcedid_long == result_id
    assignment.delete()
    assert not GradedAssignmentExtra.objects.exists()
