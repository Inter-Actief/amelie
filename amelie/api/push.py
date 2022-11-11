import logging

from django.core.exceptions import ObjectDoesNotExist
from django.template import Template, Context

from fcm_django.models import FCMDevice
from jsonrpc import jsonrpc_method
from jsonrpc.exceptions import InvalidParamsError

from amelie.api.decorators import authentication_optional, authentication_required
from amelie.api.exceptions import UnknownDeviceError, PermissionDeniedError
from amelie.api.models import PushNotification
from amelie.api.utils import generate_token

logger = logging.getLogger(__name__)


@jsonrpc_method('getDeviceId() -> String', validate=True)
def get_device_id(request):
    token = generate_token()
    return token if len(FCMDevice.objects.filter(device_id=token)) == 0 else get_device_id(request)


@jsonrpc_method('getPushContent(Number) -> Array', validate=True)
@authentication_required("account")
def get_push_content(request, push_id, authentication=None):
    person = authentication.represents()
    notification = PushNotification.objects.filter(id=push_id, recipients__in=[person]).first()
    message = Template(notification.message).render(Context({'recipient': person}))

    if not notification:
        raise PermissionDeniedError()

    return {
        'title': notification.title,
        'message': message,
    }


@jsonrpc_method('registerPushChannel(String, String, String) -> Boolean', validate=True)
@authentication_optional()
def register_push_channel(request, device_id, channel_id, type, authentication=None):
    # User object used in order to send push notifications to specific persons
    user = None

    # Overwrite user object if the method is being called with valid authentication credentials
    if authentication is not None:
        person = authentication.represents()
        user = person.user if person is not None else None

    # If the type of the device requested to be registered is not supported, raise a InvalidParameterError
    if not any(type == value for key, value in FCMDevice.DEVICE_TYPES):
        raise InvalidParamsError("The type of notification channel to be used can only be `android` or `ios`.")

    # Delete a previously registered FCMDevice for a given channel identifier
    FCMDevice.objects.filter(registration_id=channel_id).delete()

    # Register new FCM device
    FCMDevice(device_id=device_id, registration_id=channel_id, type=type, user=user).save()

    # Return true to indicate successful registration of FCM device
    return True


@jsonrpc_method('deletePushChannel(String) -> Boolean', validate=True)
def delete_push_channel(request, device_id):
    # Try to obtain the device using the device identifier and person
    try:
        device = FCMDevice.objects.get(device_id=device_id)
    except ObjectDoesNotExist:
        raise UnknownDeviceError()

    # Delete the device and return true to indicate successful deletion of FCM device
    device.delete()
    return True
