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

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QApplication, QWidget, QMainWindow, QMenu, QGroupBox, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton

# Make the program quit on Ctrl+C
import signal
signal.signal(signal.SIGINT, signal.SIG_DFL)

class DemoAppMainWindow( QMainWindow ):
    """
    A silly little app to say hello.
    """
    def __init__( self, parent, flags=Qt.WindowFlags(0) ):
        super( DemoAppMainWindow, self ).__init__( parent, flags )
        self._init_controls()
    
    def _init_controls(self):
        # Init menu
        menu = QMenu("&Actions", self)
        action_reset = menu.addAction("&Reset")
        action_reset.triggered.connect(self._reset_controls)
        self.menuBar().addMenu( menu )

        # Init widgets
        cw = DemoAppMainWindow.CentralWidget(self)
        self.setCentralWidget( cw )
        self.centralWidget().show()
        
    def _reset_controls(self):
        self.centralWidget().reset_controls()
        
    class CentralWidget( QWidget ):
        def __init__(self, parent):
            super( QWidget, self ).__init__(parent)
            self._init_controls()

        def _init_controls(self):
            name_edit = QLineEdit()
            
            input_layout = QHBoxLayout()
            input_layout.addWidget( QLabel("Name:") )
            input_layout.addWidget( name_edit )
            
            # Previously created recordings should work even if new controls
            #    are added to the application in the future, as long as these 
            #    new controls are given UNIQUE OBJECT NAMES.
            # Otherwise, old recordings might break.
            # For example, make a recording, then uncomment the following lines
            #    and play it back your recording. It should still work.
            #new_button_1 = QPushButton("NewButton1", objectName="new_button_1")
            #input_layout.addWidget( new_button_1 )

            greet_button = QPushButton("Greet!", clicked=self._update_greeting)
            input_layout.addWidget( greet_button )

            # See comment above.  
            # These lines can also be uncommented without breaking previously created recordings.
            #new_button_2 = QPushButton("NewButton2", objectName="new_button_2")
            #input_layout.addWidget( new_button_2 )
    
            input_groupbox = QGroupBox("Input", parent=self)
            input_groupbox.setLayout( input_layout )
    
            greeting_label = QLabel()
            output_layout = QVBoxLayout()
            output_layout.addWidget( greeting_label )
    
            output_groupbox = QGroupBox("Output", parent=self)
            output_groupbox.setLayout( output_layout )
            
            layout = QVBoxLayout()
            layout.addWidget( input_groupbox )
            layout.addWidget( output_groupbox )
            self.setLayout( layout )
    
            # Save as members for other methods
            self.name_edit = name_edit
            self.greeting_label = greeting_label
            
            self.reset_controls()

        def reset_controls(self):
            self.name_edit.setText("")
            self.greeting_label.setText("Who are you?")
        
        def _update_greeting(self):
            name = self.name_edit.text()
            self.greeting_label.setText( "Hello, {}!".format( name ) )

if __name__ == "__main__":
    import sys
    mode = None
    
    if len(sys.argv) == 2 and sys.argv[1] == '--record':
        mode = 'record'
        playback_script = None
    elif len(sys.argv) == 3 and sys.argv[1] == '--playback':
        mode = 'playback'
        playback_script = sys.argv[2]
    elif len(sys.argv) != 1:
        sys.stderr.write("Invalid command-line args.\n")
        sys.exit(1)
    
    if mode == 'record' or mode == 'playback':
        # When using eventcapture for recording or playback, 
        #  our app must be created by EventRecordingApp.create_app()
        from eventcapture.eventRecordingApp import EventRecordingApp
        app = EventRecordingApp.create_app( mode, playback_script, 1.0, None, None, qapp_args=([],) )
    else:
        # Start the app without eventcapture support
        app = QApplication([])

    mainwin = DemoAppMainWindow(None)
    mainwin.show()
    mainwin.raise_()

    app.exec_()
    