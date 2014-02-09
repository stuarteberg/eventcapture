from PyQt4.QtCore import QObject, QEvent, QChildEvent, QTimerEvent
from PyQt4.QtGui import QApplication, QMouseEvent, QGraphicsSceneMouseEvent, QWindowStateChangeEvent, QMoveEvent, QCursor, QComboBox, QMenu

from objectNameUtils import get_fully_qualified_name
from eventSerializers import event_to_string
from eventTypeNames import EventTypes
from eventRecordingApp import EventRecordingApp

from timer import Timer

import gc
import logging
logger = logging.getLogger(__name__)

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
        
        assert isinstance(QApplication.instance(), EventRecordingApp)
        QApplication.instance().aboutToNotify.connect( self.handleApplicationEvent )

    def handleApplicationEvent(self, receiver, event):
        if not self.paused:
            self.captureEvent(receiver, event)

    @property
    def paused(self):
        return self._timer.paused

    IgnoredEventTypes = set( [ QEvent.Paint,
                              QEvent.KeyboardLayoutChange,
                              QEvent.WindowActivate,
                              QEvent.WindowDeactivate,
                              QEvent.ActivationChange,
                              QEvent.FileOpen,
                              QEvent.Clipboard,
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

    def pause(self):
        self._timer.pause()
    
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

    
