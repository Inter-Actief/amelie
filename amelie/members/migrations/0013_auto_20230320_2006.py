# Generated by Django 3.2.16 on 2023-03-20 19:06

import colorfield.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0012_person_ut_external_username'),
    ]

    operations = [
        migrations.AddField(
            model_name='dogroup',
            name='color',
            field=colorfield.fields.ColorField(default='#000000', help_text='What is the color of this dogroup?', image_field=None, max_length=18, samples=None, verbose_name='Color'),
        ),
        migrations.AddField(
            model_name='dogroupgeneration',
            name='generation_color',
            field=colorfield.fields.ColorField(blank=True, default=None, help_text='Similar to the dogroup color, however this value can be set in order to override the color for just this generation', image_field=None, max_length=18, null=True, samples=None, verbose_name='Generation color'),
        ),
    ]
