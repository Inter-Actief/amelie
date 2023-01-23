# Generated manually
# Edited by Maarten for default career label

from django.db import migrations, models
import django.db.models.deletion


def create_default_career_label(apps, schema_editor):
    ActivityLabel = apps.get_model('activities', 'ActivityLabel')

    # this part is just because we need this label in the database, in case it does not exist
    # if it already exists, this will do nothing    
    obj, created = ActivityLabel.objects.get_or_create(
        name_en="Career",
        name_nl="Carrière",
        color="2450A8",
        icon="building",
        explanation_en="Activities from companies, lunch lectures or trainings",
        explanation_nl="Activiteiten van bedrijven, lunch lectures of trainingen"
    )

class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0004_auto_20221028_1502'),
    ]

    operations = [
        migrations.RunPython(create_default_career_label),
    ]
