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

from PyQt4.QtCore import QEvent, QPoint
from PyQt4.QtGui import QMouseEvent, QWheelEvent, QKeyEvent, QMoveEvent, QWindowStateChangeEvent, \
                        QResizeEvent, QContextMenuEvent, QCloseEvent, QApplication

from eventTypeNames import get_event_type_name, get_mouse_button_string, get_key_modifiers_string

event_serializers = {}

def register_serializer(eventType):
    def _dec(f):
        event_serializers[eventType] = f
        return f
    return _dec

def event_to_string(e):
    """
    Convert the given event into a string that can be eval'd in Python.
    """
    return event_serializers[type(e)](e)

##
## Note: Some events use 'global' coordinates, which are global to the screen (not the main window).
##       We serialize the coordinates relative to the main window's corner window, 
##        and then calculate the global coordinates from the relative ones during playback.
##       This allows us to not worry about moving the main window around the screen while we're recording test cases.
##

@register_serializer(QMouseEvent)
def QMouseEvent_to_string(mouseEvent):
    type_name = get_event_type_name( mouseEvent.type() )
    button_str = get_mouse_button_string(mouseEvent.button())
    buttons_str = get_mouse_button_string(mouseEvent.buttons())
    key_str = get_key_modifiers_string(mouseEvent.modifiers())
    mainwin = QApplication.instance().getMainWindow()
    topLeftCorner_global = mainwin.mapToGlobal( QPoint(0,0) )
    relPos = mouseEvent.globalPos() - topLeftCorner_global
    return "PyQt4.QtGui.QMouseEvent({}, {}, mainwin.mapToGlobal( QPoint(0,0) ) + {}, {}, {}, {})".format( type_name, mouseEvent.pos(), relPos, button_str, buttons_str, key_str )

@register_serializer(QWheelEvent)
def QWheelEvent_to_string(wheelEvent):
    buttons_str = get_mouse_button_string(wheelEvent.buttons())
    key_str = get_key_modifiers_string(wheelEvent.modifiers())
    mainwin = QApplication.instance().getMainWindow()
    topLeftCorner_global = mainwin.mapToGlobal( QPoint(0,0) )
    relPos = wheelEvent.globalPos() - topLeftCorner_global
    return "PyQt4.QtGui.QWheelEvent({}, mainwin.mapToGlobal( QPoint(0,0) ) + {}, {}, {}, {}, {})".format( wheelEvent.pos(), relPos, wheelEvent.delta(), buttons_str, key_str, wheelEvent.orientation() )

@register_serializer(QKeyEvent)
def QKeyEvent_to_string(keyEvent):
    text = str(keyEvent.text())
    text = text.replace('\n', '\\n')
    text = text.replace('"', '\\"')
    text = text.replace("'", "\\'")
    text = '"""' + text + '"""'
    type_name = get_event_type_name( keyEvent.type() )
    mod_str = get_key_modifiers_string(keyEvent.modifiers())
    return "PyQt4.QtGui.QKeyEvent({}, 0x{:x}, {}, {}, {}, {})".format( type_name, keyEvent.key(), mod_str, text, keyEvent.isAutoRepeat(), keyEvent.count() )

@register_serializer(QMoveEvent)
def QMoveEvent_to_string(moveEvent):
    return "PyQt4.QtGui.QMoveEvent({}, {})".format( moveEvent.pos(), moveEvent.oldPos() )

@register_serializer(QContextMenuEvent)
def QContextMenuEvent_to_string(contextMenuEvent):
    key_str = get_key_modifiers_string(contextMenuEvent.modifiers())
    mainwin = QApplication.instance().getMainWindow()
    topLeftCorner_global = mainwin.mapToGlobal( QPoint(0,0) )
    relPos = contextMenuEvent.globalPos() - topLeftCorner_global
    return "PyQt4.QtGui.QContextMenuEvent({}, {}, mainwin.mapToGlobal( QPoint(0,0) ) + {}, {})".format( int(contextMenuEvent.reason()), contextMenuEvent.pos(), relPos, key_str )

@register_serializer(QResizeEvent)
def QResizeEvent_to_string(resizeEvent):
    return "PyQt4.QtGui.QResizeEvent({}, {})".format( resizeEvent.size(), resizeEvent.oldSize() )

@register_serializer(QWindowStateChangeEvent)
def QWindowStateChangeEvent_to_string(windowStateChangeEvent):
    return "PyQt4.QtGui.QWindowStateChangeEvent(0x{:x})".format( int(windowStateChangeEvent.oldState()) )

@register_serializer(QCloseEvent)
def QCloseEvent_to_string(closeEvent):
    return "PyQt4.QtGui.QCloseEvent()"

@register_serializer(QEvent)
def QEvent_to_string(event):
    type_name = get_event_type_name( event.type() )
    # Some event types are not exposed in pyqt as symbols
    if not hasattr( QEvent, type_name.split('.')[1] ):
        type_name = int(event.type())
    return "PyQt4.QtCore.QEvent({})".format( type_name )

