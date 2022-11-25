# Generated manually
# Edited by Maarten for default career label

from django.db import migrations, models
import django.db.models.deletion


def create_default_career_label(apps, schema_editor):
    ActivityLabel = apps.get_model('activities', 'ActivityLabel')

    obj, created = ActivityLabel.objects.get_or_create(
        name_en="Education",
        name_nl="Onderwijs",
        color="DC332E",
        icon="book_open",
        explanation_en="Educational",
        explanation_nl="Onderwijs-gerelateerd"
    )

class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0004_auto_20221028_1502'),
    ]

    operations = [
        migrations.RunPython(create_default_career_label),
    ]
