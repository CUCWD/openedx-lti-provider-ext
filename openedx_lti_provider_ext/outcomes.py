"""Use complete LTI result identifiers when sending grade updates."""

from functools import wraps
import logging

from requests.exceptions import RequestException


log = logging.getLogger("edx.lti_provider")


def _send_score_update(assignment, score):
    """Use platform request helpers while retaining error response details."""
    from lms.djangoapps.lti_provider import outcomes

    xml = outcomes.generate_replace_result_xml(
        assignment.lis_result_sourcedid, score
    )
    try:
        response = outcomes.sign_and_send_replace_result(assignment, xml)
    except RequestException:
        # failed to send result. 'response' is None, so more detail will be
        # logged at the end of the method.
        response = None
        log.exception("Outcome Service: Error when sending result. Assignment: %s", assignment.pk)

    # Requests makes HTTP 4xx/5xx responses falsey. Test against None so a
    # Canvas 422 response containing "Invalid sourcedid" is not lost as Unknown.
    # ---
    # If something went wrong, make sure that we have a complete log record.
    # That way we can manually fix things up on the campus system later if
    # necessary.
    if response is None or not outcomes.check_replace_result_response(response):
        log.error(
            "Outcome Service: Failed to update score on LTI consumer. "
            "Assignment: %s, User: %s, course: %s, usage: %s, score: %s, "
            "endpoint: %s, status: %s, request_id: %s, body: %s",
            assignment.pk,
            assignment.user,
            assignment.course_key,
            assignment.usage_key,
            score,
            assignment.outcome_service.lis_outcome_service_url,
            response.status_code if response is not None else "No response",
            response.headers.get("x-request-context-id", "Unknown") if response is not None else "Unknown",
            response.text if response is not None else "No response received",
        )


def install_send_score_update_override():
    """Install long-ID selection and diagnostic logging once."""
    # Import at installation time, after Django has loaded the application models.
    from lms.djangoapps.lti_provider import outcomes

    from .models import GradedAssignmentExtra

    original = outcomes.send_score_update
    # App initialization may run more than once. Keep a single wrapper so each
    # score update performs only one extra lookup and calls the sender once.
    if getattr(original, "_long_sourcedid_override", False):
        return

    @wraps(original)
    def send_score_update(assignment, score):
        # The core field holds at most 255 characters; the extra table preserves
        # the complete opaque ID `lis_result_sourcedid_long` supplied by the consuming LMS during launch.
        # Read it directly because assignment.extra may already be cached with
        # an older value (or cached as missing) on this assignment instance.
        long_sourcedid = GradedAssignmentExtra.objects.filter(
            gradedassignment_id=assignment.pk,
        ).values_list("lis_result_sourcedid_long", flat=True).first()
        if long_sourcedid:
            # Substitute before the original sender generates its replaceResult
            # XML. This also goes through the model's sourced-ID descriptor when
            # installed. Do not save the assignment: sending a grade should not
            # write the complete ID back into the limited core database column.
            assignment.lis_result_sourcedid = long_sourcedid
        # Missing rows and null/empty long IDs retain the existing assignment ID.
        # Keep the platform XML, signing, and response validation helpers, but
        # use our sender to log error bodies without the platform truthiness bug.
        return _send_score_update(assignment, score)

    send_score_update._long_sourcedid_override = True
    # Platform grade tasks call outcomes.send_score_update through this module,
    # so replacing the module attribute routes those calls through our wrapper.
    outcomes.send_score_update = send_score_update
