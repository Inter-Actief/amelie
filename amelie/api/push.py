import logging
from typing import Dict

from fcm_django.models import FCMDevice
from modernrpc import RpcRequestContext
from modernrpc.exceptions import RPCInvalidParams

from django.template import Template, Context

from amelie.api.api import api_server
from amelie.api.authentication_types import AnonymousAuthentication
from amelie.api.decorators import auth_optional, auth_required
from amelie.api.exceptions import UnknownDeviceError, PermissionDeniedError
from amelie.api.models import PushNotification
from amelie.api.utils import generate_token


logger = logging.getLogger(__name__)


@api_server.register_procedure(name='getDeviceId')
def get_device_id(**kwargs) -> str:
    """
    Requests a new deviceId. Your application SHOULD call this method only once in your
    app's lifetime, just after its first start, and store the result for further use.

    **Module**: `push`

    **Authentication:** _(none)_

    **Parameters:** _(none)_

    **Return:**
      `str`: A string containing a newly assigned deviceId

    **Example:**

        --> {"method":"getDeviceId", "params":[]}
        <-- {"result": "QphLtj#z%Itaceny"}
    """
    token = generate_token()
    # Make sure token is unique across all FCMDevices
    while len(FCMDevice.objects.filter(device_id=token)) > 0:
        token = generate_token()
    return token


@api_server.register_procedure(name='getPushContent', auth=auth_required('account'), context_target='ctx')
def get_push_content(push_id: int, ctx: RpcRequestContext = None, **kwargs) -> Dict[str, str]:
    """
    Retrieves the details of a push notification that was sent to the currently authenticated person by its ID.

    **Module**: `push`

    **Authentication:** REQUIRED (Scope: account)

    **Parameters:**
      This method accepts the following parameters:

        - push_id: The ID of the push notification.

    **Return:**
      `Dict`: A dictionary with the following fields:

        - title: The title of the notification
        - message: The message of the notification

    **Raises:**

      NotLoggedInError: Token was not recognized or already revoked.

      PermissionDeniedError: Push notification does not exist or the authenticated person is not a
        recipient of this push notification.

    **Example:**

        --> {"method":"getPushContent", "params":[1234]}
        <-- {"result": {
               "title": "Activity is starting",
               "message": "The activity you signed up for is starting."
        }}
    """
    authentication = ctx.auth_result
    person = authentication.represents()
    notification = PushNotification.objects.filter(id=push_id, recipients__in=[person]).first()
    message = Template(notification.message).render(Context({'recipient': person}))

    if not notification:
        raise PermissionDeniedError()

    return {
        'title': notification.title,
        'message': message,
    }


@api_server.register_procedure(name='registerPushChannel', auth=auth_optional, context_target='ctx')
def register_push_channel(device_id: str, channel_id: str, type: str, ctx: RpcRequestContext = None, **kwargs) -> bool:
    """
    Registers a device to receive push notifications (optionally for the current authenticated person).
    If any old registrations for this device exist, they will be deactivated.

    **Module**: `push`

    **Authentication:** OPTIONAL

    **Parameters:**
      This method accepts the following parameters:

        - device_id: The ID of the device. (You can create a device ID once with `getDeviceId`).
        - channel_id: The Firebase FCM token registered to the device.
        - type: The type of the device wishing to receive the notification. (one of "ios", "android" or "web")

    **Return:**
      `bool`: If the device registration was successful or not.

    **Raises:**

      InvalidParamsError: The `type` parameter was invalid.

    **Example:**

        --> {"method":"registerPushChannel", "params":["QphLtj#z%Itaceny", "j_7_4....f2a+r", "android"]}
        <-- {"result": true}
    """
    authentication = ctx.auth_result

    # User object used in order to send push notifications to specific persons
    user = None

    # Overwrite user object if the method is being called with valid authentication credentials
    if authentication is not None:
        person = authentication.represents()
        user = person.user if person is not None else None

    # If the type of the device requested to be registered is not supported, raise a InvalidParameterError
    if not any(type == value for key, value in FCMDevice.DEVICE_TYPES):
        raise RPCInvalidParams("The type of notification channel to be used can only be `android` or `ios`.")

    # Delete a previously registered FCMDevice for a given channel identifier
    FCMDevice.objects.filter(registration_id=channel_id).delete()

    # Register new FCM device
    FCMDevice(device_id=device_id, registration_id=channel_id, type=type, user=user).save()

    # Return true to indicate successful registration of FCM device
    return True


@api_server.register_procedure(name='deletePushChannel')
def delete_push_channel(device_id: str, **kwargs) -> bool:
    """
    Unregisters a device from all push notifications.

    **Module**: `push`

    **Authentication:** _(none)_

    **Parameters:**
      This method accepts the following parameters:

        - device_id: The ID of the device. (You can create a device ID once with `getDeviceId`).

    **Return:**
      `bool`: If the deletion was successful or not.

    **Raises:**

      UnknownDeviceError: The device was not known.

    **Example:**

        --> {"method":"deletePushChannel", "params":["QphLtj#z%Itaceny"]}
        <-- {"result": true}
    """
    # Try to obtain the device using the device identifier and person
    try:
        device = FCMDevice.objects.get(device_id=device_id)
    except FCMDevice.DoesNotExist:
        raise UnknownDeviceError()

    # Delete the device and return true to indicate successful deletion of FCM device
    device.delete()
    return True
