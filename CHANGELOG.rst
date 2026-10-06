Change Log
##########

..
   All enhancements and patches to openedx_lti_provider_ext will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).

.. There should always be an "Unreleased" section for changes pending release.

Unreleased
**********

*

0.1.5 - 2026-10-06
******************

Fixed
=====

* Use the saved ``GradedAssignmentExtra.lis_result_sourcedid_long`` value before
  ``send_score_update`` generates grade passback XML, avoiding truncated result
  identifiers when a complete value is available. Retain the existing identifier
  when the extra record is missing or its long value is empty.
* Install the score update override once during application initialization when
  LTI Provider is enabled, preserving the platform's XML generation, OAuth
  signing, HTTP request, and response validation helpers.
* Preserve HTTP error response bodies in grade passback logs by checking whether
  a response is ``None`` instead of testing its truthiness. This addresses the
  unhelpful ``body: Unknown`` log observed with Canvas's HTTP 422 Unprocessable
  Entity response containing ``Invalid sourcedid [EID_125440000000074506]``.
  Error logs now include the assignment ID, endpoint, HTTP status, and Canvas
  request context ID to support investigation without manual requests.

Added
=====

* Regression tests for complete result identifiers in generated XML, fallback
  behavior, repeated override installation, HTTP error body logging, transport
  failures, and LTI success/failure responses.

0.1.1 - 2025-12-10
**********************************************

Added
=====

* First release on PyPI.
