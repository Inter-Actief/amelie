import uuid
import logging
import ldap

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from typing import Optional


logger = logging.getLogger(__name__)


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

    from amelie.claudia.clau import Claudia
    from amelie.claudia.models import Mapping
    claudia = Claudia.get_instance()

    # Retrieve object to be verified
    if object_type is not None:
        obj = Mapping.get_object_from_mapping(object_type, object_id)
        logger.debug(f"Verification of object '{obj.get_name()}' requested. (type {object_type}, oid {object_id})")
        # First check if a mapping exists
        mp = Mapping.find(obj)
        # If no mapping was found, check if one is needed
        if mp is None and obj.is_needed():
            logger.debug(f"{obj.get_name()} has no mapping, but is active, creating.")
            mp = Mapping.create(obj)
            claudia.notify_mapping_created(mp)
        # If there is no mapping, then this object is not needed and exists nowhere, we can skip it.
        if mp is None:
            logger.debug(f"{obj.get_name()} is not active and has no mapping, skipping.")
            return {"status": "skipped", "object_id": object_id, "object_type": object_type}
    else:
        mp = Mapping.objects.get(id=object_id)
        logger.debug(f"Verification of mapping '{mp.name}' requested (type {mp.type}, oid {mp.ident}, cid {mp.id}).")

    # Check if the mapping should be activated
    if not mp.active and mp.is_needed():
        logger.debug(f"Activating mapping '{mp.name}' (cid {mp.id})")
        mp.active = True
        mp.save()
        claudia.notify_mapping_created(mp)

    checked_objects_cache_key = f"verification_cycle_{cycle_id}_objects"
    pending_count_cache_key = f"verification_cycle_{cycle_id}_pending"

    # Check if already queued
    already_checked_objects = cache.get(checked_objects_cache_key, set())
    if mp.id in already_checked_objects:
        logger.debug(f"Not verifying Mapping '{mp.name}' (cid {mp.id}) because it has already been checked in cycle {cycle_id}")
        return {"status": "already_checked", "object_id": object_id, "object_type": object_type}

    # Do some logging
    logger.debug(f"Verifying Mapping '{mp.name}' (cid {mp.id}) in cycle {cycle_id}...")

    # Track pending tasks for cleanup. Make sure the root (first to process) always gets a pending count of 1.
    if is_root:
        cache.set(pending_count_cache_key, 1, timeout=7200)

    try:
        try:
            # Perform the actual verify action.
            claudia.verify_mapping(mp=mp, fix=fix)
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

        return {"status": "verified", "object_id": object_id, "object_type": object_type}

    except Exception as exc:
        logger.error(f"Failed to verify mapping '{mp.name}' (cid {mp.id}): {exc}")
        # Remove from queued set so it can be retried in case it is enqueued again in this same run.
        already_checked_objects = cache.get(checked_objects_cache_key, set())
        already_checked_objects.discard(object_id)
        cache.set(checked_objects_cache_key, already_checked_objects, timeout=7200)
        raise

    finally:
        # Add to checked objects
        already_checked_objects = cache.get(checked_objects_cache_key, set())
        already_checked_objects.add(object_id)
        cache.set(checked_objects_cache_key, already_checked_objects, timeout=7200)

        # Decrement pending counter
        current_pending = cache.get(pending_count_cache_key, 1)
        cache.set(pending_count_cache_key, current_pending - 1, timeout=7200)

        # Last task in cycle, cleanup
        final_pending = cache.get(pending_count_cache_key, 0)
        if final_pending <= 0:
            cache.delete(checked_objects_cache_key)
            cache.delete(pending_count_cache_key)
            logger.info(f"Cleaned up verification cycle {cycle_id}")

            # Finally, if this was the last object to be verified in this cycle, check if any of the processed mappings should be deactivated.
            logger.debug(f"Checking if any mappings need to be deactivated...")
            for object_id in already_checked_objects:
                checked_mapping = Mapping.objects.get(id=object_id)
                if not checked_mapping.is_needed() and checked_mapping.active:
                    logger.debug(f"Deactivating mapping '{checked_mapping.name}' (cid {checked_mapping.id})")
                    checked_mapping.active = False
                    checked_mapping.save()
                    claudia.notify_mapping_deleted(checked_mapping)

        logger.debug(f"Finished Claudia verification for object {object_id} (type {object_type}) ({final_pending} pending in queue for this cycle).")
