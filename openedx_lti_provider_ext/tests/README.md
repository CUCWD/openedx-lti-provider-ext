# Testing Procedure With Django Plugin Extension
Need to following these directions when testing this application. The tests were brought over from the existing `edx-platform/lms/djangoapps/lti_provider` application with minor tweaks initially for changes made within the `./test_outcomes.py` for adding the larger text field value for `lis_result_sourcedid` > 256 character limit.

## Ensure the static assets are built for the test run.
This helps with the tests that check for presence of webpack-built assets (e.g. views.py).
```
STATIC_ROOT_LMS="$PWD/test_root/staticfiles" STATIC_ROOT_CMS="$STATIC_ROOT_LMS/studio" npm run webpack
```

## Update the `tutor-env` to include the `openedx_lti_provider_ext` application.
Testing the application with this new Django app ext, you will need to make sure that it's installed. I'm not sure if there is a tutor patch for this, so I just manually added this to the tutor environment.
```
# tutor-env/env/apps/openedx/settings/lms/test.py

from lms.envs.test import *

# Fix MongoDb connection credentials
DOC_STORE_CONFIG["user"] = None
DOC_STORE_CONFIG["password"] = None

# Added custom code here.
# --------------------------------------
####################### LTI Provider Settings #######################
INSTALLED_APPS.append('openedx_lti_provider_ext')
```

## Example command to run all tests within the openedx-lti-provider-ext app.
```
PYTHONPATH="$PWD/src:$PYTHONPATH" DJANGO_SETTINGS_MODULE="lms.envs.tutor.test" pytest ../src/openedx-lti-provider-ext/openedx_lti_provider_ext/tests/ -q --nomigrations
```

## Example command to run a specific test within the openedx-lti-provider-ext app (e.g. test_outcomes.py)
```
PYTHONPATH="$PWD/src:$PYTHONPATH" DJANGO_SETTINGS_MODULE="lms.envs.tutor.test" pytest ../src/openedx-lti-provider-ext/openedx_lti_provider_ext/tests/test_outcomes.py::StoreOutcomeParametersTest::test_graded_assignment_created -q --nomigrations
```