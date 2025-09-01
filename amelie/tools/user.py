from django.contrib.auth import get_user_model
from django.conf import settings


def get_user_by_username(username):
    """
    Retrieve a Django user model by username

    This can be an Inter-Actief username, or a UT student- or employee number.
    """
    UserModel = get_user_model()

    if not username:
        return UserModel.objects.none()

    if not settings.DEBUG and username.lower() in settings.LOGIN_NOT_ALLOWED_USERNAMES:
        return UserModel.objects.none()

    # Find Person by IA account name
    from amelie.members.models import Person
    try:
        person = Person.objects.get(account_name=username)
    except Person.DoesNotExist:
        # Login was successful, but person was not found (should not happen)
        person = None

    if person:
        # Get or create the user object for this person
        user, created = person.get_or_create_user(username)
    else:
        # Get or create the user object for this unknown user (not linked to a Person)
        user, created = UserModel.objects.get_or_create(username=username)
    return user
