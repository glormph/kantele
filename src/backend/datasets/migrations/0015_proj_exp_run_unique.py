from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0014_merge_duplicate_projects'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='name',
            field=models.TextField(unique=True),
        ),
        migrations.AddConstraint(
            model_name='experiment',
            constraint=models.UniqueConstraint(fields=('name', 'project'), name='uni_expproj'),
        ),
        migrations.AddConstraint(
            model_name='runname',
            constraint=models.UniqueConstraint(fields=('name', 'experiment'), name='uni_runexp'),
        ),
    ]
