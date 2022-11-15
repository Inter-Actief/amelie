# Generated by Django 3.2.16 on 2022-10-28 13:02

import amelie.files.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('files', '0004_auto_20220905_2137'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attachment',
            name='file',
            field=models.FileField(max_length=150, upload_to=amelie.files.models.get_upload_filename),
        ),
        migrations.AlterField(
            model_name='attachment',
            name='thumb_large',
            field=models.ImageField(blank=True, editable=False, height_field='thumb_large_height', max_length=150, null=True, upload_to=amelie.files.models.get_upload_filename, width_field='thumb_large_width'),
        ),
        migrations.AlterField(
            model_name='attachment',
            name='thumb_medium',
            field=models.ImageField(blank=True, editable=False, height_field='thumb_medium_height', max_length=150, null=True, upload_to=amelie.files.models.get_upload_filename, width_field='thumb_medium_width'),
        ),
        migrations.AlterField(
            model_name='attachment',
            name='thumb_small',
            field=models.ImageField(blank=True, editable=False, height_field='thumb_small_height', max_length=150, null=True, upload_to=amelie.files.models.get_upload_filename, width_field='thumb_small_width'),
        ),
    ]