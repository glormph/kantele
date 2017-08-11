from django.contrib import admin

from datasets.models import HiriefRange, Datatype, PrincipalInvestigator

# Register your models here.

admin.site.register(HiriefRange)
admin.site.register(Datatype)
admin.site.register(PrincipalInvestigator)
