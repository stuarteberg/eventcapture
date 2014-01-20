import functools
from PyQt4.QtCore import Qt, QEvent, QTimer
from PyQt4.QtGui import QApplication, QWidget, QMainWindow

from objectNameUtils import assign_unique_child_index

class EventRecordingApp(QApplication):
    """
    Special QApplication subclass that overrides the notify() function.
    Using notify() instead of QApplication.instance().installEventFilter() is more general,
    and necessary for our purposes.
    """
    def __init__(self, *args, **kwargs):
        super(EventRecordingApp, self).__init__(*args, **kwargs)
        self._notify = functools.partial( QApplication.notify, QApplication.instance() )

        # Lazy import here because there can be subtle problems 
        #  if this is imported BEFORE the app is created.
        from eventcapture.eventRecorderGui import EventRecorderGui

        # We keep the recorder control window as a member of the app 
        # to ensure that it isn't deleted while the app is alive
        # (It does not belong to the MainWindow.)        
        self.recorder_control_window = EventRecorderGui()
    
    def notify(self, receiver, event):
        f = self._notify
        
        # Whenever a new object is created and added to a parent, 
        #  we update the special unique_child_index attribute for that new object and any siblings.
        # Note: Since this is sent by the event system, there may be several queued up "child polished" events to be processed at once.
        # The assign_unique_child_index function does not assume that this is the ONLY new object that needs a unique id assigned to it.
        if event.type() == QEvent.ChildPolished:
            child = event.child()
            if hasattr(child, 'unique_child_index'):
                del child.unique_child_index
            assign_unique_child_index(child)
        if event.type() == QEvent.ChildRemoved:
            child = event.child()
            if hasattr(child, 'unique_child_index'):
                del child.unique_child_index
        return f( receiver, event )

    def getMainWindow(self):
        top_level_widgets = list(self.topLevelWidgets())
        
        # If there's just one, return it.
        if len(top_level_widgets) == 1:
            return top_level_widgets[0]
        
        # If there's more than one, check for a QMainWindow
        for widget in top_level_widgets:
            if isinstance(widget, QMainWindow):
                return widget
        
        # Otherwise, return the biggest one, not counting the event recorder gui (if any)
        from eventRecorderGui import EventRecorderGui # lazy import here to avoid early-import
        top_level_widgets = filter( lambda w: not isinstance(w, EventRecorderGui), top_level_widgets )
        top_level_widgets = filter( lambda w: isinstance(w, QWidget), top_level_widgets )
        biggest_size = top_level_widgets[0].size()
        biggest_widget = top_level_widgets[0]
        for widget in top_level_widgets[1:]:
            if widget.size() > biggest_size:
                biggest_size = widget.size()
                biggest_widget = widget
        return biggest_widget
    
    @classmethod
    def create_app(cls,
                   mode,
                   playback_script=None,
                   playback_speed=1.0,
                   comment_display=None,
                   finish_callback=None,
                   qapp_args=([],)):
        """
        Create the application.

        mode: must be either 'record' or 'playback'.
        playback_script: Path to a previously recorded playback script.  Used only if mode='playback'
        playback_speed, comment_display, finish_callback: See EventPlayer and EventPlayer.play_script()
        qapp_args: The list of arguments to provide to the QApplication constructor.
        """
        QApplication.setAttribute(Qt.AA_DontUseNativeMenuBar, True)
        app = cls(*qapp_args)

        if mode == 'record':
            app.recorder_control_window.openInPausedState()
            QTimer.singleShot( 100, app.recorder_control_window.raise_ )
            QTimer.singleShot( 110, app.recorder_control_window.activateWindow )
        elif mode == 'playback':
            from eventcapture.eventPlayer import EventPlayer
            player = EventPlayer(playback_speed, comment_display)
            # Playback must be launched from within the event loop,
            # after application has started up.
            assert playback_script is not None, "Can't playback without a playback script path!"
            QTimer.singleShot( 0, lambda: player.play_script(playback_script, finish_callback) )
        else:
            assert False, "Unknown mode: {}".format( mode )
        
        # Also, we must use non-native menus when using eventcapture
        def configureNonNativeMenu():
            mainwin = app.getMainWindow()
            if isinstance( mainwin, QMainWindow ):
                mainwin.menuBar().setNativeMenuBar(False)
        QTimer.singleShot( 0, configureNonNativeMenu )
        
        return app

