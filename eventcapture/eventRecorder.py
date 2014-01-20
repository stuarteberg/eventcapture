from PyQt4.QtCore import pyqtSignal
from PyQt4.QtCore import Qt, QObject, QEvent, QChildEvent, QTimerEvent
from PyQt4.QtGui import QApplication, QMouseEvent, QGraphicsSceneMouseEvent, QWindowStateChangeEvent, QMoveEvent, QCursor, QComboBox, QMenu

from objectNameUtils import get_fully_qualified_name, get_named_object, NamedObjectNotFoundError, Signaler
from eventSerializers import event_to_string
from eventTypeNames import EventTypes

from timer import Timer

import functools
import gc
import threading
import logging
logger = logging.getLogger(__name__)

_orig_QApp_notify = functools.partial( QApplication.notify, QApplication.instance() )

class EventFlusher(QObject):
    SetEvent = QEvent.Type(QEvent.registerEventType())

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._state = threading.Event()

    def event(self, e):
        if e.type() == EventFlusher.SetEvent:
            assert threading.current_thread().name == "MainThread"
            self.set()
            return True
        return False

    def eventFilter(self, watched, event):
        return self.event(event)

    def set(self):
        QApplication.sendPostedEvents()
        QApplication.processEvents()
        QApplication.flush()
        assert not self._state.is_set()
        self._state.set()
        
    def clear(self):
        self._state.clear()

    def wait(self):
        assert threading.current_thread().name != "MainThread"
        self._state.wait()

class EventPlayer(object):
    def __init__(self, playback_speed=None, comment_display=None):
        self._playback_speed = playback_speed
        self._timer = Timer()
        self._timer.unpause()
        if comment_display is None:
            self._comment_display = self._default_comment_display
        else:
            self._comment_display = comment_display

    def play_script(self, path, finish_callback=None):
        """
        Start execution of the given script in a separate thread and return immediately.
        Note: You should handle any exceptions from the playback script via sys.execpthook.
        """
        _globals = {}
        _locals = {}
        """ 
        Calls to events in the playback script like: player.post_event(obj,PyQt4.QtGui.QMouseEvent(...),t)
        are/were responsible for the xcb-error on Ubuntu, because you may not use
        a Gui-object from a thread other than the MainThread running the Gui
        """
        execfile(path, _globals, _locals)
        def run():
            _locals['playback_events'](player=self)
            if finish_callback is not None:
                finish_callback()
        th = threading.Thread( target=run )
        th.daemon = True
        th.start()
    
    def post_event(self, obj_name, event, timestamp_in_seconds):
        # Remove any lingering widgets (which might have conflicting names with our receiver)
        gc.collect()
        
        try:
            # Locate the receiver object.
            obj = get_named_object(obj_name)
        except NamedObjectNotFoundError:
            # If the object couldn't be found, check to see if this smells 
            # like a silly mouse-move event that was sent after a window closed.
            if event.type() == QEvent.MouseMove \
                and int(event.button()) == 0 \
                and int(event.buttons()) == 0 \
                and int(event.modifiers()) == 0:
                # Just proceed. We shouldn't raise an exception just because we failed to 
                # deliver a pointless mouse-movement to a widget that doesn't exist anymore.
                return
            elif event.type() == QEvent.KeyRelease:
                # Sometimes we try to send a KeyRelease to a just-closed dialog.
                # Ignore errors from such cases.
                return
            elif event.type() == QEvent.Wheel:
                # Also don't freak out if we can't find an object that is supposed to be receiving wheel events.
                # If there's a real problem, it will be noticed that object is sent a mousepress or key event.
                return
            else:
                # This isn't a plain mouse-move.
                # It was probably important, and something went wrong.
                raise

        if self._playback_speed is not None:
            self._timer.sleep_until(timestamp_in_seconds / self._playback_speed)
        assert threading.current_thread().name != "MainThread"
        event.spont = True
        QApplication.postEvent(obj, event)
        assert QApplication.instance().thread() == obj.thread()
        
        flusher = EventFlusher()
        flusher.moveToThread( obj.thread() )
        flusher.setParent( QApplication.instance() )
    
        signaler = Signaler()
        signaler.sig.connect( flusher.set, Qt.QueuedConnection )
        signaler.sig.emit()
        flusher.wait()
        flusher.clear()

    def display_comment(self, comment):
        self._comment_display(comment)

    def _default_comment_display(self, comment):
        print "--------------------------------------------------"
        print comment
        print "--------------------------------------------------"

def has_ancestor(obj, object_type):
    # Must call QObject.parent this way because obj.parent() is *shadowed* in 
    #  some subclasses (e.g. QModelIndex), which really is very ugly on Qt's part.
    parent = QObject.parent( obj )
    if parent is None:
        return False
    if isinstance( parent, object_type ):
        return True
    return has_ancestor( parent, object_type )

