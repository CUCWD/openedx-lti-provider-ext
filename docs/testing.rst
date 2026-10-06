.. _chapter-testing:

Testing
#######

Standalone CI and platform integration
======================================

The GitHub Actions Django jobs use synthetic LMS models from
``test_utils/platform_stubs`` with the real extension model. The score update
regression tests load the real platform outcome helpers from a pinned checkout
specified in ``.github/workflows/ci.yml``. Set its location when running locally:

.. code-block:: bash

    export LTI_TEST_PLATFORM_ROOT=/absolute/path/to/openedx-platform
    tox -e django42,django52,pii_check,docs

The standalone settings disable LTI startup hooks and platform migrations.
These checks cover long-ID storage and deletion, ID selection, XML generation,
and response logging. They do not validate platform migrations, launch views,
Celery startup, or the sourced-ID descriptor against the full platform.
The test-only modules are not included in the extension wheel.

The remaining tests under ``openedx_lti_provider_ext/tests`` require an LMS test
container with this extension enabled. Follow that directory's ``README.md``
for full platform integration testing. Explicit test paths override the
standalone pytest selection.

The PII scanner inspects the real extension model. Its opaque external result
identifier is classified in ``.annotation_safe_list.yml``; it is not marked as
containing no PII. Synthetic models contain no real learner data.

Lint baseline
=============

The quality job runs pylint, pycodestyle, pydocstyle, and isort. Existing findings
are recorded in ``.quality-baseline.json`` to preserve application source during
this CI repair. New diagnostics or increased occurrence counts fail the job;
import-order exceptions are tied to each file's content hash. Tool crashes fail
the job rather than being accepted as baseline findings.

To refresh the baseline after reviewing the changes, run the following with the
quality environment activated and ``DJANGO_SETTINGS_MODULE=test_settings``:

.. code-block:: bash

    python test_utils/check_quality.py --update-baseline

Review and commit the resulting diff. CI never updates the baseline itself.

Other checks
============

openedx-lti-provider-ext has an assortment of test cases and code quality
checks to catch potential problems during development.  To run them all in the
version of Python you chose for your virtualenv:

.. code-block:: bash

    $ make validate

To run just the unit tests:

.. code-block:: bash

    $ make test

To run just the unit tests and check diff coverage

.. code-block:: bash

    $ make diff_cover

To run just the code quality checks:

.. code-block:: bash

    $ make quality

To run the unit tests under every supported Python version and the code
quality checks:

.. code-block:: bash

    $ make test-all

To generate and open an HTML report of how much of the code is covered by
test cases:

.. code-block:: bash

    $ make coverage
