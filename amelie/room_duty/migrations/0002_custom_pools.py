from __future__ import unicode_literals

from django.db import migrations, models


def pool_to_tables(apps, schema_editor):
    RoomDutyTable = apps.get_model('room_duty', 'RoomDutyTable')

    for table in RoomDutyTable.objects.prefetch_related('pool').all():
        for rel in table.pool.unsorted_persons.through.objects.filter(roomdutypool=table.pool).order_by('id').prefetch_related('person'):
            table.unsorted_pool.add(rel.person)

        table.save()


class Migration(migrations.Migration):

    dependencies = [
        ('members', '0001_initial'),
        ('room_duty', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='roomdutytable',
            name='unsorted_pool',
            field=models.ManyToManyField(related_name='room_duty_tables', to='members.Person'),
        ),
        migrations.RunPython(
            code=pool_to_tables,
        ),
        migrations.RemoveField(
            model_name='roomdutytable',
            name='pool',
        ),
    ]
