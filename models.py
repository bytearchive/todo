from django.db import models
from django.contrib.auth.models import Group, User

from todo.proto.models import Prototype
from todo.managers import TodoManager, TaskManager, ProtoManager
from todo.workflow import statuses, STATUS_ADJ_CHOICES, STATUS_VERB_CHOICES, RESOLUTION_CHOICES
from todo.signals import todo_changed
    
from datetime import datetime

class Todo(models.Model):
    prototype = models.ForeignKey(Prototype, related_name='instances', null=True, blank=True)
    summary = models.CharField(max_length=200, blank=True)
    parent = models.ForeignKey('self', related_name='children', null=True, blank=True)
    owner = models.ForeignKey(Group, null=True, blank=True)
    order = models.PositiveIntegerField(null=True, blank=True)
    
    status = models.PositiveIntegerField(choices=STATUS_ADJ_CHOICES, default=1)
    resolution = models.PositiveIntegerField(choices=RESOLUTION_CHOICES, null=True, blank=True)
    
    is_auto_activated = models.BooleanField(default=False) #set on first
    is_review = models.BooleanField(default=False)
    resolves_parent = models.BooleanField(default=False) #set on last
    repeat_if_failed = models.BooleanField(default=False) #set on review action's parent
    
    objects = TodoManager()
    tasks = TaskManager()
    proto = ProtoManager()

    class Meta:
        ordering = ('order',)

    def __unicode__(self):
        return "%s" % (self.summary,) 

    def save(self):
        super(Todo, self).save()
        todo_changed.send(sender=self, user=User.objects.get(pk=1), action=self.status)
        
    def clone(self):
        return Todo.proto.clone(self, parent=self.parent, order=self.order)
        
    def resolve(self, resolution=1):
        self.status = 4
        self.resolution = resolution
        self.save()
        if not self.is_task:
            if self.resolves_parent or self.is_last:
                self.parent.resolve(self.resolution)
                if self.resolution == 2:
                    clone = self.parent.clone()
                    clone.activate()
            elif self.resolution == 1:
                self.next.activate()
            
    def activate(self):
        self.status = 2
        self.save()
        if self.has_children():
            self.activate_children()

    def activate_children(self):
        auto_activated_children = self.children.filter(is_auto_activated=True)
        if len(auto_activated_children) == 0:
            auto_activated_children = (self.children.get(order=1),)
        for child in auto_activated_children:
            child.status = 2
            child.save()
        
    def has_children(self):
        return len(self.children.all()) > 0    

    @property
    def next(self):
        try:
            next = self.order + 1
            return self.parent.children.get(order=next)
        except:
            return None

    @property
    def is_last(self):
        return self.next is None
        
    @property
    def is_task(self):
        return self.parent is None