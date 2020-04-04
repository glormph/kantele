from django.contrib import admin

from analysis.models import (NextflowWfVersion, NextflowWorkflow, Workflow,
                             Param, FileParam, WorkflowParam, WorkflowFileParam,
                             WorkflowPredefFileParam, WorkflowType, Proteowizard)


admin.site.register(NextflowWfVersion)
admin.site.register(NextflowWorkflow)
admin.site.register(WorkflowType)
admin.site.register(Workflow)
admin.site.register(WorkflowParam)
admin.site.register(WorkflowFileParam)
admin.site.register(WorkflowPredefFileParam)
admin.site.register(Param)
admin.site.register(FileParam)
admin.site.register(Proteowizard)
