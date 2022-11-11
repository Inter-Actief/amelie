import logging
from threading import Timer, Lock

import ldap
from django.conf import settings

from amelie.claudia.models import Mapping

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

    def __init__(self):
        self.plugins = []
        self.queue = []
        self.queue_history = []
        # This lock is acquired by the run_queue method during the entire run.
        # This ensures that only one queue runner is running at the same time.
        self.run_queue_lock = Lock()
        # This lock protects the self.queue, self.queue_history variables
        self.queue_lock = Lock()

        # Load plugins
        for p in settings.CLAUDIA_PLUGINS:
            cls = _get_class(p)
            self.add_plugin(cls())

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

    def check_integrity(self):
        """
        Runs a complete integrity check of all aliases, mappings and other Mappables.
        In more detail, this will run:
        - Verify on all objects in the linked database
        - Verify on all other cid's in the database
        - Verify on all e-mail addresses in the alias database
        """
        logger.info("Start of check_integrity")

        # Keep track of Cid's
        cids = []
        for rc in Mapping.RELATED_CLASSES:
            logger.debug("Checking %s objects." % rc)
            for obj in Mapping.RELATED_CLASSES[rc].get_all():
                cid = self.do_verify_object(obj, enqueue_only=True)
                if cid:
                    cids.append(cid)

        # Other left-over mappings, should not happen.
        for mp in Mapping.objects.all():
            if mp.id not in cids:
                self.do_verify_mp(mp, enqueue_only=True)

        # The above should have queued all objects for a verify. Let's check them!
        self.run_queue(fix=True)

        logger.info("End of check_integrity")

    # ===== Verify functions ====

    def do_verify(self, obj, enqueue_only=False):
        if isinstance(obj, Mapping):
            self.do_verify_mp(obj, enqueue_only)
        else:
            self.do_verify_object(obj, enqueue_only)

    def do_verify_object(self, obj, enqueue_only=False):
        """
        Checks for an object if its mapping is present
        :type obj: Mappable & models.Model
        :type enqueue_only: bool
        """
        logger.debug("Verification of object %s requested (type %s, id %s)."
                     % (obj.get_name(), Mapping.get_type(obj), obj.id))

        # First check if a mapping exists
        mp = Mapping.find(obj)

        # Check mapping/cmid
        if mp is None and obj.is_needed():
            logger.debug('%s has no mapping, but is active, creating' % obj.get_name())
            mp = Mapping.create(obj)

        if mp is None:
            logger.debug('%s is not active and has no mapping, skipping.' % obj.get_name())
            return False

        return self.do_verify_mp(mp, enqueue_only)

    def do_verify_mp(self, mp, enqueue_only=False):
        """
        Checks a mapping.
        :type mp: Mapping
        :type enqueue_only: bool
        """
        logger.debug("Verification of mapping %s requested (type %s, id %s)." % (mp.name, mp.type, mp.ident))

        # Check if the mapping should be active
        if not mp.active and mp.is_needed():
            logger.debug("Activating mapping %s (cid %s)" % (mp.name, mp.id))
            mp.active = True
            mp.save()
            self.notify_mapping_created(mp)

        # Enqueue the actual verification
        self.enqueue(mp)
        if not enqueue_only:
            self.run_queue(fix=True)

        # Finally, check if the mapping should be inactive
        if not mp.is_needed() and mp.active:
            logger.debug("Deactivating mapping %s (cid %s)" % (mp.name, mp.id))
            mp.active = False
            mp.save()
            self.notify_mapping_deleted(mp)

        return mp.id

    def enqueue(self, mp):
        """Put the given mapping into the queue to be verified. This will ensure neat sequential verification."""

        # If the mapping is already in the queue history for this session, don't add it,
        # because it might lead to infinite recursion and we don't want that.
        with self.queue_lock:
            if mp.id not in self.queue_history:
                logger.debug("Enqueueing Mapping %s (id %s) for later verification" % (mp.name, mp.id))
                self.queue_history.append(mp.id)
                self.queue.append(mp)
            else:
                logger.debug("Not enqueueing Mapping %s (id %s) because it has already been checked"
                             % (mp.name, mp.id))

    def run_queue(self, fix):
        """Run verifications for the queue of mappings."""

        # Try to obtain the queue lock (non-blocking). If this fails, there is already a queue runner and
        # that one will process anything that was added to the queue before now.
        if self.run_queue_lock.acquire(False):
            logger.debug("Starting queue run")
            # Lock the queue_lock. It needs to be locked when checking the while
            # condition, since that accesses the queue.
            self.queue_lock.acquire()
            stop = False
            while self.queue and not stop:
                # Get the first object
                mp = self.queue.pop()

                # Done with the queue for now, release
                self.queue_lock.release()

                try:
                    logger.debug("Verifying Mapping %s (cid %s) from queue" % (mp.name, mp.id))
                    self.verify_mapping(mp, fix)

                except ldap.SERVER_DOWN as e:
                    # On server connection problems, stop processing and retry
                    # in five minutes. This is only a partial solution, since
                    # if any new verification requests come in, they will fail
                    # before ending up in the queue (because creating a
                    # ClaudiaObject does some ad calls already). Perhaps we
                    # should thus also put the (type, id) and addresses in the
                    # queue, instead of processing those directly in
                    # do_verify_object / verify_email. Until then, this delay
                    # code is slightly pointless.

                    logger.error('LDAP server down: %s (retrying in 300s)' % str(e))
                    # Requeue the object
                    self.queue.append(mp)
                    # Schedule a new runner in 300s
                    t = Timer(300.0, self.run_queue, [fix])
                    t.start()
                    # Stop this runner
                    stop = True
                except Exception as e:
                    # Report exception, but continue with the queue
                    logger.exception(
                        "Exception raised when verifying Mapping %s (cid %s): %s" % (mp.name, mp.id, str(e)))
                    if settings.CLAUDIA_STOP_ON_ERROR:
                        raise

                # Lock again for the while condition
                self.queue_lock.acquire()

            # Clear the history. The queue might not be empty yet (when a retry
            # is scheduled), but in that case, redoing some work shouldn't hurt
            # (and shouldn't lead to infinite loops, since we should stop
            # rescheduling eventually.
            self.queue_history = []

            # Release locks. Always release the run_queue lock first, to
            # prevent the following scenario:
            # - We see that the queue is empty
            # - We release queue_lock
            # - Another thread enqueues something
            # - Another thread calls run_queue, which returns since we are running already
            # - We release run_queue_lock
            # -> No queue is running, but the queue is not empty yet!
            self.run_queue_lock.release()
            self.queue_lock.release()

            # Let plugins know we finished processing.
            self.notify_verify_finished()
        else:
            logger.debug("Not starting queue run, one is already running.")

    def verify_mapping(self, mp, fix=False):
        """
        Check all standard attributes
        :type mp: Mapping
        :type fix: bool
        """
        logger.debug("Verifying mapping %s (cid: %s)" % (mp.name, mp.id))

        changes = mp.check_mapping(fix)
        if changes:
            self.notify_mapping_changed(mp, changes)

        self.notify_verify_mapping(mp, fix)

        if mp.is_group() or mp.is_shareddrive():
            for mem in mp.members(old_members=True):
                self.do_verify_mp(mem, enqueue_only=True)
