from django.contrib import admin

from analysis.models import (NextflowWfVersion, NextflowWorkflow, Workflow,
                             Param, FileParam, PsetParam, PsetFileParam,
                             PsetPredefFileParam, WorkflowType, Proteowizard)


admin.site.register(NextflowWfVersion)
admin.site.register(NextflowWorkflow)
admin.site.register(WorkflowType)
admin.site.register(Workflow)
admin.site.register(PsetParam)
admin.site.register(PsetFileParam)
admin.site.register(PsetPredefFileParam)
admin.site.register(Param)
admin.site.register(FileParam)
admin.site.register(Proteowizard)
