from django.contrib import admin

from datasets.models import (Datatype, PrincipalInvestigator, DatatypeComponent,
                             SelectParameter, SelectParameterOption,
                             CheckboxParameter, CheckboxParameterOption,
                             FieldParameter, SampleMaterialType,
                             Enzyme, QuantType, QuantChannel, QuantTypeChannel,
                             Operator, Prefractionation, HiriefRange,
                             )

# Register your models here.

admin.site.register(FieldParameter)
admin.site.register(SelectParameter)
admin.site.register(SelectParameterOption)
admin.site.register(CheckboxParameter)
admin.site.register(CheckboxParameterOption)
admin.site.register(HiriefRange)
admin.site.register(Datatype)
admin.site.register(PrincipalInvestigator)
admin.site.register(Enzyme)
admin.site.register(SampleMaterialType)
admin.site.register(QuantType)
admin.site.register(QuantChannel)
admin.site.register(QuantTypeChannel)
admin.site.register(Operator)
admin.site.register(Prefractionation)
admin.site.register(DatatypeComponent)
