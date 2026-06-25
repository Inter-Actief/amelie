from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0011_alter_activity_components'),
    ]

    operations = [
        migrations.AddField(
            model_name='activity',
            name='enrollment_private',
            field=models.BooleanField(default=True, verbose_name='Hide participants'),
        ),
        migrations.AlterField(
            model_name='activity',
            name='enrollment_private',
            field=models.BooleanField(default=False, verbose_name='Hide participants'),
        ),
    ]
