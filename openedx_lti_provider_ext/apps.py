"""
openedx_lti_provider_ext Django application initialization.
"""
from django.conf import settings
from edx_django_utils.plugins import PluginURLs, PluginSettings
from django.apps import AppConfig
from waffle import switch_is_active
import logging

from .views import _wrap

logger = logging.getLogger(__name__)

class OpenedxLtiProviderExtConfig(AppConfig):
    """
    Configuration for the openedx_lti_provider_ext Django application.
    """

    name = 'openedx_lti_provider_ext'
    label = "openedx_lti_provider_ext"
    verbose_name = "LTI Provider Extensions"

    # simple guard so we don't double-install if Django reloads apps
    _patched = False

    def ready(self):
        """
        Application initialization code.
        """
        # Avoid double-patching on autoreload
        if self._patched:
            return
        
        logger.info("openedx_lti_provider_ext application is ready.")

        if settings.FEATURES.get('ENABLE_LTI_PROVIDER'): 
            # Wrap the lti_launch view to add custom behavior for enrollment, logging, etc.           
            self._override_lti_launch_view()

            # Install the lis_result_sourcedid proxy to support long values via sidecar table.
            self._install_lis_result_sourcedid_proxy()
            
        self._patched = True

    def _override_lti_launch_view(self):
        """
        Override the lti_launch view to add custom behavior.
        """
        # Define a wrapper around the original lti_launch view
        # This will allow us to add custom behavior after the original view is executed
        # without modifying the original source code.
        # This is useful for adding logging, error handling, or other side effects.
        # We only want to do this if the LTI Provider feature is enabled.

        # Useful to enroll the user in the course if they have the appropriate role.
        # This is helpful for reporting purposes for enrollment but LTI users doing 
        # typically get added into the course when accessing the lti_launch URL.
        # We do this after the original launch so that we don't interfere with any
        # errors that might occur during the launch itself.
        from lms.djangoapps.lti_provider import views as lti_views
        lti_views.lti_launch = _wrap(lti_views.lti_launch)

    def _install_lis_result_sourcedid_proxy(self):
        """
        Install a descriptor on lti_provider.GradedAssignment.lis_result_sourcedid
        that:
          - GET: returns sidecar Extra.lis_result_sourcedid_long when present,
                 else falls back to the original (255-char) field value.
          - SET: writes the long value to the sidecar (deferred until GA has a PK),
                 and stores a truncated (<=255) copy into the core column for
                 compatibility with forms/validators/admin.
        Also connects a post_save signal to persist deferred sidecar writes.
        """

        from django.db.models.signals import post_save
        from lms.djangoapps.lti_provider.models import GradedAssignment
        from .models import GradedAssignmentExtra

        # If someone else already swapped this, don't override again.
        if "lis_result_sourcedid" not in GradedAssignment.__dict__:
            return

        # Preserve the original class descriptor for lis_result_sourcedid so the proxy
        # can delegate to the original behavior; use getattr to retrieve the descriptor
        # and bail out if we cannot obtain it to avoid raising exceptions.
        try:
            orig_descr = getattr(GradedAssignment, "lis_result_sourcedid")
        except Exception:
            return
        setattr(GradedAssignment, "_orig_lis_result_sourcedid_descr", orig_descr)

        class _SourcedidProxy:
            """
            Descriptor that proxies lis_result_sourcedid to the sidecar long field on read,
            and mirrors writes into both sidecar (long) and core (truncated) fields.
            """

            # Any GradedAssignment.lis_result_sourcedid now yields the long sidecar value (if set), 
            # so we don’t have to modify call for this field elsewhere in the codebase.
            # Filters/queries: ORM filters like .filter(lis_result_sourcedid__icontains="abc") still
            # operate on the core 255-char column. If you need searching on the long value, add 
            # filters on GradedAssignmentExtra (e.g., .filter(extra__lis_result_sourcedid_long__icontains=...)).
            def __get__(self, instance, owner=None):
                if instance is None:
                    return self
                try:
                    # Attempt to read from sidecar first grabbing the long version for lis_result_sourcedid.
                    extra = getattr(instance, "extra", None)
                    if extra and extra.lis_result_sourcedid_long:
                        return extra.lis_result_sourcedid_long
                except Exception:
                    # fall through to original value if sidecar access fails
                    pass
                return orig_descr.__get__(instance, owner)

            # GradedAssignment.lis_result_sourcedid = <very long> stores the long value in the sidecar and
            # a truncated copy in the core column, keeping admin/forms happy.
            def __set__(self, instance, value):
                # Always keep a truncated copy in the core CharField (<=255)
                # for compatibility with existing code that expects that field.
                # Decided not to use a SHA 256 char field because of potential ORM filtering on original value.
                if isinstance(value, str) and len(value) > 255:
                    trunc = value[:255]
                else:
                    trunc = value
                # Write directly into the instance dict to avoid invoking the
                # descriptor again (which would recurse into __set__).
                instance.__dict__['lis_result_sourcedid'] = trunc

                # Handle long/sidecar value
                # ------------------------------------------------------------

                # If value is None, clear sidecar field if it exists and set up a deferred extra save.
                if value is None:
                    try:
                        extra = getattr(instance, "extra", None)
                        if extra:
                            extra.lis_result_sourcedid_long = None
                            object.__setattr__(instance, "_ga__needs_extra_save", True)
                    except Exception:
                        pass
                    return

                # Otherwise, setup a deferred extra write for long value to sidecar (creating if necessary).
                try:
                    extra = getattr(instance, "extra", None)
                except Exception:
                    extra = None

                # If the GradedAssignment doesn't yet have a PK, we can't create the sidecar row yet.
                # Defer writing until after save (using post_save signal handler).
                # Set a flag so the signal handler knows to write the long value later.
                if extra is None:
                    # Defer writing value until after GradedAssignment has a PK
                    object.__setattr__(instance, "_ga__pending_long_sourcedid", value)
                else:
                    extra.lis_result_sourcedid_long = value
                    object.__setattr__(instance, "_ga__needs_extra_save", True)

        # Install proxy on the model class
        setattr(GradedAssignment, "lis_result_sourcedid", _SourcedidProxy())

        # Persist deferred sidecar writes after GradedAssignment is saved (when it has a PK)
        def _sync_sidecar(sender, instance, created, **kwargs):
            pending = getattr(instance, "_ga__pending_long_sourcedid", None)
            needs_save = getattr(instance, "_ga__needs_extra_save", False)
            if pending is not None or needs_save:
                extra, _ = GradedAssignmentExtra.objects.get_or_create(gradedassignment=instance)

                # Write pending long sourcedid if present
                if pending is not None:
                    extra.lis_result_sourcedid_long = pending
                    object.__setattr__(instance, "_ga__pending_long_sourcedid", None)
                if needs_save:
                    object.__setattr__(instance, "_ga__needs_extra_save", False)

                # Save the sidecar row when we have updates for it
                extra.save(update_fields=["lis_result_sourcedid_long"])

        # Connect the post_save signal to sync sidecar writes
        post_save.connect(_sync_sidecar, sender=GradedAssignment, weak=False)

