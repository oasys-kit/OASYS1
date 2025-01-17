import logging
import sys
# 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
#              because of deprecation
#import pkg_resources
import importlib_resources
import importlib_metadata

from PyQt5.QtGui import QPixmap, QFont, QFontMetrics, QColor, QPainter, QIcon
from PyQt5.QtCore import Qt, QCoreApplication, QPoint, QRect

from orangewidget.canvas import config as owconfig
from orangecanvas import config

from . import discovery, widgetsscheme


WIDGETS_ENTRY = "oasys.widgets"
MENU_ENTRY = "oasys.menus"

#: Parameters for searching add-on packages in PyPi using xmlrpc api.
ADDON_PYPI_SEARCH_SPEC = {"keywords": "oasys1", "owner" : "lucarebuffi"}
#: Entry points by which add-ons register with pkg_resources.
ADDONS_ENTRY = "oasys.addons"

# Add a default for our extra default-working-dir setting.
config.spec += [
    config.config_slot("output/default-working-dir", str, "",
                       "Default working directory"),
    config.config_slot("oasys/addon-update-check-period", int, 1,
                       "Check for updates every (in days)")
]

class oasysconf(owconfig.orangeconfig):
    OrganizationDomain = ""
    ApplicationName = "OASYS1"

    if sys.platform == 'darwin' and sys.version_info[1] <= 6:
        ApplicationVersion = "1.1"
    else:
        if sys.version[:3]=="3.8":
            ApplicationVersion = "1.3"
        else:
            ApplicationVersion = "1.2"

    @staticmethod
    def splash_screen():
        ref = importlib_resources.files(__name__).joinpath("icons/oasys-splash-screen.png")
        with importlib_resources.as_file(ref) as path: pm = QPixmap(str(path))

        version = QCoreApplication.applicationVersion()
        size = 21 if len(version) < 5 else 16
        font = QFont("Helvetica")
        font.setPixelSize(size)
        font.setBold(True)
        font.setItalic(True)
        font.setLetterSpacing(QFont.AbsoluteSpacing, 2)
        metrics = QFontMetrics(font)
        br = metrics.boundingRect(version).adjusted(-5, 0, 5, 0)
        br.moveCenter(QPoint(436, 224))

        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)
        p.setFont(font)
        p.setPen(QColor("#231F20"))
        p.drawText(br, Qt.AlignCenter, version)
        p.end()
        return pm, QRect(88, 193, 200, 20)

    @staticmethod
    def application_icon():
        """
        Return the main application icon.
        """
        ref = importlib_resources.files(__name__).joinpath("icons/oasys.png")
        with importlib_resources.as_file(ref) as path: return QIcon(str(path))

    @staticmethod
    def widgets_entry_points():
        # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
        #              because of deprecation
        return importlib_metadata.entry_points(group=WIDGETS_ENTRY)
        #return pkg_resources.iter_entry_points(WIDGETS_ENTRY)

    @staticmethod
    def addon_entry_points():
        # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
        #              because of deprecation
        return importlib_metadata.entry_points(group=ADDONS_ENTRY)
        #return pkg_resources.iter_entry_points(ADDONS_ENTRY)

    @staticmethod
    def addon_pypi_search_spec():
        return dict(ADDON_PYPI_SEARCH_SPEC)

    @staticmethod
    def tutorials_entry_points():
        # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
        #              because of deprecation
        return importlib_metadata.entry_points(group="oasys.tutorials")
        #return pkg_resources.iter_entry_points("oasys.tutorials")

    workflow_constructor = widgetsscheme.OASYSWidgetsScheme


def omenus():
    """
    Return an iterator of oasys.menu.OMenu instances registered
    by 'orange.menu' pkg_resources entry point.
    """
    log = logging.getLogger(__name__)
    # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
    #              because of deprecation
    #for ep in pkg_resources.iter_entry_points(MENU_ENTRY):
    for ep in importlib_metadata.entry_points(group=MENU_ENTRY):
        try:
            menu = ep.load()
        #except pkg_resources.ResolutionError:
        #    log.info("Error loading a '%s' entry point.", MENU_ENTRY, exc_info=True)
        except Exception:
            log.exception("Error loading a '%s' entry point.", MENU_ENTRY)
        else:
            if "MENU" in menu.__dict__:
                yield from discovery.omenus_from_package(menu)


def menu_registry():
    """
    Return the the OASYS extension menu registry.
    """
    return discovery.MenuRegistry(list(omenus()))
