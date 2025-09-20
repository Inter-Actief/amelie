import logging

from django.conf import settings

from amelie.claudia.tasks import verify_object

logger = logging.getLogger(__name__)


# clau.py
# Claudia-data-database things
# authors b.c.peschier & m.kooijman

# Source: https://stackoverflow.com/questions/452969/does-python-have-an-equivalent-to-java-class-forname#answer-452981
def _get_class(cls):
    """ Get a class by name """
    parts = cls.split('.')
    module = ".".join(parts[:-1])
    m = __import__(module)
    for comp in parts[1:]:
        m = getattr(m, comp)
    return m


def wrap_call_plugins(hook):
    """
    Generate a function that can be called to run all plugins that respond to a given hook.
    Caution: voodoo!
    :param hook: The hook to generate the function for
    :type hook: str
    :return: Function that will run all plugins with the given hook.
    :rtype: callable
    """

    def call_plugins(self, *args, **kwargs):
        """
        Calls plugins listening on a predefined hook.
        :param self: CoproManager instance
        :type self: CoproManager
        """
        logger.debug("Calling plugins for hook %s" % hook)
        for plugin in self.plugins:
            try:
                # Find the hook method in the current plugin
                f = getattr(plugin, hook)
            except AttributeError:
                # The current plugin does not provide the hook.
                continue
            logger.debug("Calling %s::%s" % (plugin.__class__.__name__, hook))
            try:
                # Call the actual hook
                f(self, *args, **kwargs)
            except Exception as e:
                logger.exception("Plugin %s hook %s raised exception: %s" % (plugin.__class__.__name__, hook, str(e)))
                if settings.CLAUDIA_STOP_ON_ERROR:
                    raise

    return call_plugins


class Claudia:
    """
    Claudia
    The Inter-Actief data synchronizer
    """
    _instance = None

    def __init__(self):
        self.plugins = []

        # Load plugins
        for p in settings.CLAUDIA_PLUGINS:
            cls = _get_class(p)
            self.add_plugin(cls())

    @classmethod
    def get_instance(cls) -> 'Claudia':
        if cls._instance is None:
            cls._instance = Claudia()
        return cls._instance

    # ===== Plugin functions =====

    def add_plugin(self, cplugin):
        """
        Add a plugin
        :param cplugin: A ClaudiaPlugin plugin instance
        :type cplugin: ClaudiaPlugin
        """
        logger.debug("Plugin %s registered" % cplugin.__class__.__name__)
        self.plugins.append(cplugin)

    def delete_plugin(self, cplugin):
        """
        Remove a plugin
        :param cplugin: A ClaudiaPlugin plugin instance
        :type cplugin: ClaudiaPlugin
        """
        self.plugins.remove(cplugin)

    notify_mapping_created = wrap_call_plugins("mapping_created")
    notify_mapping_changed = wrap_call_plugins("mapping_changed")
    notify_mapping_deleted = wrap_call_plugins("mapping_deleted")

    notify_verify_mapping = wrap_call_plugins("verify_mapping")
    notify_verify_finished = wrap_call_plugins("verify_finished")

    notify_account_created = wrap_call_plugins("account_created")
    notify_account_changed = wrap_call_plugins("account_changed")
    notify_account_scheduled_delete = wrap_call_plugins("account_scheduled_delete")
    notify_account_unscheduled_delete = wrap_call_plugins("account_unscheduled_delete")

    notify_gsuite_created = wrap_call_plugins("gsuite_created")
    notify_gsuite_changed = wrap_call_plugins("gsuite_changed")
    notify_gsuite_scheduled_delete = wrap_call_plugins("gsuite_scheduled_delete")
    notify_gsuite_unscheduled_delete = wrap_call_plugins("gsuite_unscheduled_delete")

    notify_alexia_created = wrap_call_plugins("alexia_created")
    notify_alexia_changed = wrap_call_plugins("alexia_changed")

    notify_gitlab_created = wrap_call_plugins("gitlab_created")
    notify_gitlab_changed = wrap_call_plugins("gitlab_changed")

    # ===== Integrity check ======
    @staticmethod
    def check_integrity():
        """
        Enqueues a complete integrity check of all aliases, mappings and other Mappables.
        In more detail, this will run:
        - Verify on all objects in the linked database
        - Verify on all other cid's in the database
        These both need to be queued, because a Mapping might not exist for a new object, or a Mapping might still exist for a deleted object.
        """
        logger.info("Start of check_integrity")
        from amelie.claudia.models import Mapping

        # Generate a cycle ID for the Celery tasks, so that they use the same cache key
        # to determine whether a Mapping was already verified before or not.
        # If we would not pass this, each queued object would get a different cycle ID,
        # resulting in its own separated tree of verified objects, and we would be doing a lot of extra work.
        import uuid
        cycle_id = str(uuid.uuid4())

        # Keep track of Cid's
        cids = []
        for rc in Mapping.RELATED_CLASSES:
            rc_objects = Mapping.RELATED_CLASSES[rc].get_all()
            logger.debug(f"Queueing verification for {rc_objects.count()} '{rc}' objects.")
            for obj in rc_objects:
                mp = Mapping.find(obj)
                verify_object.delay(object_id=obj.id, object_type=rc, cycle_id=cycle_id)
                if mp:
                    cids.append(mp.id)

        # Other left-over mappings, should not happen.
        for mp in Mapping.objects.all():
            if mp.id not in cids:
                verify_object.delay(object_id=mp.id, object_type=None, cycle_id=cycle_id)

        logger.info("Scheduled all objects for verification. They are now being processed by Celery, this may take a while.")

    # ===== Verify function ====

    def verify_mapping(self, mp, fix=False):
        """
        Check all standard attributes, and call all activated plugins to verify this mapping.
        :type mp: Mapping
        :type fix: bool
        """
        logger.debug(f"Verifying mapping '{mp.name}' (cid: {mp.id})")

        changes = mp.check_mapping(fix)
        if changes:
            self.notify_mapping_changed(mp, changes)

        self.notify_verify_mapping(mp, fix)
