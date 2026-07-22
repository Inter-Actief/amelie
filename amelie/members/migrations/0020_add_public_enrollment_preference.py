# Made by Conner v5.2.12 on 2026-05-06 08:41

from django.db import migrations
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def forwards(apps, schema_editor):
    Preference = apps.get_model("members", "Preference")
    pref = Preference.objects.filter(name='public_enrollment').first()
    logger.info("Starting public enrollment preference migration")

    if pref is None:
        logger.warning("Could not find the 'public_enrollment' migration! The rest of this migration will not run.")
        return

    Person = apps.get_model("members", "Person")
    logger.info(f"All persons: {len(Person.objects.all())}")

    # current state
    logger.info(f"Pre-migration old state (none should be checked):")
    persons_public_enrollment = Person.objects.filter(preferences__name="public_enrollment")
    logger.info(f"- Public enrollment (checked): {len(persons_public_enrollment)}")
    persons_no_public_enrollment = Person.objects.exclude(preferences__name="public_enrollment")
    logger.info(f"- Anonymous enrollment (unchecked): {len(persons_no_public_enrollment)}")


    for i, person in enumerate(Person.objects.all().iterator()):
        # Django does not like that it has an id of 0, and we have a dummy account with that id...
        if person.id == 0:
            continue
        person.preferences.add(pref)

    # new state, this should be inverted now
    logger.info(f"Post-migration new state (all should be checked, except one, our dummy account with id==0):")
    persons_public_enrollment = Person.objects.filter(preferences__name="public_enrollment")
    logger.info(f"- Public enrollment (checked): {len(persons_public_enrollment)}")
    persons_no_public_enrollment = Person.objects.exclude(preferences__name="public_enrollment")
    logger.info(f"- Anonymous enrollment (unchecked): {len(persons_no_public_enrollment)}")

    logger.info("Public enrollment preference migration complete.")


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0019_committee_matrix'),
    ]

    operations = [
        migrations.RunPython(forwards),
    ]

# Ik wil dat mijn inschrijving voor een activiteit door andere leden gezien kan worden.
# I want my enrollment for an activity to be visible to other members.
