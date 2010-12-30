from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import permission_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404

from todo.models import Project, Task, Step
from todo.forms import *

@require_POST
@permission_required('todo.change_task')
def resolve_task(request, task_id):
    task = get_object_or_404(Task, pk=task_id)
    form = ResolveTaskForm(request.POST)
    if form.is_valid():
        redirect_url = form.cleaned_data['redirect_url']
        project_id = form.cleaned_data['project_id']
        project = get_object_or_404(Project, pk=project_id)
        task.resolve(request.user, project)
        return HttpResponseRedirect(redirect_url)
        
@require_POST
@permission_required('todo.change_step')
def resolve_step(request, step_id):
    step = get_object_or_404(Step, pk=step_id)
    if not step.is_review:
        form = ResolveSimpleStepForm(request.POST)
        if form.is_valid():
            redirect_url = form.cleaned_data['redirect_url']
            step.resolve(request.user)
            return HttpResponseRedirect(redirect_url)
    else:
        form = ResolveReviewStepForm(request.POST)
        if form.is_valid():
            redirect_url = form.cleaned_data['redirect_url']
            success = form.cleaned_data['success']
            resolution = 1 if success else 2
            step.resolve(request.user, resolution)
            return HttpResponseRedirect(redirect_url)
