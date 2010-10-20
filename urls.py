from django.conf.urls.defaults import *
from todo.forms.new import (CreateNewWizard, ChooseProjectLocaleForm,
                            ChoosePrototypeForm, ChooseParentFactory)

action_patterns = patterns('todo.views.actions',
    (r'^resolve/task/(?P<task_id>\d+)$', 'resolve_task'),
    (r'^resolve/step/(?P<step_id>\d+)$', 'resolve_step'),
)

# the API views return JSON responses
api_patterns = patterns('todo.views.api',
    (r'^step/(?P<step_id>\d+)/reset-time$', 'reset_time'),
    (r'^task/(?P<task_id>\d+)/update-snapshot$', 'update_snapshot'),
    (r'^task/(?P<task_id>\d+)/update-bugid$', 'update_bugid'),
    (r'^task/(?P<obj_id>\d+)/update$', 'update', {'obj': 'task'},
     'todo-api-update-task'),
    (r'^tracker/(?P<obj_id>\d+)/update$', 'update', {'obj': 'tracker'},
     'todo-api-update-tracker'),
)

new_patterns = patterns('',
    (r'^$', CreateNewWizard([ChooseProjectLocaleForm, ChoosePrototypeForm,
                             ChooseParentFactory()])),
)

# demo views are used for testing and as an example for the real views
# that an application wishing to have todo needs to implement
demo_patterns = patterns('todo.views.demo',
    (r'^task/(?P<task_id>\d+)$', 'task'),
    (r'^showcase$', 'showcase'),
    (r'^tracker/(?P<tracker_id>\d+)$', 'tracker'),
    (r'^trackers$', 'trackers'),
)

urlpatterns = patterns('',
    # includes
    (r'^new/', include(new_patterns)),
    (r'^action/', include(action_patterns)),
    (r'^api/', include(api_patterns)),
    (r'^demo/', include(demo_patterns)),
)
