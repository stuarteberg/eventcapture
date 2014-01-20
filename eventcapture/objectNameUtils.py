import time
import threading

import sip
from PyQt4.QtCore import QObject, QTimer
from PyQt4.QtGui import QApplication, QWidget, QMenu, QPushButton

class MainThreadPausedContext(QObject):
    def __init__(self, *args, **kwargs):
        super(MainThreadPausedContext, self).__init__(*args, **kwargs)
        self.moveToThread( QApplication.instance().thread() )
        self._paused_event = threading.Event()
        self._pauser = threading.Event()

    def _suspend_main(self):
        self._paused_event.set()
        self._pauser.wait()

    def __enter__(self):
        if threading.current_thread().name == "MainThread":
            return

        # Schedule the suspend func to execute on the main thread
        # Note: We are allowed to use QTimer outside of the main thread like this 
        #        because the target function belongs to a QObject
        QTimer.singleShot(0, self._suspend_main)

        # Wait until the main thread entered the suspend func
        self._paused_event.wait()

    def __exit__(self, *args):
        if threading.current_thread().name == "MainThread":
            return

        # Allow the main thread to exit the suspend func
        self._pauser.set()

def get_toplevel_widgets():
    """
    Get all "top-level" widgets EXCEPT:
    - Exclude QMenus (due to a bug in Qt, and besides, they are accessible via the 'normal' mechanism)
    - Exclude widgets that are already deleted on the C++ side
    - Exclude widgets that aren't visible
    """
    toplevel_widgets = QApplication.topLevelWidgets()
    toplevel_widgets = filter( lambda w: not isinstance(w, QMenu), toplevel_widgets )
    toplevel_widgets = filter( lambda w: not sip.isdeleted(w), toplevel_widgets )
    toplevel_widgets = filter( lambda w: w.isVisible(), toplevel_widgets )
    #toplevel_widgets = filter( lambda w: w is not None, toplevel_widgets)
    return toplevel_widgets


def get_fully_qualified_name(obj):
    """
    Return a fully qualified object name of the form: someobject.somechild.somegrandchild.etc
    Before returning, this function **renames** any children that don't have unique names within their parent.

    Note: The name uniqueness check and renaming algorithm are terribly inefficient, 
          but it doesn't seem to slow things down much.  We could improve this later if it becomes a problem.
    """
    with MainThreadPausedContext():
        # Must call QObject.parent this way because obj.parent() is *shadowed* in 
        #  some subclasses (e.g. QModelIndex), which really is very ugly on Qt's part.
        parent = QObject.parent(obj)
        objName = obj.objectName()
        if objName == "":
            _assign_default_object_name(obj)
        if not _has_unique_name(obj):
            _normalize_child_names(parent)
        
        objName = str(obj.objectName())
        
        # We combine object names using periods, which means they better not have periods themselves...
        assert objName.find('.') == -1, "Objects names must not use periods!  Found an object named: {}".format( objName )
    
        if parent is None:
            return objName
        
        fullname = "{}.".format( get_fully_qualified_name(parent) ) + objName
    
        # Make sure no siblings have the same name!
        assert _has_unique_name(obj), "Detected multiple objects with full name: {}".format( fullname )
    
        return fullname

class NamedObjectNotFoundError(Exception):
    pass

def get_named_object(full_name, timeout=5.0):
    """
    Locate the object with the given fully qualified name.
    While searching for the object, actively **rename** any objects that do not have unique names within their parent.
    Since the renaming scheme is consistent with get_fully_qualified name, we should always be able to locate the target object, even if it was renamed when the object was originally recorded.
    """
    timeout_ = timeout
    with MainThreadPausedContext():
        obj = _locate_descendent(None, full_name)
    while obj is None and timeout > 0.0:
        time.sleep(1.0)
        timeout -= 1.0
        with MainThreadPausedContext():
            obj = _locate_descendent(None, full_name)
    
    ancestor_name = None
    if obj is None:
        # We couldn't find the child.
        # To give a better error message, find the deepest object that COULD be found
        names = full_name.split('.')
        for i in range(len(names)-1):
            ancestor_name = ".".join( names[:-i-1] )
            with MainThreadPausedContext():
                obj = _locate_descendent(None, ancestor_name)
            if obj is not None:
                break
            else:
                ancestor_name = None

        msg = "Couldn't locate object: {} within timeout of {} seconds\n".format( full_name, timeout_ )
        if ancestor_name:
            msg += "Deepest found object was: {}\n".format( ancestor_name )
            msg += "Existing children were: {}".format( map(QObject.objectName, obj.children()) )
        else:
            msg += "Failed to find the top-level widget {}".format( full_name.split('.')[0] )
        raise NamedObjectNotFoundError( msg )
    return obj

