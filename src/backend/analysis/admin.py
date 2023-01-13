from django.contrib import admin

from analysis.models import (NextflowWfVersion, NextflowWorkflow, Workflow, ParameterSet,
                             Param, FileParam, PsetParam, PsetFileParam, PsetMultiFileParam,
                             ParamOption, PsetPredefFileParam, WorkflowType, Proteowizard,
                             WFInputComponent, PsetComponent, WfOutput)


admin.site.register(NextflowWfVersion)
admin.site.register(NextflowWorkflow)
admin.site.register(WorkflowType)
admin.site.register(Workflow)
admin.site.register(WFInputComponent)
admin.site.register(PsetComponent)
admin.site.register(ParameterSet)
admin.site.register(PsetParam)
admin.site.register(PsetFileParam)
admin.site.register(PsetMultiFileParam)
admin.site.register(PsetPredefFileParam)
admin.site.register(Param)
admin.site.register(ParamOption)
admin.site.register(FileParam)
admin.site.register(Proteowizard)

admin.site.register(WfOutput)
