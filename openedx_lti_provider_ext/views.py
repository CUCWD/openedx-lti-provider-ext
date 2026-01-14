from django.http import HttpRequest, HttpResponse, HttpResponseForbidden, Http404
from django.views.decorators.csrf import csrf_exempt
from functools import wraps

# Wrapper function to add custom behavior around the original LTI launch view.
# This allows us to add custom behavior after the original view is executed
# without modifying the original source code.
def _wrap(original_function):
    from lms.djangoapps.lti_provider import views as lti_views
    original = lti_views.lti_launch

    """
    Wrapper function to add custom behavior around the original LTI launch view.
    """
    @csrf_exempt                 # <-- critical
    @wraps(original)             # keep name/docs for debugging
    def _custom_lti_launch(request: HttpRequest, *args, **kwargs) -> HttpResponse:

        from django.http import Http404, HttpResponseBadRequest

        # Make sure to import these view dependencies after the LMS is fully loaded
        # You will receive "Apps aren't loaded yet." errors otherwise.
        from lms.djangoapps.lti_provider.views import (
            get_optional_parameters, get_required_parameters,
            parse_course_and_usage_keys
        )
        from common.djangoapps.student.models import CourseEnrollment
        from common.djangoapps.course_modes.models import CourseMode
        from opaque_keys import InvalidKeyError

        import logging

        log = logging.getLogger(__name__)

        # --- your extra commands BEFORE ---
        # e.g. logging, querystring/header munging, feature flags, etc.
        # do_something_pre(request)
        log.info("Custom LTI Launch Invoked")

        # Delegate to the original LTI Launch
        try:
            resp = original_function(request, *args, **kwargs)

            if resp.status_code != 200:
                # Could be a 403 if the LTI consumer is not recognized (e.g. signature failed).
                log.error(f"Original LTI Launch failed with status {resp.status_code}") 

                # Pass back the original response if it wasn't successful, so the user
                # receives the message.
                return resp  # Re-raise the exception after logging it
        except Exception as e:
            # This could be an additional error like Milestone not passing (e.g. Course Pre-reqs not met).
            # We want to log the error and re-raise it so that the user sees the
            # original error message.
            log.error(f"Error during original LTI Launch: {type(e).__name__}: {e}")
            raise  # Re-raise the exception after logging it

        # If we get here, the original LTI launch was successful (200 OK).
        # The rest of the code below tries to enroll the logged-in user in the course
        # if they have the appropriate role.
        # This is helpful for reporting purposes for enrollment but LTI users doing 
        # typically get added into the course when accessing the lti_launch URL.
        # We do this after the original launch so that we don't interfere with any
        # errors that might occur during the launch itself.
        if resp.status_code == 200:         
            # Check the LTI parameters, and return 400 if any required parameters are
            # missing
            params = get_required_parameters(request.POST)
            if not params:
                log.error("Missing required LTI launch parameters.")
                return HttpResponseBadRequest()
            params.update(get_optional_parameters(request.POST))

            # Add the course and usage keys to the parameters array
            course_id = kwargs.get('course_id')
            usage_id = kwargs.get('usage_id')

            try:
                course_key, usage_key = parse_course_and_usage_keys(course_id, usage_id)
            except InvalidKeyError:
                log.error(
                    'Invalid course key %s or usage key %s from request %s',
                    course_id,
                    usage_id,
                    request
                )
                raise Http404()  # lint-amnesty, pylint: disable=raise-missing-from
            params['course_key'] = course_key
            params['usage_key'] = usage_key

            # This assumes that you call this method when the user has already authenticated and has `Learner` or `Instructor` rights.
            # Using `honor` mode because we need to issue certificates of completion.
            # Include `Instructor` as well to auto-enroll instructors if needed.
            # roles = params.get('roles') or []
            # log.info("lti_launch roles %s", roles)
            # if ("Learner" in roles) or ("Instructor" in roles):
            #     CourseEnrollment.enroll(request.user, course_key, mode=CourseMode.HONOR)
            handleUserByRole(request, params)

        log.info(f"Custom LTI Launch Completed")
        return resp
    
    if not getattr(lti_views, "_lti_launch_patched", False):
        lti_views.lti_launch = _custom_lti_launch
        lti_views._lti_launch_patched = True

    return _custom_lti_launch

