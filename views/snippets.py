from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.template import RequestContext
from django.core.urlresolvers import reverse

from todo.models import Tracker, Task

def task(request, task, redirect_view='todo.views.demo.task'):
    """A single task view snippet.

    This snippet is intended to be included on a page showing a single task.
    The template includes all the necessary JS code, too.

    Arguments:
    task -- an instance of todo.models.Task
    redirect_view -- a string with the name of the view which will be used
                     to resolve the URL that the forms will redirect to.

    See todo.views.demo.task for an example of how to use this snippet.

    """
    redirect_url = reverse(redirect_view, args=[task.pk])
    return render_to_string('todo/snippet_task.html',
                            {'task': task,
                             'redirect_url': redirect_url,},
                            # RequestContext is needed for checking 
                            # the permissions of the user.
                            context_instance=RequestContext(request))

def showcase(request, project, locale, tasks_shown=5,
             task_view='todo.views.demo.task'):
    """A snippet to be included on the combined overview page.

    This snippet shows a short list of open tasks for a project+locale
    combination.

    Arguments:
    project -- an instance of todo.models.Project
    locale -- an instance of life.models.Locale
    tasks_shown -- a number of tasks to show
    task_view -- a string with the name of the `single task` view

    See todo.views.demo.combined for an example of how to use this snippet.

    """
    tasks = project.open_tasks(locale).order_by('-latest_resolution_ts')[:5]
    return render_to_string('todo/snippet_showcase.html',
                            {'tasks': tasks,
                             'task_view': task_view})

def tree(request, tracker=None, project=None, locale=None,
         task_view='todo.views.demo.task',
         tracker_view='todo.views.demo.tracker'):
    """A snippet to be included on a single tracker page.

    Arguments:
    tracker -- an instance of todo.models.Tracker. If given, project and locale
               are ignored.
    project -- an instance of todo.models.Project. ANDed with locale.
    locale -- an instance of life.models.Locale. ANDed with project.
    task_view -- a string with the name of the `single task` view
    tracker_view -- a string with the name of the `single tracker` view

    See todo.views.demo.tracker and todo.views.demo.trackers for examples of 
    how to use this snippet.

    """
    # FIXME: needs refactoring to reduce the number of queries.
    # Possible approach:
    #   start with a list of open tasks, via selected_related('parent')
    #   group them by parent
    #   get parents of the parents in a single query, again with 
    #     selected_related('parent')
    #   repeat until there's no parents left

    filters = {}
    if tracker is not None:
        trackers = (tracker,)
        tasks = []
    else:
        trackers = Tracker.objects
        tasks = Task.objects
        if project is not None:
            filters.update(projects=project)
            trackers = trackers.filter(projects=project)
            tasks = tasks.filter(projects=project)
        if locale is not None:
            filters.update(locale=locale)
            # return top-most trackers for the locale
            trackers = trackers.filter(locale=locale, parent__locale=None)
            # return top-most tasks for the locale
            tasks = tasks.filter(locale=locale, parent__locale=None)
        else:
            # return top-level trackers for the project
            trackers = trackers.filter(parent=None)
            # return top-level tasks for the project
            tasks = tasks.filter(parent=None)

    facets = {
        'projects': [],
        'locales': [],
        'statuses': [],
        'prototypes': [],
        'bugs': [],
        'trackers': [],
        'tracker_prototypes': [],
        'next_steps_owners': [],
        'next_steps': [],
    }
    tree, facets = _make_tree(filters, trackers, tasks, [], facets) 

    return render_to_string('todo/snippet_tree.html',
                            {'tree': tree,
                             'facets': facets,
                             'task_view': task_view,
                             'tracker_view': tracker_view},
                            # RequestContext is needed for checking 
                            # the permissions of the user.
                            context_instance=RequestContext(request))

def _update_facets(facets, task_properties):
    "Update facet data with properties of a task."

    for prop, val in task_properties.iteritems():
        facets[prop].extend(val)
        facets[prop] = list(set(facets[prop])) # uniquify the list
    return facets

def _make_tree(filters, trackers, tasks, tracker_chain, facets):
    """Construct the data tree about requested trackers.

    The function recursively iterates over the given list of trackers
    to create a data hierarchy with information about each tracker and
    task. This is done so that all the necessary data is avaiable before 
    the template is rendered, which in turn allows to populate the facets
    used to navigate the tracker tree.

    Arguments:
    filters --
    trackers -- an iterable of todo.models.Tracker instances that that tree
                will be constructed for.
    tasks -- an iterable of todo.models.Tracker instances that that tree
             will be constructed for.
    tracker_chain -- a list of prototype names of tracker which were already
                     analyzed in the recursion. This is used to give tasks 
                     a 'path' of trackers above them.
    facets -- a dict with facet data.

    """
    # FIXME: The function works its way from the top to the bottom of the 
    # tracker structure, which results in tons of queries being made. 
    # A possible solution, as mentioned in todo.views.snippets.tree, might
    # be to start from the tasks and go up.

    tree = {'trackers': {}, 'tasks': {}}
    for tracker in trackers:
        child_trackers = tracker.children_all()
        if 'projects' in filters:
            child_trackers = child_trackers.filter(projects=filters['projects'])
        if 'locale' in filters:
            child_trackers = child_trackers.filter(locale=filters['locale'])
        subtree, facets = _make_tree(filters,
                                     child_trackers,
                                     tracker.tasks.all(),
                                     tracker_chain + [tracker],
                                     facets)
        tree['trackers'].update({tracker: subtree}) 
    for task in tasks:
        task_properties = {
            'projects': [unicode(p) for p in task.projects.all()],
            'locales': [unicode(task.locale)],
            'statuses': ['%s for %s' % 
                       (s.get_status_display(), unicode(s.project)) for s in
                       task.statuses.all()],
            'prototypes': [task.prototype.summary],
            'bugs': [task.bugid],
            'trackers': [t.summary for t in tracker_chain],
            'tracker_prototypes': [t.prototype.summary for t in 
                                   tracker_chain if t.prototype],
            'next_steps': [unicode(step) for step in task.next_steps()],
            'next_steps_owners': [unicode(step.owner)
                                  for step in task.next_steps()],
        }
        tree['tasks'].update({task: task_properties})
        facets = _update_facets(facets, task_properties)
    return tree, facets
