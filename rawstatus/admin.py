from django.contrib import admin
from rawstatus.models import Producer, StoredFileType, ProducerFileType

# Register your models here.

admin.site.register(Producer)
admin.site.register(StoredFileType)
admin.site.register(ProducerFileType)
