# Generated by Django 2.2.17 on 2020-11-03 21:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('claudia', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='event',
            name='mapping',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='claudia.Mapping'),
        ),
        migrations.AlterField(
            model_name='membership',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_members', to='claudia.Mapping'),
        ),
        migrations.AlterField(
            model_name='membership',
            name='member',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='extra_groupmemberships', to='claudia.Mapping'),
        ),
    ]
