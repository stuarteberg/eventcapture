# Copyright (c) 2016, HHMI
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification,
# are permitted provided that the following conditions are met:
#
#   1. Redistributions of source code must retain the above copyright notice, this
#      list of conditions and the following disclaimer.
#
#   2. Redistributions in binary form must reproduce the above copyright notice,
#      this list of conditions and the following disclaimer in the documentation
#      and/or other materials provided with the distribution.
#
#   3. Neither the name of the copyright holder nor the names of its contributors
#      may be used to endorse or promote products derived from this software
#      without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
# IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
# INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
# NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import gc
import threading

from PyQt4.QtCore import QObject, QEvent, QTimer
from PyQt4.QtGui import QApplication, QCursor

from timer import Timer
from objectNameUtils import get_named_object, NamedObjectNotFoundError

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
        
        # Before we start, move the mouse cursor to (0,0) to avoid interference with the recorded events.
        QCursor.setPos(0, 0)
        
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

        # Note: We are allowed to use QTimer outside of the main thread like this 
        #        because the target function belongs to a QObject
        QTimer.singleShot( 0, flusher.set )    
        flusher.wait()
        flusher.clear()

    def display_comment(self, comment):
        self._comment_display(comment)

    def _default_comment_display(self, comment):
        print "--------------------------------------------------"
        print comment
        print "--------------------------------------------------"

