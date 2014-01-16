from PyQt4.QtCore import Qt
from PyQt4.QtGui import QApplication, QWidget, QMainWindow, QMenu, QGroupBox, QHBoxLayout, QVBoxLayout, QLabel, QLineEdit, QPushButton

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
            greet_button = QPushButton("Greet!", clicked=self._update_greeting)
            
            input_layout = QHBoxLayout()
            input_layout.addWidget( QLabel("Name:") )
            input_layout.addWidget( name_edit )
            input_layout.addWidget( greet_button )
    
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
        app = EventRecordingApp.create_app(mode, playback_script, 1.0, None, None, [])
    else:
        # Start the app without eventcapture support
        app = QApplication([])

    mainwin = DemoAppMainWindow(None)
    mainwin.show()
    mainwin.raise_()

    app.exec_()
    