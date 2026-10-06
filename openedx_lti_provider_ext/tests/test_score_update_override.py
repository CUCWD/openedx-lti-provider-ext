"""Regression tests for selecting complete result IDs before XML generation."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from lms.djangoapps.lti_provider import outcomes
from lxml import etree
from requests import Response
from requests.exceptions import ConnectionError

from openedx_lti_provider_ext.models import GradedAssignmentExtra
from openedx_lti_provider_ext.outcomes import install_send_score_update_override
from openedx_lti_provider_ext.outcomes import _send_score_update


class ScoreUpdateOverrideTests(SimpleTestCase):
    """Exercise the wrapper with the platform XML generator and no HTTP calls."""

    def test_sourcedid_used_in_xml(self):
        """Prefer the long ID, retaining the original for missing or empty extras."""
        for long_id in ("long-id-" * 100, None, ""):
            with self.subTest(long_id=long_id):
                assignment = SimpleNamespace(pk=7917, lis_result_sourcedid="short-id")

                def original(assignment, score):
                    return outcomes.generate_replace_result_xml(assignment.lis_result_sourcedid, score)

                with patch(
                    "openedx_lti_provider_ext.outcomes._send_score_update", original
                ), patch.object(outcomes, "send_score_update", original), patch.object(
                    GradedAssignmentExtra.objects, "filter"
                ) as query:
                    query.return_value.values_list.return_value.first.return_value = long_id
                    install_send_score_update_override()
                    xml = outcomes.send_score_update(assignment, 1.0)

                root = etree.fromstring(xml)
                namespace = {"lti": "http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0"}
                self.assertEqual(root.find(".//lti:sourcedId", namespace).text, long_id or "short-id")
                self.assertEqual(root.find(".//lti:textString", namespace).text, "1.0")
                query.assert_called_once_with(gradedassignment_id=7917)

    def test_install_is_idempotent(self):
        """Repeated installation must not wrap the sender again."""
        def original(assignment, score):
            return None

        with patch.object(outcomes, "send_score_update", original):
            install_send_score_update_override()
            wrapped = outcomes.send_score_update
            install_send_score_update_override()
            self.assertIs(outcomes.send_score_update, wrapped)


class ScoreUpdateLoggingTests(SimpleTestCase):
    """Retain consumer errors even when Requests considers the response falsey."""

    def setUp(self):
        super().setUp()
        self.assignment = SimpleNamespace(
            pk=7917, user="learner", course_key="course", usage_key="block",
            lis_result_sourcedid="complete-id",
            outcome_service=SimpleNamespace(lis_outcome_service_url="https://lms.example/outcomes"),
        )

    def test_http_error_body_is_logged(self):
        response = Response()
        response.status_code = 422
        response._content = b"<imsx_description>Invalid sourcedid [EID_125440000000074506]</imsx_description>"
        response.headers["x-request-context-id"] = "canvas-request-id"
        with patch.object(outcomes, "sign_and_send_replace_result", return_value=response) as send:
            with self.assertLogs("edx.lti_provider", level="ERROR") as logs:
                _send_score_update(self.assignment, 1.0)
        send.assert_called_once()
        message = "\n".join(logs.output)
        for expected in ("422", "Invalid sourcedid", "EID_125440000000074506", "canvas-request-id", "7917"):
            self.assertIn(expected, message)
        self.assertNotIn("body: Unknown", message)

    def test_transport_error_is_logged(self):
        with patch.object(outcomes, "sign_and_send_replace_result", side_effect=ConnectionError("unreachable")):
            with self.assertLogs("edx.lti_provider", level="ERROR") as logs:
                _send_score_update(self.assignment, 1.0)
        message = "\n".join(logs.output)
        self.assertIn("unreachable", message)
        self.assertIn("No response received", message)

    def test_xml_failure_with_http_200_is_logged(self):
        response = Response()
        response.status_code = 200
        response._content = (
            b'<imsx_POXEnvelopeResponse xmlns="http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0">'
            b'<imsx_codeMajor>failure</imsx_codeMajor></imsx_POXEnvelopeResponse>'
        )
        with patch.object(outcomes, "sign_and_send_replace_result", return_value=response):
            with self.assertLogs("edx.lti_provider", level="ERROR") as logs:
                _send_score_update(self.assignment, 1.0)
        self.assertIn(response.text, "\n".join(logs.output))

    def test_success_does_not_log_error(self):
        response = Response()
        response.status_code = 200
        response._content = (
            b'<imsx_POXEnvelopeResponse xmlns="http://www.imsglobal.org/services/ltiv1p1/xsd/imsoms_v1p0">'
            b'<imsx_codeMajor>success</imsx_codeMajor></imsx_POXEnvelopeResponse>'
        )
        with patch.object(outcomes, "sign_and_send_replace_result", return_value=response):
            with self.assertNoLogs("edx.lti_provider", level="ERROR"):
                _send_score_update(self.assignment, 1.0)