def assign_unique_child_index( child ):
    """
    Assign a unique 'child index' to this child AND all its siblings of the same type.
    """
    # Must call QObject.parent this way because obj.parent() is *shadowed* in 
    #  some subclasses (e.g. QModelIndex), which really is very ugly on Qt's part.
    parent = QObject.parent(child)
    # Find all siblings of matching type
    if parent is not None:
        matching_siblings = filter( lambda c:type(c) == type(child), parent.children() )
    else:
        matching_siblings = filter( lambda c:type(c) == type(child), get_toplevel_widgets() )

    matching_siblings = filter( lambda w: w is not None, matching_siblings)
    matching_siblings = filter(lambda w: not sip.isdeleted(w), matching_siblings)
    existing_indexes = set()
    for sibling in matching_siblings:
        if hasattr(sibling, 'unique_child_index'):
            existing_indexes.add(sibling.unique_child_index)
    
    next_available_index = 0
    for sibling in matching_siblings:
        while next_available_index in existing_indexes:
            next_available_index += 1
        if not hasattr(sibling, 'unique_child_index'):
            sibling.unique_child_index = next_available_index
            existing_indexes.add( next_available_index )

def _assign_default_object_name( obj ):
    # Ensure that this object and its siblings have a child index
    assign_unique_child_index(obj)
    
    if type(obj) == QPushButton and hasattr(obj, 'unique_child_index') and obj.unique_child_index == 0:
        assign_unique_child_index(obj)
    
    # Find all siblings (including this object) that appear to have auto-defined names
    parent = QObject.parent(obj)
    # Find all siblings of matching type
    if parent is not None:
        siblings = filter( lambda c:type(c) == type(obj), parent.children() )
        siblings = filter(lambda w: not sip.isdeleted(w), siblings)
    else:
        siblings = filter( lambda c:type(c) == type(obj), get_toplevel_widgets() )

    if obj not in siblings:
        # Special case for top-level widgets, since not all of its 'siblings' are included included in get_toplevel_widgets()
        index_among_default_names = obj.unique_child_index
    else:
        siblings = filter( lambda c: c.objectName() == "" or str(c.objectName()).startswith( '{}_'.format( obj.__class__.__name__ ) ), siblings )
        if obj not in siblings:
            siblings.append(obj)
            siblings = sorted( siblings, key=lambda c: c.unique_child_index )
        index_among_default_names = siblings.index( obj )
    
    newname = '{}_{}'.format( obj.__class__.__name__, index_among_default_names )
    obj.setObjectName( newname )

def _has_unique_name(obj):
    if obj.objectName() == '':
        return False
    # Must call QObject.parent this way because obj.parent() is *shadowed* in 
    #  some subclasses (e.g. QModelIndex), which really is very ugly on Qt's part.
    parent = QObject.parent(obj)
    if parent is None:
        siblings = get_toplevel_widgets()
    else:
        siblings = parent.children()        
        siblings = filter( lambda w: w is not None, siblings)
        siblings = filter(lambda w: not sip.isdeleted(w), siblings)
    obj_name = obj.objectName()
    for child in siblings:
        if child is not obj and child.objectName() == obj_name:
            return False
    return True

def _normalize_child_names(parent):
    """
    Make sure no two children of parent have the same name.
    If two children have the same name, only rename the second one.
    """
    if parent is None:
        # For top-level widgets, we can't 'normalize' the names because we can't count on 
        #  QApplication.topLevelWidgets() to return a consistent order (I think)
        # Instead of normalizing widget names, we'll check for problems.
        toplevel_widgets = get_toplevel_widgets()
        existing_names = set()
        for child in toplevel_widgets:
            assert child.objectName() not in existing_names, \
                "Top-level widgets (i.e. widgets without a parent) MUST have unique names.  "\
                "I found multiple top-level widgets named '{}'".format( child.objectName() )
    else:
        children = parent.children()        
        existing_names = set()
        for child in children:
            if child.objectName() in existing_names:
                _assign_default_object_name(child)
            existing_names.add( child.objectName() )

def _locate_immediate_child(parent, childname):
    if parent is None:
        assert childname != "", "top-level widgets must have names!"
        siblings = get_toplevel_widgets()
    else:
        siblings = parent.children()
        siblings = filter( lambda w: w is not None, siblings)
        siblings = filter(lambda w: not sip.isdeleted(w), siblings)
        # Only consider visible children (or non-widgets)
        def isVisible(obj):
            return not isinstance(obj, QWidget) or obj.isVisible()
        siblings = filter( isVisible, siblings )

    for child in siblings:
        if child.objectName() == "":
            _assign_default_object_name(child)
        if parent is not None and not _has_unique_name(child):
            _normalize_child_names(parent)
        if child.objectName() == childname:
            return child
    return None

def _locate_descendent(parent, full_name):
    names = full_name.split('.')
    assert names[0] != ''
    child = _locate_immediate_child(parent, names[0])
    if len(names) == 1:
        return child
    else:
        return _locate_descendent( child, '.'.join(names[1:]) )
