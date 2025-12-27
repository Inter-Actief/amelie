import uuid
import ldap
import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from typing import Optional


logger = logging.getLogger(__name__)


CHECKED_OBJECTS_CACHE_KEY_TEMPLATE = "verification_cycle_{cycle_id}_objects"
PENDING_COUNT_CACHE_KEY_TEMPLATE = "verification_cycle_{cycle_id}_pending"


# ===== Integrity check ======
@shared_task(name="claudia.check_integrity", acks_late=True)
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

    # Generate a cycle ID for the Celery tasks so that they use the same cache key
    # to determine whether a Mapping was already verified before or not.
    # If we did not pass this, each queued object would get a different cycle ID,
    # resulting in its own separated tree of verified objects, and we would be doing a lot of extra work.
    import uuid
    cycle_id = str(uuid.uuid4())

    # Set initial values for the cache keys. Because there is only one claudia queue worker, and both this task and
    # the verification tasks run in that worker, their cache is guaranteed to be shared. We need to initialize these
    # caches properly because we are generating a cycle ID for the verification, which means the initialization of the
    # cache will not happen on the first verification, so we need to initialize them here.
    checked_objects_cache_key = CHECKED_OBJECTS_CACHE_KEY_TEMPLATE.format(cycle_id=cycle_id)
    pending_count_cache_key = PENDING_COUNT_CACHE_KEY_TEMPLATE.format(cycle_id=cycle_id)
    # We set the checked objects to an empty set because no objects have been checked yet.
    cache.set(checked_objects_cache_key, set(), timeout=7200)
    # We set the pending counter to 0 because no tasks have been enqueued yet. Later when enqueueing objects, this counter will be increased.
    cache.set(pending_count_cache_key, 0, timeout=7200)

    # Keep track of Cid's
    cids = []
    for rc in Mapping.RELATED_CLASSES:
        rc_objects = Mapping.RELATED_CLASSES[rc].get_all()
        logger.debug(f"Queueing verification for {rc_objects.count()} '{rc}' objects.")
        for obj in rc_objects:
            mp = Mapping.find(obj)
            # Increment pending counter
            current_pending = cache.get(pending_count_cache_key, 0)
            cache.set(pending_count_cache_key, current_pending + 1, timeout=7200)
            # Schedule task
            verify_object.delay(object_id=obj.id, object_type=rc, cycle_id=cycle_id)
            if mp:
                cids.append(mp.id)

    # Other left-over mappings (should not happen).
    for mp in Mapping.objects.all():
        if mp.id not in cids:
            # Increment pending counter
            current_pending = cache.get(pending_count_cache_key, 0)
            cache.set(pending_count_cache_key, current_pending + 1, timeout=7200)
            # Schedule task
            verify_object.delay(object_id=mp.id, object_type=None, cycle_id=cycle_id)

    logger.info("Scheduled all objects for verification. They are now being processed by Celery, this may take a while.")


