from django.contrib.syndication.feeds import Feed
from django.utils.feedgenerator import Atom1Feed
from django.contrib.auth.models import Group

from life.models import Locale
from todo.models import Project, Todo

class Lens(object):
    def __init__(self, args):
        self.locale = None
        self.project = None
        self.owner = None
        self._props = []
        
        if args.has_key('locale'):
            self.locale = Locale.objects.get(code=args['locale'])
            self._props.append('locale')
        if args.has_key('project'):
            self.project = Project.objects.get(slug=args['project'])
            self._props.append('project')
        if args.has_key('owner'):
            self.owner = Group.objects.get(name=args['owner'])
            self._props.append('owner')
    
    def get_for_string(self):
        string = ''
        for prop in self._props:
            string += " for %s" % getattr(self, prop)
        return string
        
    def get_url_string(self):
        string = ''
        for prop in self._props:
            string += "%s:%s" % (prop, getattr(self, prop).code)
        return string

    def filter_queryset(self, q):
        filter_dict = {}
        for prop in self._props:
            filter_dict.update({prop: getattr(self, prop)})
        return q.filter(**filter_dict)
        
class NewTasksFeed(Feed):
    feed_type = Atom1Feed
    
    def get_object(self, bits):
        args = dict( [ bit.split(':') for bit in bits] )
        return Lens(args)

    def title(self, lens):
        title = "New tasks"
        title += lens.get_for_string()
        return title
        
    def subtitle(self, lens):
        subtitle = "New l10n tasks (product and web)" 
        subtitle += lens.get_for_string()
        return subtitle

    def link(self, lens):
        url = '/todo/feed/tasks/'
        url += lens.get_url_string()
        return url

    def item_link(self, task):
        return task.get_absolute_url()

    def items(self, lens):
        tasks = Todo.tasks.active()
        tasks = lens.filter_queryset(tasks)
        return tasks.order_by('-pk')[:30]

class NewNextActionsFeed(NewTasksFeed):
    pass