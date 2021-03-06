# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla todo app.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Stas Malolepszy <stas@mozilla.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.template import RequestContext
from django.core.urlresolvers import reverse

from todo.models import Tracker, Task, Step, TaskInProject
from todo.workflow import NEXT

from itertools import groupby

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
    div = render_to_string('todo/snippet_task.html',
                           {'task': task,
                            'redirect_url': redirect_url,},
                           # RequestContext is needed for checking 
                           # the permissions of the user.
                           context_instance=RequestContext(request))
    return {
        'div': mark_safe(div),
    }

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
    tasks = project.open_tasks(locale).order_by('-latest_resolution_ts')
    # Force-evaluate the query before it is used in `task__in` filter below.  
    # This is needed because MySQL 5.1 doesn't support LIMIT and IN in one 
    # query.
    tasks = list(tasks[:tasks_shown])
    # instead of querying for next steps for every tasks separately, get all 
    # next steps for the current tasks and group them by task
    next_steps = {}
    step_objects = Step.objects.select_related('task').order_by('task')
    flat_next_steps = step_objects.filter(task__in=tasks, status=NEXT)
    for task, steps in groupby(flat_next_steps, lambda s: s.task):
        next_steps[task] = list(steps)
    for task in tasks:
        try:
            task.next_steps = next_steps[task]
        except KeyError:
            task.next_steps = []
    div = render_to_string('todo/snippet_showcase.html',
                           {'tasks': tasks,
                            'task_view': task_view})
    return {
        'empty': not bool(tasks),
        'div': mark_safe(div),
    }

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
    tracker_objects = Tracker.objects.select_related('parent')
    task_objects = Task.objects.select_related('parent')
    step_objects = Step.objects.select_related('task').order_by('task')
    status_objects = TaskInProject.objects.select_related('task', 'project')
    status_objects = status_objects.order_by('task')

    if tracker is not None:
        trackers = (tracker,)
        tasks = []
    else:
        # call `all` to get a new queryset to work with
        trackers = tracker_objects.all()
        tasks = task_objects.all()
        # trackers come in 3 types:
        # 1. no projects, no locale -- so-called 'generic' trackers
        # 2. projects, no locale
        # 3. projects, locale
        if project is not None:
            # requesting type 2 or 3
            trackers = trackers.filter(projects=project)
            tasks = tasks.filter(projects=project)
        if locale is not None:
            # requesting type 3
            # return top-most trackers/tasks for the locale
            trackers = trackers.filter(locale=locale, parent__locale=None)
            tasks = tasks.filter(locale=locale, parent__locale=None)
        else:
            # requesting type 2
            # return top-most trackers/tasks for the project
            trackers = trackers.filter(parent__projects=None)
            tasks = tasks.filter(parent__projects=None)
    # force-evaluate the querysets to reduce queries' amount and complexity;
    # bool() and while are faster for lists and passing a list to a 
    # `filter(task__in=tasks` results in a simple WHERE ... IN (id1, id2, etc) 
    # instead of an extra JOIN.
    trackers = list(trackers)
    tasks = list(tasks)
    # is there anything to show?
    empty = not (bool(trackers) or bool(tasks))

    # these dicts will be used to store objects returned by the queries
    cache = {}
    next_steps = {}
    statuses = {}
    # the depth of the tree, used as a loop's counter in step 2 below
    depth = 0

    # 1. retrive all trackers and tasks in the tree and store them as flat
    #    lists; for each level in the tree, get next steps for tasks
    while trackers or tasks:
        for tracker in trackers:
            cache[tracker] = {
                'trackers': {},
                'tasks': {},
            }
        for task in tasks:
            cache[task] = {}
        # get all next steps for the current tasks and group them by task
        flat_next_steps = step_objects.filter(task__in=tasks, status=NEXT)
        for task, steps in groupby(flat_next_steps, lambda s: s.task):
            next_steps[task] = list(steps)
        # get all statuses for the current tasks and group them by task
        flat_statuses = status_objects.filter(task__in=tasks)
        for task, task_statuses in groupby(flat_statuses, lambda s: s.task):
            statuses[task] = list(task_statuses)
        # prepare for the loop's next run
        tasks = list(task_objects.filter(parent__in=trackers))
        trackers = list(tracker_objects.filter(parent__in=trackers))
        depth += 1

    # 2. iterate over the cache a couple of times and group retrived trackers
    #    and tasks into a tree-like structure
    tree = {
        'trackers': {},
        'tasks': {},
    }
    while depth:
        # The key to understanding how this loop works is the fact that nothing
        # is removed from the `cache` at any point.  The `depth` variable makes
        # sure the loop runs enough times to include all relations in the
        # structure.
        keys = sorted(cache.keys(), key=lambda k: k.parent)
        for parent, children in groupby(keys, lambda k: k.parent):
            for child in children:
                if parent is None or parent not in cache:
                    # if there is no parent or the parent is outside of the 
                    # scope of displayed trackers and tasks (e.g. a generic
                    # tracker which is not assigned to any projects while we're
                    # displaying trackers specific to a certain project), 
                    # store the child as a top-level node directly in `tree`.
                    parent_node = tree
                else:
                    parent_node = cache[parent]
                # put the child under its parent; the first time the loop 
                # executes, `cache[child]` is just an empty dict for all
                # children. In the following runs, however, it contains
                # a subtree of trackers and tasks grouped by the loop before.
                if isinstance(child, Tracker):
                    parent_node['trackers'][child] = cache[child]
                else:
                    parent_node['tasks'][child] = cache[child]
        depth -= 1

    # 3. recurse into the tree to retrieve the meta data about the tasks and
    #    store it in the tree (in corresponding task dicts) and as the facets
    facets = {
        'projects': [],
        'locales': [],
        'statuses': [],
        'prototypes': [],
        'bugs': [],
        'trackers': [],
        'next_steps_owners': [],
        'next_steps': [],
    }

    def _get_facet_data(tree, tracker_chain=[]):
        """Retrive meta data for every task in the tree.

        The function recurses into a tree of trackers and tasks and retrieves
        information about every task it finds.  The data gathered this way is
        then stored in corresponding tasks' dicts in the tree.  It is also used
        to prepare data for the faceted interface that will allow to filter the
        tree.

        Arguments:
            tree -- a tree-like structure of dicts representing a hierarchy of
                    trackers and tasks
            tracker_chain -- a list of prototype names of trackers which were
                             already analyzed in the recursion. This is used to
                             give tasks a breadcrumbs-like 'path' of trackers
                             above them.

        """
        for tracker, subtree in tree['trackers'].iteritems():
            subtree = _get_facet_data(subtree, tracker_chain + [tracker])
            tree['trackers'][tracker] = subtree 
        for task in tree['tasks'].keys():
            try:
                task.next_steps = next_steps[task]
            except KeyError:
                # the task might be inactive or resolved, and thus might have 
                # no next steps
                task.next_steps = []
            task_properties = {
                'projects': [unicode(s.project) for s in statuses[task]],
                'locales': [task.locale_repr],
                'statuses': ['%s for %s' % 
                             (s.get_status_display(), unicode(s.project))
                             for s in statuses[task]],
                'prototypes': [task.prototype_repr],
                'bugs': [task.bugid],
                'trackers': [t.summary for t in tracker_chain],
                'next_steps': [unicode(step) for step in task.next_steps],
                'next_steps_owners': [step.owner_repr
                                      for step in task.next_steps],
            }
            # call this now so that when it's called from the template, the
            # cached value is used
            task.is_resolved_all(statuses[task])
            tree['tasks'][task] = task_properties
            # Update facet data with properties of the task.
            for prop, val in task_properties.iteritems():
                facets[prop].extend(val)
                facets[prop] = list(set(facets[prop])) # uniquify the list
        return tree

    tree = _get_facet_data(tree)
    # sort the facets alphabetically
    for k, v in facets.iteritems():
        facets[k] = sorted(v)

    div = render_to_string('todo/snippet_tree.html',
                           {'tree': tree,
                            'facets': facets,
                            'task_view': task_view,
                            'tracker_view': tracker_view},
                           # RequestContext is needed for checking 
                           # the permissions of the user.
                           context_instance=RequestContext(request))
    return {
        'empty': empty,
        'div': mark_safe(div),
    }