class EventRecorder( QObject ):
    """
    Records spontaneous events from the UI and serializes them as strings that can be evaluated in Python.
    """
    def __init__(self, parent=None, ignore_parent_events=True):
        QObject.__init__(self, parent=parent)
        self._ignore_parent_events = False
        if parent is not None and ignore_parent_events:
            self._ignore_parent_events = True
            self._parent_name = get_fully_qualified_name(parent)
        self._captured_events = []
        self._timer = Timer()

    @property
    def paused(self):
        return self._timer.paused

    IgnoredEventTypes = set( [ QEvent.Paint,
                              QEvent.KeyboardLayoutChange,
                              QEvent.WindowActivate,
                              QEvent.WindowDeactivate,
                              QEvent.ActivationChange,
                              QEvent.FileOpen,
                              # These event symbols are not exposed in pyqt, so we pull them from our own enum
                              EventTypes.Style,
                              EventTypes.ApplicationActivate,
                              EventTypes.ApplicationDeactivate,
                              EventTypes.NonClientAreaMouseMove,
                              EventTypes.NonClientAreaMouseButtonPress,
                              EventTypes.NonClientAreaMouseButtonRelease,
                              EventTypes.NonClientAreaMouseButtonDblClick
                               ] )
    IgnoredEventClasses = (QChildEvent, QTimerEvent, QGraphicsSceneMouseEvent, QWindowStateChangeEvent, QMoveEvent)

    def captureEvent(self, watched, event):
        if self._shouldSaveEvent(event):
            try:
                eventstr = event_to_string(event)
            except KeyError:
                logger.warn("Don't know how to record event: {}".format( str(event) ))
                print "Don't know how to record", str(event)
            else:
                # Perform a full garbage collection before determining the name of this widget
                gc.collect()
                timestamp_in_seconds = self._timer.seconds()
                objname = str(get_fully_qualified_name(watched))
                if not ( self._ignore_parent_events and objname.startswith(self._parent_name) ):
                    self._captured_events.append( (eventstr, objname, timestamp_in_seconds) )
        return False

    def insertComment(self, comment):
        self._captured_events.append( (comment, "comment", None) )

    def _shouldSaveEvent(self, event):
        if isinstance(event, QMouseEvent):
            # Ignore most mouse movement events if the user isn't pressing anything.
            if event.type() == QEvent.MouseMove \
                and int(event.button()) == 0 \
                and int(event.buttons()) == 0 \
                and int(event.modifiers()) == 0:

                # If mouse tracking is enabled for this widget, 
                #  then we'll assume mouse movements are important to it.
                widgetUnderCursor = QApplication.instance().widgetAt( QCursor.pos() )
                if widgetUnderCursor is not None and widgetUnderCursor.hasMouseTracking():
                    return True

                # Somewhat hackish (and slow), but we have to record mouse movements during combo box usage.
                # Same for QMenu usage (on Mac, it doesn't seem to matter, but on Fedora it does matter.)
                if widgetUnderCursor is not None and widgetUnderCursor.objectName() == "qt_scrollarea_viewport":
                    return has_ancestor(widgetUnderCursor, QComboBox)
                if isinstance(widgetUnderCursor, QMenu):
                    return True
                return False
            else:
                return True
        
        # Ignore non-spontaneous events
        if not event.spontaneous():
            return False
        if event.type() in self.IgnoredEventTypes:
            return False
        if isinstance(event, self.IgnoredEventClasses):
            return False
        return True

    def unpause(self):
        # Here, we use a special override of QApplication.notify() instead of using QApplication.instance().installEventFilter().
        # That's because (contrary to the documentation), the QApplication eventFilter does NOT get to see every event in the application.
        # Testing shows that events that were "filtered out" by a different event filter may not be seen by the QApplication event filter.
        self._timer.unpause()

        def _notify(receiver, event):
            self.captureEvent(receiver, event)
            return _orig_QApp_notify(receiver, event)

        from eventRecordingApp import EventRecordingApp
        assert isinstance( QApplication.instance(), EventRecordingApp )
        QApplication.instance()._notify =_notify

    def pause(self):
        self._timer.pause()
        QApplication.instance()._notify = _orig_QApp_notify
    
    def writeScript(self, fileobj, author_name):
        # Write header comments
        fileobj.write(
"""
# Event Recording
# Created by {}
# Started at: {}
""".format( author_name, str(self._timer.start_time) ) )

        # Write playback function definition
        fileobj.write(
"""
def playback_events(player):
    import PyQt4.QtCore
    from PyQt4.QtCore import Qt, QEvent, QPoint
    import PyQt4.QtGui
    
    # The getMainWindow() function is provided by EventRecorderApp
    mainwin = PyQt4.QtGui.QApplication.instance().getMainWindow()

    player.display_comment("SCRIPT STARTING")

""")

        # Write all events and comments
        for eventstr, objname, timestamp_in_seconds in self._captured_events:
            if objname == "comment":
                eventstr = eventstr.replace('\\', '\\\\')
                eventstr = eventstr.replace('"', '\\"')
                eventstr = eventstr.replace("'", "\\'")
                fileobj.write(
"""
    ########################
    player.display_comment(\"""{eventstr}\""")
    ########################
""".format( **locals() ) )
            else:
                fileobj.write(
"""
    event = {eventstr}
    player.post_event( '{objname}', event , {timestamp_in_seconds} )
""".format( **locals() )
)
        fileobj.write(
"""
    player.display_comment("SCRIPT COMPLETE")
""")

    
