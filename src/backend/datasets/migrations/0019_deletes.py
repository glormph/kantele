from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('datasets', '0018_generalizing_analysis_dsets_samples'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ParamLabcategory',
        ),

        migrations.DeleteModel(
            name='DatasetComponent',
        ),

    ]

