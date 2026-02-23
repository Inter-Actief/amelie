"""Plugin for managing Matrix spaces."""
import asyncio
import logging
from typing import Optional, List, Tuple

from asgiref.sync import sync_to_async
from django.conf import settings
from mautrix.client import ClientAPI
from mautrix.errors import MatrixResponseError
from mautrix.types import UserID, RoomID, RoomDirectoryVisibility, RoomCreateStateEventContent, RoomType, EventType, \
    SpaceChildStateEventContent, SpaceParentStateEventContent

from amelie.claudia.plugins.plugin import ClaudiaPlugin
from amelie.claudia.clau import Claudia
from amelie.claudia.models import Mapping

logger = logging.getLogger(__name__)


def get_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


class MatrixPlugin(ClaudiaPlugin):
    """
    Matrix plugin for Claudia

    Manages the link between Claudia objects and Matrix spaces

    Author: k.j.alberts
    """

    def verify_mapping(self, claudia: Claudia, mp: Mapping, fix: bool = False):
        """
        Verify the Matrix account of a mapping

        :param Claudia claudia: Claudia instance.
        :param Mapping mp: Mapping object to verify.
        :param bool fix: Fixes should be applied.
        """
        logger.debug("Verifying Matrix data of {} (cid: {})".format(mp.name, mp.id))
        loop = get_event_loop()
        return loop.run_until_complete(self.verify_mapping_async(claudia, mp, fix))

    async def verify_mapping_async(self, claudia: Claudia, mp: Mapping, fix: bool = False):

        changes: List[Tuple[str, str]] = []

        user: UserID = UserID(settings.CLAUDIA_MATRIX['USER'])
        server: str = settings.CLAUDIA_MATRIX['SERVER']
        token: str = settings.CLAUDIA_MATRIX['TOKEN']

        client: ClientAPI = ClientAPI(user, base_url=server, token=token)
        try:
            if not fix:
                logger.debug("No changes will me made to internal attributes")

            if mp.is_person():
                logger.debug("Mapping is a person, no Matrix actions necessary.")

            elif mp.is_group():
                wants_matrix =  mp.extra_data().get('matrix', False)
                if wants_matrix:
                    logger.debug("Mapping is a group and should have a Matrix space, checking if a space exists in Matrix.")

                    if mp.adname:
                        # Check if this committee has a space
                        space = await self.get_or_find_space(client, mp)

                        if space:
                            logger.debug("Matrix space for {} exists.".format(mp.adname))

                        if space is None and mp.needs_account():
                            logger.debug("Matrix space for {} does not exist, creating.".format(mp.adname))
                            if fix:
                                space = await self.create_space(client, mp)
                                await sync_to_async(mp.set_matrix_space_id, thread_sensitive=True)(matrix_space_id=space)
                                if space:
                                    changes.append(('space', '{} created'.format(space)))
                                    await sync_to_async(claudia.notify_matrix_created, thread_sensitive=True)(mp, mp.adname)
                                else:
                                    logger.error("Matrix space creation for {} failed.".format(mp.adname))
                else:
                    logger.debug("Mapping is a group, but no Matrix space is requested for this group.")

            if changes:
                await sync_to_async(claudia.notify_matrix_changed, thread_sensitive=True)(mp, mp.adname, changes)
        finally:
            if client and client.api and client.api.session:
                await client.api.session.close()

    @staticmethod
    async def get_or_find_space(client: ClientAPI, mapping: Mapping) -> Optional[RoomID]:
        """
        Get the space for this mapping, find it based on tags if it is not cached.
        Returns None if no space is found.
        """
        joined_rooms = await client.get_joined_rooms()

        # Find room from ID stored in the mapping
        mapping_space_id = mapping.get_matrix_space_id()
        if mapping_space_id is not None:
            # Check if this space still exists
            space = RoomID(mapping_space_id)
            try:
                if space in joined_rooms:
                    return space
            except KeyError:
                pass
            # Space doesn't exist (or the bot isn't a member anymore), remove its reference from the mapping
            await sync_to_async(mapping.set_matrix_space_id, thread_sensitive=True)(matrix_space_id=None)

        # Find room by tags of joined rooms, save its Room ID in the mapping if found.
        for room in joined_rooms:
            room_tags = await client.get_room_tag(room, tag="ia.group_name:{}".format(mapping.adname))
            if room_tags is not None:
                await sync_to_async(mapping.set_matrix_space_id, thread_sensitive=True)(matrix_space_id=room)
                return room

        return None

    @staticmethod
    async def create_space(client: ClientAPI, mapping: Mapping) -> Optional[RoomID]:
        """
        Creates a space for the given mapping.
        """
        space: Optional[RoomID] = None

        # Determine group suffix for use in the Space topic based on mapping type
        group_description = "group"
        if mapping.is_committee():
            group_description = "committee"
        if mapping.is_dogroup():
            group_description = "dogroup"

        # Add a flag to indicate we are creating a Space, not a Room
        creation_content = RoomCreateStateEventContent()
        creation_content.type = RoomType.SPACE

        # Create the space as a Private space with the options above.
        try:
            space = await client.create_room(
                visibility=RoomDirectoryVisibility.PRIVATE,
                name=mapping.name,
                topic=f"Private space for {mapping.name} {group_description}",
                creation_content=creation_content
            )
        except MatrixResponseError as e:
            logger.error(f"Failed to create Matrix space for {mapping.adname} failed. - {e}")

        # Add tags indicating this is a space for one of our groups (used by our auto-invite bot)
        if space is not None:
            await client.set_room_tag(
                space, tag="ia.group_name:{}".format(mapping.adname)
            )

        # Add the newly created space to the general IA space as a child.
        main_ia_space = RoomID(settings.CLAUDIA_MATRIX['IA_SPACE_ID'])
        homeserver = RoomID(settings.CLAUDIA_MATRIX['HOMESERVER'])
        try:
            await client.send_state_event(main_ia_space, EventType.SPACE_CHILD, SpaceChildStateEventContent(via=[homeserver]), space)
        except MatrixResponseError as e:
            logger.error(f"Failed to add Matrix space {space} as a child of main IA space {main_ia_space}. - {e}")
        try:
            await client.send_state_event(space, EventType.SPACE_PARENT, SpaceParentStateEventContent(via=[homeserver]), main_ia_space)
        except MatrixResponseError as e:
            logger.error(f"Failed to add main IA space {main_ia_space} as a parent of Matrix space {space}. - {e}")

        return space
