# Generated by Django 2.2.17 on 2020-11-03 21:20

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('publications', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='publication',
            name='publication_type',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='publications.PublicationType'),
        ),
    ]