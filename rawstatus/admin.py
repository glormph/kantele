from django.contrib import admin
from rawstatus.models import Producer, StoredFileType, MSInstrument, MSInstrumentType

# Register your models here.

admin.site.register(Producer)
admin.site.register(StoredFileType)
admin.site.register(MSInstrumentType)
admin.site.register(MSInstrument)