def handleUserByRole(request, params):
    ''' 
    Handle user enrollment based on LTI roles passed in with the launch.
    As mentioned by the https://www.imsglobal.org/spec/lti/v1p3/#users-and-roles it looks like
    typical roles are:
    "urn:lti:instrole:ims/lis/Administrator,Administrator,
     urn:lti:instrole:ims/lis/ContentDeveloper,ContentDeveloper,
     urn:lti:instrole:ims/lis/Faculty,Faculty,
     urn:lti:instrole:ims/lis/Member,Member,
     urn:lti:instrole:ims/lis/Instructor,Instructor,
     urn:lti:instrole:ims/lis/Staff,Staff,
     urn:lti:instrole:ims/lis/TeachingAssistant,TeachingAssistant,
     urn:lti:instrole:ims/lis/Learner,Learner,
     urn:lti:instrole:ims/lis/None,None"
    1. We will enroll users with the "Learner", "Instructor" or "Administrator" roles.
    2. We will enroll them in "honor" course mode so that they can earn a certificate of completion.
    3. We will not unenroll users if they are missing the role on a subsequent launch.
    4. We will not demote users if they are instructors.
    5. We will not change their enrollment mode if they are already enrolled.

    request - Includes the user object
    params - Includes the LTI launch parameters including 'roles' and 'course_key'
     - 'roles' is a list of roles assigned to the user
     - 'course_key' is the course to enroll the user in
    '''
    from common.djangoapps.student.models import CourseEnrollment
    from common.djangoapps.student.roles import CourseStaffRole, CourseInstructorRole
    from common.djangoapps.course_modes.models import CourseMode

    import logging

    log = logging.getLogger(__name__)

    # Convert all roles to lowercase for case-insensitive comparison and 
    # handle the case where roles is a single string or a list of strings
    # e.g. "Learner" or ["Learner", "Instructor"] or
    # ["urn:lti:instrole:ims/lis/Faculty","Faculty",
    #  "urn:lti:instrole:ims/lis/Member","Member",
    #  "urn:lti:instrole:ims/lis/Instructor","Instructor",
    #  "urn:lti:instrole:ims/lis/Staff","Staff"]
    roles = params.get('roles')
    if isinstance(roles, (list, tuple, set)):
        roles_lower = [str(role).lower() for role in roles]
    elif isinstance(roles, str):
        roles_lower = [str(role).strip().lower() for role in roles.split(',')]
    else:
        roles_lower = []

    # Use a dictionary as a "switch" to map roles to specific functions or actions
    # Each function handles enrollment and any other role-specific logic
    # At this time we don't need to do anything special for each role, however, we define
    # separate functions in case we want to add role-specific logic in the future.

    def _handle_staff():
        _handle_course_enrollment()

        # Add staff-specific role logic here
        # e.g. grant additional permissions, etc.

        course_key = params.get('course_key')
        if not course_key:
            return  # No course key provided, nothing to do
        user = request.user

        # Enroll the user as an instructor role if they are already enrolled in the course.
        if CourseEnrollment.is_enrolled(user, course_key):
            CourseStaffRole(course_key).add_users(user)
    
    def _handle_instructor():
        _handle_course_enrollment()

        # Add instructor-specific role logic here
        # e.g. grant additional permissions, etc.
        
        course_key = params.get('course_key')
        if not course_key:
            return  # No course key provided, nothing to do
        user = request.user

        # Enroll the user as an instructor role if they are already enrolled in the course.
        if CourseEnrollment.is_enrolled(user, course_key):
            CourseInstructorRole(course_key).add_users(user)
        
    def _handle_learner():
        _handle_course_enrollment()

        # Add learner-specific logic here
        # e.g. restrict permissions, etc.
        # We don't need to do anything special for learners at this time.

    def _handle_course_enrollment():
        '''
        Enroll the user in the course with 'honor' mode if they are not already enrolled.
        This course mode will allow them to earn a certificate of completion.
        At this point we know the user has a role that requires enrollment.
        '''        
        from django.conf import settings
        from django.core.exceptions import PermissionDenied
        from django.http import HttpResponseForbidden
        from common.djangoapps.edxmako.shortcuts import render_to_response
        from lms.djangoapps.lti_provider.models import LtiConsumer
        from lms.djangoapps.lti_provider.users import authenticate_lti_user

        course_key = params.get('course_key')
        if not course_key:
            return  # No course key provided, nothing to do
        user = request.user

        # Get the consumer information from either the instance GUID or the consumer
        # key
        try:
            lti_consumer = LtiConsumer.get_or_supplement(
                params.get('tool_consumer_instance_guid', None),
                params['oauth_consumer_key']
            )
        except LtiConsumer.DoesNotExist:
            return HttpResponseForbidden()
        
        # Create an edX account if the user identifed by the LTI launch doesn't have
        # one already, and log the edX account into the platform.
        # We enable LTI Provider "require user account" to ensure that the user
        # is linked to the LTI identity and is already created before we get here.
        try:
            authenticate_lti_user(request, params['user_id'], lti_consumer)
        except PermissionDenied:
            request.session.flush()
            context = {
                "login_link": request.build_absolute_uri(settings.LOGIN_URL),
                "allow_iframing": True,
                "disable_header": True,
                "disable_footer": True,
            }
            return render_to_response("lti_provider/user-auth-error.html", context)

        if not user or not user.is_authenticated:
            return  # No authenticated user, nothing to do, Anonymous users cannot be enrolled
        if CourseEnrollment.is_enrolled(user, course_key):
            return  # User is already enrolled, nothing to do
        else:
            CourseEnrollment.enroll(user, course_key, mode=CourseMode.HONOR)
            log.info(f"Enrolled user {user.username} in course {course_key} with honor mode.")
        
    # Define actions for each role.
    # https://www.imsglobal.org/specs/ltiv1p0/implementation-guide (Appendix A.2 Role Vocabularies)
    actions = {
        # Administrators
        # -------------------------------------------
        'administrator': _handle_instructor,
        'urn:lti:role:ims/lis/administrator': _handle_instructor,
        'urn:lti:role:ims/lis/administrator/administrator': _handle_instructor,
        'urn:lti:role:ims/lis/administrator/support': _handle_instructor,
        'urn:lti:role:ims/lis/administrator/externaldeveloper': _handle_instructor,
        'urn:lti:role:ims/lis/administrator/systemadministrator': _handle_instructor,
        'urn:lti:role:ims/lis/administrator/externalsystemadministrator': _handle_instructor,
        'urn:lti:role:ims/lis/administrator/externalsupport': _handle_instructor,

        # A person with institution-level management or oversight responsibilities (LMS administrators, Deans, Department heads, System owners)
        'urn:lti:instrole:ims/lis/administrator': _handle_instructor,
        
        # Instructors
        # -------------------------------------------
        'instructor': _handle_instructor,
        'urn:lti:role:ims/lis/instructor': _handle_instructor,
        'urn:lti:role:ims/lis/instructor/primaryinstructor': _handle_instructor,
        'urn:lti:role:ims/lis/instructor/lecturer': _handle_instructor,
        'urn:lti:role:ims/lis/instructor/guestinstructor': _handle_instructor,
        'urn:lti:role:ims/lis/instructor/externalinstructor': _handle_instructor,

        'urn:lti:role:ims/lis/teachingassistant': _handle_staff,
        'urn:lti:role:ims/lis/teachingassistant/teachingassistant': _handle_staff,
        'urn:lti:role:ims/lis/teachingassistant/teachingassistantsection': _handle_staff,
        'urn:lti:role:ims/lis/teachingassistant/teachingassistantsectionassociation': _handle_staff,
        'urn:lti:role:ims/lis/teachingassistant/teachingassistantoffering': _handle_staff,
        'urn:lti:role:ims/lis/teachingassistant/teachingassistanttemplate': _handle_staff,
        'urn:lti:role:ims/lis/teachingassistant/teachingassistantgroup': _handle_staff,
        'urn:lti:role:ims/lis/teachingassistant/grader': _handle_staff,

        # Deprecated roles from LTI 1.1 launch
        'faculty': _handle_instructor,
        'urn:lti:role:ims/lis/faculty': _handle_instructor,
        'staff': _handle_staff,
        'urn:lti:role:ims/lis/staff': _handle_staff,

        # Learners
        # -------------------------------------------
        'learner': _handle_learner,
        'urn:lti:role:ims/lis/learner': _handle_learner,
        'urn:lti:role:ims/lis/learner/learner': _handle_learner,
        'urn:lti:role:ims/lis/learner/noncreditlearner': _handle_learner,
        'urn:lti:role:ims/lis/learner/guestlearner': _handle_learner,
        'urn:lti:role:ims/lis/learner/externallearner': _handle_learner,
        'urn:lti:role:ims/lis/learner/instructor': _handle_learner,

        # Deprecated roles from LTI 1.1 launch
        'student': _handle_learner,
        'urn:lti:role:ims/lis/student': _handle_learner,   
    }
        
    # Check for each target role in the list and execute the corresponding action
    # If the role is not found, do nothing for the user.
    for role_to_check in actions:
        if role_to_check in roles_lower:
            log.info(f"User has {role_to_check} role from LTI Consumer.")
            actions[role_to_check]()

