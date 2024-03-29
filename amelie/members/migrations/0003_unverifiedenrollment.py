# -*- coding: utf-8 -*-
# Generated by Django 1.11.22 on 2019-07-16 11:47
from __future__ import unicode_literals

import amelie.tools.validators
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import localflavor.generic.models


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0002_model_translations'),
        ('personal_tab', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UnverifiedEnrollment',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=50, verbose_name='First name')),
                ('last_name_prefix', models.CharField(blank=True, max_length=25, verbose_name='Last name pre-fix')),
                ('last_name', models.CharField(max_length=50, verbose_name='Last name')),
                ('initials', models.CharField(blank=True, max_length=20, verbose_name='Initials')),
                ('gender', models.CharField(choices=[('Unknown', 'Unknown'), ('Man', 'Man'), ('Woman', 'Woman'), ('Other', 'Other')], max_length=9, verbose_name='Gender')),
                ('preferred_language', models.CharField(choices=[('nl', 'Dutch'), ('en', 'English')], default='nl', max_length=100, verbose_name='Language of preference')),
                ('international_member', models.CharField(choices=[('Yes', 'Yes, I am an international student.'), ('No', 'No, I am not an international student.'), ('Unknown', "I would rather not say if I'm an international student or not.")], max_length=16, verbose_name='International student')),
                ('date_of_birth', models.DateField(blank=True, null=True, verbose_name='Birth date')),
                ('email_address', models.EmailField(max_length=254, null=True, verbose_name='E-mail address')),
                ('address', models.CharField(max_length=50, verbose_name='Address')),
                ('postal_code', models.CharField(max_length=8, verbose_name='Postal code')),
                ('city', models.CharField(max_length=30, verbose_name='City')),
                ('country', models.CharField(default='Nederland', max_length=25, verbose_name='Country')),
                ('telephone', models.CharField(blank=True, max_length=20, verbose_name='Phonenumber')),
                ('email_address_parents', models.EmailField(blank=True, max_length=254, verbose_name='E-mail address of parent(s)/guardian(s)')),
                ('address_parents', models.CharField(blank=True, max_length=50, verbose_name='Address of parent(s)/guardian(s)')),
                ('postal_code_parents', models.CharField(blank=True, max_length=8, verbose_name='Postal code of parent(s)/guardian(s)')),
                ('city_parents', models.CharField(blank=True, max_length=30, verbose_name='Residence of parent(s)/guardian(s)')),
                ('country_parents', models.CharField(blank=True, default='Nederland', max_length=25, verbose_name='Country of parent(s)/guardian(s)')),
                ('can_use_parents_address', models.BooleanField(default=False, verbose_name="My parents' address details may be used for the parents day.")),
                ('authorizations', models.ManyToManyField(blank=True, to='personal_tab.Authorization', verbose_name='Authorizations')),
                ('membership_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='members.MembershipType', verbose_name='Chosen membership type')),
                ('membership_year', models.PositiveIntegerField(verbose_name='Membership start year')),
                ('student_number', models.PositiveIntegerField(blank=True, null=True, unique=True, validators=[amelie.tools.validators.CheckDigitValidator(7), django.core.validators.MaxValueValidator(9999999)], verbose_name='Student number')),
                ('study_start_date', models.DateField(verbose_name='Study start date')),
                ('dogroup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='members.DogroupGeneration', verbose_name='Dogroup')),
                ('preferences', models.ManyToManyField(blank=True, to='members.Preference', verbose_name='Preferences')),
                ('studies', models.ManyToManyField(blank=True, to='members.Study', verbose_name='Studies')),
            ],
        ),
    ]