@shared_task(
    name="claudia.verify_object", acks_late=True,
    # Auto-retry when LDAP is down, first time after 1 minute, exponential after that (2m, 4m, 8m, 10m, 10m)
    autoretry_for=(ldap.SERVER_DOWN,), retry_backoff=60, retry_backoff_max=600, retry_jitter=True,
)
def verify_object(object_id: int, object_type: Optional[str] = None, fix: bool = True, cycle_id: Optional[str] = None):
    """
    Let Claudia verify an object and all of its related objects.

    :param object_id: The PK of a Mappable object, or the PK of a Claudia Mapping.
                      If a Mappable object is given, the `object_type` parameter must be given as well.
    :type object_id: int

    :param object_type: The type of the Mappable object, or None if the given object is a Mapping. Must be a key of `Mapping.RELATED_CLASSES`.
    :type object_type: str | None

    :param fix: Whether to fix any issues that Claudia finds. Defaults to True.
    :type fix: bool

    :param cycle_id: Leave empty on the initial call. Verifications of related objects will set this to determine which processing cycle they belong to.
    :type cycle_id: str | None

    :return: A dictionary with the following keys:
      - status: "verified", "skipped", "already_checked" or "failed"
      - object_id: The PK of the object that was verified
      - object_type: The type of the object that was verified. Only present if the object was a Mappable object.

    :raises Exception: If the verification fails for any reason. Can be any exception type.
    """
    logger.debug(f"Starting Claudia verification for object {object_id} (type {object_type}) with fix={fix} and cycle_id={cycle_id}...")
    is_root = False
    if cycle_id is None:
        cycle_id = str(uuid.uuid4())
        is_root = True
        logger.info(f"Started new verification cycle: {cycle_id}")

    # Determine the names for the cache keys.
    checked_objects_cache_key = CHECKED_OBJECTS_CACHE_KEY_TEMPLATE.format(cycle_id=cycle_id)
    pending_count_cache_key = PENDING_COUNT_CACHE_KEY_TEMPLATE.format(cycle_id=cycle_id)

    def check_cycle_end():
        """
        Helper function to call whenever we are about to exit the verification function,
        to decrement the pending objects counter and to perform cleanup at the very end of the cycle.
        """
        # Decrement pending counter
        cycle_pending = cache.get(pending_count_cache_key, 1)
        cache.set(pending_count_cache_key, cycle_pending - 1, timeout=7200)

        # Last task in cycle, cleanup
        final_pending = cache.get(pending_count_cache_key, 0)
        if final_pending <= 0:
            final_checked_objects = cache.get(checked_objects_cache_key, set())
            cache.delete(checked_objects_cache_key)
            cache.delete(pending_count_cache_key)
            logger.info(f"Cleaned up verification cycle {cycle_id}")

            # Finally, if this was the last object to be verified in this cycle, check if any of the processed mappings should be deactivated.
            logger.debug(f"Checking if any mappings need to be deactivated...")
            for checked_object_id in final_checked_objects:
                checked_mapping = Mapping.objects.get(id=checked_object_id)
                if not checked_mapping.is_needed() and checked_mapping.active:
                    logger.debug(f"Deactivating mapping '{checked_mapping.name}' (cid {checked_mapping.id})")
                    checked_mapping.active = False
                    checked_mapping.save()
                    claudia.notify_mapping_deleted(checked_mapping)

        logger.debug(f"Finished Claudia verification for object {object_id} (type {object_type}) ({final_pending} pending in queue for this cycle).")

    # Get Claudia in here so we can notify other plugins and schedule other mappings
    from amelie.claudia.clau import Claudia
    from amelie.claudia.models import Mapping
    claudia = Claudia.get_instance()

    # Retrieve object to be verified
    if object_type is not None:
        obj = Mapping.get_object_from_mapping(object_type, object_id)
        logger.debug(f"Verification of object '{obj.get_name()}' requested. (type {object_type}, oid {object_id})")
        # First, check if a mapping exists
        mp = Mapping.find(obj)
        # If no mapping was found, check if one is needed
        if mp is None and obj.is_needed():
            logger.debug(f"{obj.get_name()} has no mapping, but is active, creating.")
            mp = Mapping.create(obj)
            claudia.notify_mapping_created(mp)
        # If there is no mapping, then this object is not needed and exists nowhere; we can skip it.
        if mp is None:
            logger.debug(f"{obj.get_name()} is not active and has no mapping, skipping.")
            check_cycle_end()
            return {"status": "skipped", "object_id": object_id, "object_type": object_type}
    else:
        mp = Mapping.objects.get(id=object_id)
        logger.debug(f"Verification of mapping '{mp.name}' requested (type {mp.type}, oid {mp.ident}, cid {mp.id}).")

    # Check if already queued
    already_checked_objects = cache.get(checked_objects_cache_key, set())
    if mp.id in already_checked_objects:
        logger.debug(f"Not verifying Mapping '{mp.name}' (cid {mp.id}) because it has already been checked in cycle {cycle_id}")
        check_cycle_end()
        return {"status": "already_checked", "object_id": object_id, "object_type": object_type}

    # Do some logging
    logger.debug(f"Verifying Mapping '{mp.name}' (cid {mp.id}) in cycle {cycle_id}...")

    # Check if the mapping should be activated
    if not mp.active and mp.is_needed():
        logger.debug(f"Activating mapping '{mp.name}' (cid {mp.id})")
        mp.active = True
        mp.save()
        claudia.notify_mapping_created(mp)

    # Track pending tasks for cleanup. Make sure the root (first to process) always gets a pending count of 1.
    if is_root:
        cache.set(pending_count_cache_key, 1, timeout=7200)

    try:
        try:
            # Perform the actual verify action.
            claudia.verify_mapping(mp=mp, fix=fix)

            # Add to checked objects.  We do this here because the actual verification is done now. If an exception
            # occurs later (i.e., when queueing members), the object will be removed again so it can be re-queued.
            already_checked_objects = cache.get(checked_objects_cache_key, set())
            already_checked_objects.add(object_id)
            cache.set(checked_objects_cache_key, already_checked_objects, timeout=7200)
        except ldap.SERVER_DOWN:
            # Active Directory server is down. Just re-raise this error, because it is listed in the `autoretry_for`
            # list for the task, which will re-schedule this verification in 1 minute (with exponential backoff).
            # This is only a partial solution, since other verification requests already in the queue after us will
            # all fail too and also be retried.
            raise
        except Exception as e:
            # If the setting CLAUDIA_STOP_ON_ERROR is set, processing sub-mappings (members) is stopped.
            # Any objects that were already in the queue will still be verified after this.
            # If the setting is not set, any member objects will still be added to the queue for verification
            # even though verification of their parent failed.
            logger.exception(f"Exception raised when verifying Mapping '{mp.name}' (cid {mp.id}): {e}")
            if settings.CLAUDIA_STOP_ON_ERROR:
                raise

        # Queue related objects
        if mp.is_group() or mp.is_shareddrive():
            for member_mp in mp.members(old_members=True):
                # If the mapping is already in the history for this session, don't enqueue it for verification,
                # because it might lead to infinite recursion, and we don't want that.
                current_queued = cache.get(checked_objects_cache_key, set())
                if member_mp.id not in current_queued:
                    logger.debug(f"Enqueueing Mapping '{member_mp.name}' (cid {member_mp.id}) for later verification in cycle {cycle_id}")
                    # Increment pending counter
                    current_pending = cache.get(pending_count_cache_key, 0)
                    cache.set(pending_count_cache_key, current_pending + 1, timeout=7200)
                    # Schedule task
                    verify_object.delay(object_id=member_mp.id, object_type=None, fix=fix, cycle_id=cycle_id)
                else:
                    logger.debug(f"Not enqueueing Mapping '{member_mp.name}' (cid {member_mp.id}) because it has already been checked in cycle {cycle_id}")

        check_cycle_end()
        return {"status": "verified", "object_id": object_id, "object_type": object_type}

    except Exception as exc:
        logger.error(f"Error during verify of mapping '{mp.name}' (cid {mp.id}): {exc}")
        # Remove from the checked set so it can be retried in case it is enqueued again later in this cycle.
        already_checked_objects = cache.get(checked_objects_cache_key, set())
        already_checked_objects.discard(object_id)
        cache.set(checked_objects_cache_key, already_checked_objects, timeout=7200)
        raise

    finally:
        check_cycle_end()
