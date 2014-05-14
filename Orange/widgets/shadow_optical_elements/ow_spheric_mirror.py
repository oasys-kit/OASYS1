import sys
from numpy import array
import Orange
import Orange.shadow
from Orange.widgets import gui
from PyQt4.QtGui import QApplication

from Orange.widgets.shadow_gui import ow_spheric_element, ow_optical_element

class SphericMirror(ow_spheric_element.SphericElement):

    name = "Spherical Mirror"
    description = "Shadow OE: Spherical Mirror"
    icon = "icons/spherical_mirror.png"
    maintainer = "Luca Rebuffi"
    maintainer_email = "luca.rebuffi(@at@)elettra.eu"
    priority = 2
    category = "Optical Elements"
    keywords = ["data", "file", "load", "read"]

    def __init__(self):
        graphical_Options=ow_optical_element.GraphicalOptions(is_mirror=True)

        super().__init__(graphical_Options)

        gui.rubber(self.controlArea)

        gui.rubber(self.mainArea)

    ################################################################
    #
    #  SHADOW MANAGEMENT
    #
    ################################################################

    def instantiateShadowOE(self):
        return Orange.shadow.ShadowOpticalElement.create_spherical_mirror()

if __name__ == "__main__":
    a = QApplication(sys.argv)
    ow = SphericMirror()
    ow.show()
    a.exec_()
    ow.saveSettings()