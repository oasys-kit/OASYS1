import os
import io
import platform
import pickle
import tempfile
import logging
import concurrent.futures
from xml.etree import ElementTree
from contextlib import contextmanager
from datetime import datetime, timedelta
#import pkg_resources
import importlib_metadata
import importlib_resources

from PyQt5.QtWidgets import (
    QWidget, QMenu, QAction, QDialog, QMessageBox, QFileDialog,
    QHBoxLayout, QLineEdit, QPushButton, QCheckBox, QVBoxLayout, QLabel,
    QFormLayout, QComboBox, QGridLayout, QApplication
)
from PyQt5.QtGui import (
    QKeySequence, QIcon
)
from PyQt5.QtCore import Qt, QSettings, QEvent
from PyQt5.QtCore import pyqtSlot as Slot
from PyQt5.QtCore import pyqtSignal as pyqtSignal

from orangecanvas.scheme import readwrite
from orangecanvas.application import (
    canvasmain, welcomedialog, schemeinfo, settings
)
from orangecanvas.gui.utils import (
    message_critical, message_warning, message_information
)
from orangecanvas import config

import oasys.application.addons as addons
import oasys.application.internal_libraries as internal_libraries

from . import widgetsscheme
from .conf import oasysconf
from oasys.util.oasys_util import ShowWaitDialog
from urllib.request import urlopen

class OASYSUserSettings(settings.UserSettingsDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # find an hide the "Show welcome screen" check box
        showwelcome = self.findChild(QCheckBox, name="show-welcome-screen")
        if showwelcome is not None:
            showwelcome.hide()

        generaltab = self.widget(0)
        outputtab = self.widget(1)
        appstab = self.widget(2)

        box = QWidget(self, objectName="working-directory-container")
        layout = QVBoxLayout()
        self.default_wd_label = QLabel(widgetsscheme.check_working_directory(QSettings().value("output/default-working-directory", "", type=str)))
        pb = QPushButton("Change ...")
        pb.clicked.connect(self.change_working_directory)

        layout.addWidget(self.default_wd_label)
        layout.addWidget(pb)
        box.setLayout(layout)

        box1 = QWidget(self, objectName="change-container")

        layout1 = QVBoxLayout()
        layout1.setContentsMargins(0, 0, 0, 0)
        self.combo_change_title = QComboBox()
        self.combo_change_title.addItems([self.tr("No"),  self.tr("Yes")])
        self.combo_change_title.setCurrentIndex(QSettings().value("oasys/change_title_on_new_duplicate", 0, int))
        self.combo_change_title.currentIndexChanged.connect(self.change_title)

        layout1.addWidget(self.combo_change_title)
        box1.setLayout(layout1)

        box2 = QWidget(self, objectName="units-container")

        layout2 = QVBoxLayout()
        layout2.setContentsMargins(0, 0, 0, 0)
        self.combo_units = QComboBox()
        self.combo_units.addItems([self.tr("m"),self.tr("cm"), self.tr("mm")])
        self.combo_units.setCurrentIndex(QSettings().value("output/default-units", 1, int))
        self.combo_units.currentIndexChanged.connect(self.change_units)

        layout2.addWidget(self.combo_units)
        box2.setLayout(layout2)

        box3 = QWidget(self, objectName="automatic-save-container")

        layout3 = QVBoxLayout()
        layout3.setContentsMargins(0, 0, 0, 0)
        self.combo_automatic_save = QComboBox()
        self.combo_automatic_save.addItems([self.tr("Never"),
                                  self.tr("5 min"),
                                  self.tr("10 min"),
                                  self.tr("30 min"),
                                  self.tr("60 min")])

        self.combo_automatic_save.setCurrentIndex(QSettings().value("output/automatic-save-minutes", 0, int))
        self.combo_automatic_save.currentIndexChanged.connect(self.change_automatic_save)

        layout3.addWidget(self.combo_automatic_save)
        box3.setLayout(layout3)


        box8 = QWidget(self, objectName="show-effective-source-size-container")

        layout8 = QVBoxLayout()
        layout8.setContentsMargins(0, 0, 0, 0)

        self.combo_show_effective_source_size = QComboBox()
        self.combo_show_effective_source_size.addItems([self.tr("No"), self.tr("Yes")])

        self.combo_show_effective_source_size.setCurrentIndex(QSettings().value("output/show-effective-source-size", 0, int))
        self.combo_show_effective_source_size.currentIndexChanged.connect(self.change_show_effective_source_size)

        layout8.addWidget(self.combo_show_effective_source_size)
        box8.setLayout(layout8)

        box4 = QWidget(self, objectName="send-footprint-container")

        layout4 = QVBoxLayout()
        layout4.setContentsMargins(0, 0, 0, 0)

        self.combo_send_footprint = QComboBox()
        self.combo_send_footprint.addItems([self.tr("No"), self.tr("Yes")])

        self.combo_send_footprint.setCurrentIndex(QSettings().value("output/send-footprint", 0, int))
        self.combo_send_footprint.currentIndexChanged.connect(self.change_send_footprint)

        layout4.addWidget(self.combo_send_footprint)
        box4.setLayout(layout4)

        box5 = QWidget(self, objectName="shadow-default-colormap-container")

        layout5 = QVBoxLayout()
        layout5.setContentsMargins(0, 0, 0, 0)

        self.combo_default_cm_shadow = QComboBox()
        self.combo_default_cm_shadow.addItems([self.tr("gray"), self.tr("reversed gray"), self.tr("temperature")])

        self.combo_default_cm_shadow.setCurrentText(QSettings().value("output/shadow-default-colormap", "temperature", str))
        self.combo_default_cm_shadow.currentIndexChanged.connect(self.change_default_cm_shadow)

        layout5.addWidget(self.combo_default_cm_shadow)
        box5.setLayout(layout5)

        box6 = QWidget(self, objectName="srw-default-colormap-container")

        layout6 = QVBoxLayout()
        layout6.setContentsMargins(0, 0, 0, 0)

        self.combo_default_cm_srw = QComboBox()
        self.combo_default_cm_srw.addItems([self.tr("gray"), self.tr("reversed gray"), self.tr("temperature")])

        self.combo_default_cm_srw.setCurrentText(QSettings().value("output/srw-default-colormap", "gray", str))
        self.combo_default_cm_srw.currentIndexChanged.connect(self.change_default_cm_srw)

        layout6.addWidget(self.combo_default_cm_srw)
        box6.setLayout(layout6)

        box7 = QWidget(self, objectName="srw-default-propagation-mode-container")

        layout7 = QVBoxLayout()
        layout7.setContentsMargins(0, 0, 0, 0)

        self.combo_default_pm_srw = QComboBox()
        self.combo_default_pm_srw.addItems([self.tr("Element by Element (Wofry)"), self.tr("Element by Element (Native)"), self.tr("Whole Beamline (Native)")])

        self.combo_default_pm_srw.setCurrentIndex(QSettings().value("output/srw-default-propagation-mode", 1, int))
        self.combo_default_pm_srw.currentIndexChanged.connect(self.change_default_pm_srw)

        layout7.addWidget(self.combo_default_pm_srw)
        box7.setLayout(layout7)


        box10 = QWidget(self, objectName="wonder-default-gsasii-mode-container")

        layout10 = QVBoxLayout()
        layout10.setContentsMargins(0, 0, 0, 0)

        self.combo_default_gsasii_wonder = QComboBox()
        self.combo_default_gsasii_wonder.addItems([self.tr("Online"), self.tr("External")])

        self.combo_default_gsasii_wonder.setCurrentIndex(QSettings().value("output/wonder-default-gsasii-mode", 0, int))
        self.combo_default_gsasii_wonder.currentIndexChanged.connect(self.change_default_gsasii_wonder)

        layout10.addWidget(self.combo_default_gsasii_wonder)
        box10.setLayout(layout10)

        box11 = QWidget(self, objectName="wonder-default-automatic-container")

        layout11 = QVBoxLayout()
        layout11.setContentsMargins(0, 0, 0, 0)

        self.combo_default_automatic_wonder = QComboBox()
        self.combo_default_automatic_wonder.addItems([self.tr("Runtime Only"), self.tr("OASYS Setting")])

        self.combo_default_automatic_wonder.setCurrentIndex(QSettings().value("output/wonder-default-automatic", 1, int))
        self.combo_default_automatic_wonder.currentIndexChanged.connect(self.change_default_automatic_wonder)

        layout11.addWidget(self.combo_default_automatic_wonder)
        box11.setLayout(layout11)

        for i in range(generaltab.layout().count()):
            if generaltab.layout().itemAt(i).widget().objectName() == "startup-group":
                widget = generaltab.layout().itemAt(i).widget()

                cb_update = QCheckBox(self.tr("No auto-update inner libraries"), self, objectName="no-update-inner-libraries")
                self.bind(cb_update, "checked", "startup/no-update-inner-libraries")
                widget.layout().addWidget(cb_update)

        generaltab.layout().insertRow(
            0, self.tr("Add Numeral on New/Duplicate"), box1)

        generaltab.layout().insertRow(
            0, self.tr("Default Units"), box2)

        generaltab.layout().insertRow(
            0, self.tr("Automatically save every"), box3)

        appstab.layout().insertRow(
            0, self.tr("Wonder: GSAS-II mode"), box10)

        appstab.layout().insertRow(
            0, self.tr("Wonder: Automatic Fit"), box11)

        appstab.layout().insertRow(
            0, self.tr("SRW: Default Propagation Mode"), box7)

        appstab.layout().insertRow(
            0, self.tr("SRW: Default Colormap"), box6)

        appstab.layout().insertRow(
            0, self.tr("ShadowOui: Default Colormap"), box5)

        appstab.layout().insertRow(
            0, self.tr("ShadowOui: Send footprint beam"), box4)

        appstab.layout().insertRow(
            0, self.tr("ShadowOui: Show Effective Source Size"), box8)

        outputtab.layout().insertRow(
            0, self.tr("Default working directory"), box)

    def change_automatic_save(self):
        QSettings().setValue("output/automatic-save-minutes", self.combo_automatic_save.currentIndex())
        
    def change_title(self):
        QSettings().setValue("oasys/change_title_on_new_duplicate", self.combo_change_title.currentIndex())

    def change_units(self):
        QSettings().setValue("output/default-units", self.combo_units.currentIndex())

    def change_show_effective_source_size(self):
        QSettings().setValue("output/show-effective-source-size", self.combo_show_effective_source_size.currentIndex())

    def change_send_footprint(self):
        QSettings().setValue("output/send-footprint", self.combo_send_footprint.currentIndex())

    def change_default_cm_shadow(self):
        QSettings().setValue("output/shadow-default-colormap", self.combo_default_cm_shadow.currentText())

    def change_default_cm_srw(self):
        QSettings().setValue("output/srw-default-colormap", self.combo_default_cm_srw.currentText())

    def change_default_pm_srw(self):
        QSettings().setValue("output/srw-default-propagation-mode", self.combo_default_pm_srw.currentIndex())

    def change_default_gsasii_wonder(self):
        QSettings().setValue("output/wonder-default-gsasii-mode", self.combo_default_gsasii_wonder.currentIndex())

    def change_default_automatic_wonder(self):
        QSettings().setValue("output/wonder-default-automatic", self.combo_default_automatic_wonder.currentIndex())

    def change_working_directory(self):
        cur_wd = widgetsscheme.check_working_directory(QSettings().value("output/default-working-directory", os.path.expanduser("~/Oasys"), type=str))
        new_wd = QFileDialog.getExistingDirectory(self, "Set working directory", cur_wd)
        if new_wd:
            new_wd = widgetsscheme.check_working_directory(new_wd)
            QSettings().setValue("output/default-working-directory", new_wd)
            self.default_wd_label.setText(new_wd)

class OASYSSchemeInfoDialog(schemeinfo.SchemeInfoDialog):
    def __init__(self, parent=None, existing_scheme=False, **kwargs):
        super().__init__(parent, **kwargs)

        # Insert a 'Working Directory' row in the editor form.
        layout = self.editor.layout()

        self.working_dir_edit = QWidget(self)
        self.working_dir_edit.setLayout(QHBoxLayout())
        self.working_dir_edit.layout().setContentsMargins(0, 0, 0, 0)

        settings = QSettings()

        self.working_dir_line = QLineEdit(self)
        self.working_dir_line.setReadOnly(True)

        cur_wd = widgetsscheme.check_working_directory(settings.value("output/default-working-directory", "", type=str) or os.path.expanduser("~/Oasys"))

        self.working_dir_line.setText(cur_wd)
        pb = QPushButton("Change ...")
        pb.clicked.connect(self.__change_working_directory)

        self.working_dir_edit.layout().addWidget(self.working_dir_line)
        self.working_dir_edit.layout().addWidget(pb)

        layout.insertRow(2, self.tr("Working directory"), self.working_dir_edit)

        self.units_edit = QWidget(self)
        self.units_edit.setLayout(QGridLayout())
        self.units_edit.layout().setContentsMargins(0, 0, 0, 0)

        self.combo_units = QComboBox()
        self.combo_units.addItems([self.tr("m"),
                                   self.tr("cm"),
                                   self.tr("mm")])

        self.combo_units.setEnabled(not existing_scheme)

        label = QLabel("")

        richText = "<html><head><meta name=\"qrichtext\" content=\"1\" /></head>" + \
                       "<body style=\" white-space: pre-wrap; " + \
                       "font-size:9pt; font-weight:400; font-style:normal; text-decoration:none;\">" + \
                       "<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; " +\
                       "margin-right:0px; -qt-block-indent:0; text-indent:0px; font-size:12pt;\">Units in use in the scheme:</p>" "</body></html>"

        label.setText(richText)

        self.units_edit.layout().addWidget(label, 0, 0)
        self.units_edit.layout().addWidget(self.combo_units, 0, 1, Qt.AlignRight)

        label = QLabel("")

        richText = "<html><head><meta name=\"qrichtext\" content=\"1\" /></head>" + \
                       "<body style=\" white-space: pre-wrap; " + \
                       "font-size:9pt; font-weight:400; font-style:normal; text-decoration:none;\">" + \
                       "<p style=\" margin-top:0px; margin-bottom:0px; margin-left:0px; " +\
                       "margin-right:0px; -qt-block-indent:0; text-indent:0px; font-size:12pt;\">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(effective for ShadowOui only)</p>" "</body></html>"

        label.setText(richText)

        self.units_edit.layout().addWidget(label, 0, 2, Qt.AlignLeft)

        layout.insertRow( 2, self.tr("Units"), self.units_edit)

        # Fix the widget tab order.
        item = layout.itemAt(1, QFormLayout.FieldRole)
        if item.widget() is not None:
            QWidget.setTabOrder(item.widget(), self.combo_units)
            QWidget.setTabOrder(self.combo_units, self.working_dir_line)
            QWidget.setTabOrder(self.working_dir_line, pb)

    def setScheme(self, scheme):
        super().setScheme(scheme)
        self.working_dir_line.setText(scheme.working_directory)
        self.combo_units.setCurrentIndex(scheme.workspace_units)

    def __change_working_directory(self):
        cur_wd = widgetsscheme.check_working_directory(self.working_dir_line.text())
        new_wd = widgetsscheme.check_working_directory(QFileDialog.getExistingDirectory(self, self.tr("Set working directory"), cur_wd))
        if new_wd: self.working_dir_line.setText(new_wd)

    def title(self):
        return self.editor.title()

    def description(self):
        return self.editor.description()

    def workingDirectory(self):
        return self.working_dir_line.text()

    def workspaceUnits(self):
        return self.combo_units.currentIndex()


def addons_cache_dir():
    cachedir = os.path.join(config.cache_dir(), "addons-cache")
    os.makedirs(cachedir, exist_ok=True)
    return cachedir


def addons_cache_path():
    cachedir = addons_cache_dir()
    cachename = "items-cache.pickle"
    return os.path.join(cachedir, cachename)


def _mktemp(dir, prefix, suffix=None, delete=False):
    return tempfile.NamedTemporaryFile(
        prefix=prefix, suffix=suffix, dir=dir, delete=False)


@contextmanager
def atomicupdate(filepath):
    dirname, basename = os.path.split(filepath)

    if not basename:
        raise ValueError("must name a file")

    basename, ext = os.path.splitext(basename)

    f = _mktemp(dirname, prefix=basename + "-", suffix=ext, delete=False)
    tempfilename = f.name

    try:
        stat = os.stat(filepath)
    except FileNotFoundError:
        os.chmod(tempfilename, 0o644)
    else:
        # Copy user, group and access flags
        if platform.system() != 'Windows':
            os.chown(tempfilename, stat.st_uid, stat.st_gid)
        os.chmod(tempfilename, stat.st_mode)

    try:
        yield f
    except BaseException:
        f.close()
        os.remove(tempfilename)
        raise
    else:
        f.close()

    try:
        os.replace(tempfilename, filepath)
    except OSError:
        os.remove(tempfilename)
        raise


def store_pypi_packages(items):
    with atomicupdate(addons_cache_path()) as f:
        pickle.dump(items, f)


def load_pypi_packages():
    try:
        with open(addons_cache_path(), "rb") as f:
            try:
                items = pickle.load(f)
            except Exception:
                items = []
    except OSError:
        items = []
    return items

def load_pypi_internal_libraries():
    return internal_libraries.list_available_internal_libraries()

def resource_path(path):
    #return pkg_resources.resource_filename(__name__, path)
    ref = importlib_resources.files(__name__) / path
    with importlib_resources.as_file(ref) as resource_path: return str(resource_path)

from oasys.util.external_command import run_command

class OASYSMainWindow(canvasmain.CanvasMainWindow):

    automatic_save = pyqtSignal()

    def __init__(self, parent=None, no_update=False, **kwargs):
        super().__init__(parent, **kwargs)
        self.is_main = True
        self.menu_registry = None

        settings = QSettings()
        updateperiod = settings.value("oasys/addon-update-check-period", defaultValue=1, type=int)
        try:
            timestamp = os.stat(addons_cache_path()).st_mtime
        except OSError:
            timestamp = 0

        lastdelta = datetime.now() - datetime.fromtimestamp(timestamp)
        self._log = logging.getLogger(__name__)
        self._log.info("Time from last update %s (%s)", lastdelta, timestamp)
        check = updateperiod >= 0 and abs(lastdelta) > timedelta(minutes=updateperiod)

        self.__executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.__pypi_addons_f = None
        self.__pypi_addons = None
        self.__updatable = 0

        self.__pypi_internal_libraries = None
        self.__internal_library_to_update = None
        self.__internal_library_updatable = 0
        self.__internal_library_to_install = None
        self.__internal_library_installable = 0

        # AUTOMATIC UPDATE OF THE INTERNAL LIBRARIES
        if not no_update: self.__set_pypi_internal_libraries(load_pypi_internal_libraries())

        if check:
            f = self.__executor.submit(addons.list_available_versions)
            f.add_done_callback(addons.method_queued(self.__set_pypi_addons_f, (object,)))
            self.__pypi_addons_f = f
        else:
            try:
                items = load_pypi_packages()
            except Exception:
                pass
            else:
                self.__set_pypi_addons(items)

        self.automatic_save.connect(self.automatic_save_scheme)

        # PUT OLD CODE HERE IN CASE OF ROLLBACK

        if platform.system() == "Darwin":
            self.new_instance_action = \
                QAction(self.tr("New OASYS instance"), self,
                        objectName="new-oasys-instance",
                        toolTip=self.tr("Run a new OASYS instance"),
                        triggered=self.new_instance,
                        icon=canvasmain.canvas_icons("Open.svg")
                        )

            file_menu = self.menuBar().children()[-1]

            file_menu.addSeparator()
            file_menu.addAction(self.new_instance_action)

    def set_secondary(self):
        self.is_main = False

    @Slot(object)
    def __set_pypi_addons_f(self, f):
        if f.exception():
            err = f.exception()
            self._log.error("Error querying PyPi",
                            exc_info=(type(err), err, None))
        else:
            self.__set_pypi_addons(f.result())
            store_pypi_packages(self.__pypi_addons)

    def __set_pypi_addons(self, items):
            self.__pypi_addons = items
            self._log.debug("Got pypi packages: %r", self.__pypi_addons)
            items = addons.installable_items(
                self.__pypi_addons,
                [ep.dist for ep in oasysconf.addon_entry_points()])

            self.__updatable = sum(addons.is_updatable(item) for item in items)

    def __set_pypi_internal_libraries(self, items):
        if not items is None:
            self.__pypi_internal_libraries = items

            class EntryPoint():
                def __init__(self, project_name, version):
                    self.project_name = project_name
                    self.version      = version

            entry_points = []
            #for internal_library in self.__pypi_internal_libraries:
            #    try:
            #        entry_points.append(EntryPoint(internal_library.name, pkg_resources.get_distribution(internal_library.name).version))
            #    except pkg_resources.DistributionNotFound:
            #        pass
            for internal_library in self.__pypi_internal_libraries:
                try:
                    version = importlib_metadata.version(internal_library.name)
                    entry_points.append(EntryPoint(internal_library.name, version))
                except importlib_metadata.PackageNotFoundError:
                    pass

            items = addons.installable_items(self.__pypi_internal_libraries, entry_points)

            self.__internal_library_to_update = []
            self.__internal_library_to_install = []
            for item in items:
                if internal_libraries.is_updatable(item):     self.__internal_library_to_update.append(item)
                elif internal_libraries.is_installable(item): self.__internal_library_to_install.append(item)

            self.__internal_library_updatable   = len(self.__internal_library_to_update)
            self.__internal_library_installable = len(self.__internal_library_to_install)

    def new_instance(self):
        run_command(["python", "-m", "oasys.canvas"], raise_on_fail=False, wait_for_output=False)

    def automatic_save_scheme(self):
        """Save the current scheme. If the scheme does not have an associated
        path then prompt the user to select a scheme file. Return
        QDialog.Accepted if the scheme was successfully saved and
        QDialog.Rejected if the user canceled the file selection.

        """
        document = self.current_document()
        curr_scheme = document.scheme()
        path = document.path()

        temporary_file_name = "automatic_save_" + str(id(self)) + ".ows~"

        if path and self.check_can_save(document, path + "~"):
            if self.save_scheme_to(curr_scheme, path + "~"):
                if os.path.exists(temporary_file_name):
                    os.remove(temporary_file_name)

                return QDialog.Accepted
            else:
                return QDialog.Rejected
        else:
            return self.save_scheme_to(curr_scheme, temporary_file_name)

    def new_scheme(self):
        """
        Reimplemented from `CanvasMainWindow.new_scheme`.

        Create a new empty workflow scheme.

        Return QDialog.Rejected if the user canceled the operation and
        QDialog.Accepted otherwise.
        """
        document = self.current_document()
        if document.isModifiedStrict():
            # Ask for save changes
            if self.ask_save_changes() == QDialog.Rejected:
                return QDialog.Rejected

        new_scheme = widgetsscheme.OASYSWidgetsScheme(parent=self)

        status = self.show_scheme_properties_for(new_scheme, self.tr("New Workflow"))

        if status == QDialog.Rejected: return QDialog.Rejected
        elif not os.path.isdir(new_scheme.working_directory):
            message_information(
                "Workflow Working Directory does not exist\n\n"
                "project creation aborted",
                parent=self)

            return QDialog.Rejected

        self.set_new_scheme(new_scheme)
        self._log.info("Changing current work dir to '%s'",
                       new_scheme.working_directory)
        os.chdir(new_scheme.working_directory)
        return QDialog.Accepted

    def new_scheme_from(self, filename):
        """
        Reimplemented from `CanvasMainWindow.new_scheme_from`.
        Create and return a new :class:`WidgetsScheme` from `filename`.
        Return `None` if an error occurs or the user aborts the process.
        """
        log = logging.getLogger(__name__)

        default_workdir = widgetsscheme.check_working_directory(QSettings().value("output/default-working-directory", os.path.expanduser("~/Oasys"), type=str))
        default_units   = QSettings().value("output/default-units", 1, type=int)

        if "http" in filename: is_remote = True
        else: is_remote = False

        try:
            try:
                if is_remote: contents = urlopen(filename)
                else:         contents = io.BytesIO(open(filename, "rb").read())
            except Exception as e:
                message_critical(
                     self.tr("Could not load an OASYS " + ("Remote " if is_remote else "") + "Workflow file"),
                     title=self.tr("Error"),
                     informative_text=self.tr("An I/O error occurred while loading '%s'.") % filename + ":\n\n" + str(e),
                     exc_info=False,
                     parent=self)
                return None

            doc  = ElementTree.parse(contents)
            root = doc.getroot()
            working_directory  = root.get("working_directory", default_workdir)
            working_units      = root.get("workspace_units", str(default_units))
            title              = root.get("title", "untitled")
            description        = root.get("description", "")
            # First parse the contents into intermediate representation
            # to catch format errors early (will be re-parsed later).
            try:
                readwrite.parse_ows_etree_v_2_0(doc)
            except Exception:
                message_critical(
                     self.tr("Could not load an OASYS Workflow file"),
                     title=self.tr("Error"),
                     informative_text=self.tr("An unexpected error occurred "
                                              "while loading '%s'.") % filename,
                     exc_info=True,
                     parent=self)
                return None

            working_directory = widgetsscheme.check_working_directory(working_directory)

            if not working_directory or not os.path.isdir(working_directory): working_directory = default_workdir
            if working_units is None: working_units = default_units
        except Exception:
            return None

        # change working directory of units on open

        new_scheme = widgetsscheme.OASYSWidgetsScheme(parent=self)

        if not title is None: new_scheme.title = title
        new_scheme.working_directory = working_directory
        new_scheme.workspace_units   = int(working_units)
        if not description is None: new_scheme.description = description

        status = self.show_scheme_properties_for(new_scheme, self.tr("Properties of " + new_scheme.title))

        if status == QDialog.Rejected or \
                (new_scheme.working_directory is None or new_scheme.workspace_units is None):
            log.info("Confirmation/Modification of workflow properties aborted by user")
            message_information(
                "Confirmation/Modification of workflow properties canceled by user\n\n"
                "project load aborted",
                parent=self)

            return None
        else:
            new_title       = new_scheme.title
            new_description = new_scheme.description

            message = None
            if title          != new_scheme.title:             message = "Workflow title"
            if working_directory        != new_scheme.working_directory: message = "Workflow working directory" if message is None else (message + ", working directory")
            if int(working_units) != new_scheme.workspace_units:   message = "Workflow units" if message is None else (message + ", units")
            if description    != new_scheme.description:       message = "Workflow description" if message is None else (message + ", description")

            if not message is None:
                message += " changed by user"
                log.info(message)
                message_information(message, parent=self)

                self.current_document().setModified(True)

            if not os.path.isdir(new_scheme.working_directory): os.mkdir(new_scheme.working_directory)

            errors = []
            if is_remote: contents = urlopen(filename) # remote stream does not support seek operation
            else:         contents.seek(0)
            try:
                readwrite.scheme_load(new_scheme, contents, error_handler=errors.append)
                new_scheme.title       = new_title
                new_scheme.description = new_description
            except Exception:
                message_critical(
                     self.tr("Could not load an OASYS Workflow file"),
                     title=self.tr("Error"),
                     informative_text=self.tr("An unexpected error occurred "
                                              "while loading '%s'.") % filename,
                     exc_info=True,
                     parent=self)
                return None

            if errors:
                message_warning(
                    self.tr("Errors occurred while loading the workflow."),
                    title=self.tr("Problem"),
                    informative_text=self.tr(
                         "There were problems loading some "
                         "of the widgets/links in the "
                         "workflow."
                    ),
                    details="\n".join(map(repr, errors)),
                    parent=self
                )

            # now start the actual load with a valid working directory
            log.info("Changing current work dir to '%s'", new_scheme.working_directory)
            os.chdir(new_scheme.working_directory)

            return new_scheme

    def set_new_scheme(self, new_scheme):
        dlg = ShowWaitDialog("Loading Workflow...", "Loading Workflow " + new_scheme.title, parent=self)
        dlg.show()

        raised_exception = None
        try:
            super().set_new_scheme(new_scheme)
        except Exception as exception:
            raised_exception = exception

        dlg.hide()
        dlg.deleteLater()

        if not raised_exception is None: raise raised_exception

    def getWorkspaceUnitsLabel(self, units):
        if units == 0:   return "m"
        elif units == 1: return "cm"
        elif units == 2: return "mm"
        else:            return None

    def welcome_dialog(self):
        """
        Show a modal welcome dialog for OASYS.

        Reimplemented from `CanvasMainWindow`.
        """

        dialog = welcomedialog.WelcomeDialog(self)
        dialog.setWindowTitle(self.tr("Welcome to OASYS"))
        dialog.setModal(True)

        def new_scheme():
            if self.new_scheme() == QDialog.Accepted:
                dialog.accept()

        def open_scheme():
            if self.open_scheme() == QDialog.Accepted:
                dialog.accept()

        def open_scheme_remote():
            if self.open_remote_scheme() == QDialog.Accepted:
                dialog.accept()

        def open_recent():
            if self.recent_scheme() == QDialog.Accepted:
                dialog.accept()

        def get_started():
            import webbrowser
            webbrowser.open("https://github.com/oasys-kit/oasys_school")

        def documentation():
            import webbrowser
            webbrowser.open("https://www.aps.anl.gov/Science/Scientific-Software/OASYS")


        new_action = \
            QAction(self.tr("New"), dialog,
                    toolTip=self.tr("Open a new workflow."),
                    triggered=new_scheme,
                    shortcut=QKeySequence.New,
                    icon=canvasmain.canvas_icons("New.svg")
                    )

        open_action = \
            QAction(self.tr("Open"), dialog,
                    objectName="welcome-action-open",
                    toolTip=self.tr("Open a workflow."),
                    triggered=open_scheme,
                    shortcut=QKeySequence.Open,
                    icon=canvasmain.canvas_icons("Open.svg")
                    )

        open_remote_action = \
            QAction(self.tr("Open Remote"), dialog,
                    objectName="welcome-action-open-remote",
                    toolTip=self.tr("Open a remote workflow."),
                    triggered=open_scheme_remote,
                    shortcut=QKeySequence(Qt.ControlModifier | \
                                          (Qt.ShiftModifier | Qt.Key_U)),
                    icon=canvasmain.canvas_icons("Documentation.svg")
                    )

        recent_action = \
            QAction(self.tr("Recent"), dialog,
                    objectName="welcome-recent-action",
                    toolTip=self.tr("Browse and open a recent workflow."),
                    triggered=open_recent,
                    shortcut=QKeySequence(Qt.ControlModifier | \
                                          (Qt.ShiftModifier | Qt.Key_R)),
                    icon=canvasmain.canvas_icons("Recent.svg")
                    )

        get_started_action = \
            QAction(self.tr("OASYS School"), self,
                    objectName="get-started-action",
                    toolTip=self.tr("OASYS School"),
                    triggered=get_started,
                    icon=canvasmain.canvas_icons("Tutorials.svg")
                    )

        documentation_action = \
            QAction(self.tr("OASYS Site"), self,
                    objectName="documentation-action",
                    toolTip=self.tr("View reference website."),
                    triggered=documentation,
                    icon=canvasmain.canvas_icons("Get Started.svg")
                    )

        icon = resource_path("icons/Install.svg")

        addons_action = \
            QAction(self.tr("Add-ons"), dialog,
                    objectName="welcome-addons-action",
                    toolTip=self.tr("Install add-ons"),
                    triggered=self.open_addons,
                    icon=QIcon(icon),
                    )

        # -------------------------------------------------------------
        # AUTOMATIC UPDATES
        # -------------------------------------------------------------

        if self.__internal_library_updatable or self.__internal_library_installable or self.__updatable:
            message = ""

            if self.__internal_library_updatable or self.__internal_library_installable:
                message += "OASYS needs to update/install its internal libraries"

            if self.__updatable:
                addons_action.setText("Update Now")
                addons_action.setToolTip("Update or install new add-ons")
                addons_action.setIcon(QIcon(resource_path("icons/Update.svg")))

                if self.__internal_library_updatable or self.__internal_library_installable:
                    message += " and "
                    one = "one"
                else:
                    one = "One"

                message += "{} add-on{} {} a newer version.".format(one if self.__updatable == 1 else self.__updatable,
                                                                    "s" if self.__updatable > 1 else "",
                                                                    "has" if self.__updatable == 1 else "have")

            message += "\n\nWould you like to update now (recommended)?"

            mbox = QMessageBox(dialog, icon=QMessageBox.Information, text=message, standardButtons=QMessageBox.Ok | QMessageBox.No)
            mbox.setWindowFlags(Qt.Sheet | Qt.MSWindowsFixedSizeDialogHint)
            mbox.setModal(True)
            dialog.show()
            mbox.show()

            def do_update():
                is_app_to_be_closed = False
                if self.__internal_library_updatable or self.__internal_library_installable:
                    is_app_to_be_closed = self.open_internal_libraries(is_app_to_be_closed=not self.__updatable) > 0
                if self.__updatable:
                    self.open_addons(is_app_to_be_closed=is_app_to_be_closed)

            def do_nothing(): pass

            mbox.finished.connect(lambda r: do_update() if r == QMessageBox.Ok else do_nothing())

        # -------------------------------------------------------------

        bottom_row = [get_started_action, documentation_action, addons_action]

        self.new_action.triggered.connect(dialog.accept)
        top_row = [new_action, open_action, open_remote_action, recent_action]

        dialog.addRow(top_row, background="light-grass")
        dialog.addRow(bottom_row, background="light-orange")

        # Find and hide the welcome dialogs bottom bar. It contains the
        # Show at startup" check box and we ALWAYS want the Welcome Dialog
        # to show.
        bottombar = dialog.findChild(QWidget, name='bottom-bar')
        if bottombar is not None:
            bottombar.hide()

        status = dialog.exec_()

        dialog.deleteLater()

        return status

    def scheme_properties_dialog(self, existing_scheme=False):
        """Return an empty `SchemeInfo` dialog instance.
        """
        dialog = OASYSSchemeInfoDialog(self, existing_scheme)

        dialog.setWindowTitle(self.tr("Workflow Info"))
        dialog.setFixedSize(725, 450)
        return dialog

    def show_scheme_properties(self):
        """Show current scheme properties.
        """
        current_doc = self.current_document()
        scheme = current_doc.scheme()
        dialog = self.scheme_properties_dialog(existing_scheme=True)
        dialog.setAutoCommit(False)
        dialog.setScheme(scheme)
        status = dialog.exec_()

        if status == QDialog.Accepted:
            stack = current_doc.undoStack()
            scheme = current_doc.scheme()
            stack.beginMacro(self.tr("Change Info"))
            current_doc.setTitle(dialog.title())
            current_doc.setDescription(dialog.description())
            scheme.working_directory = dialog.workingDirectory()
            scheme.workspace_units = dialog.workspaceUnits()
            os.chdir(scheme.working_directory)

            stack.endMacro()

        return status

    def show_scheme_properties_for(self, scheme, window_title=None):
        """
        Reimplemented from `CanvasMainWindow.show_properties_for`

        Show scheme properties for `scheme` with `window_title (if None
        a default 'Scheme Info' title will be used.
        """
        dialog = self.scheme_properties_dialog(existing_scheme=False)
        if window_title is not None: dialog.setWindowTitle(window_title)
        dialog.setScheme(scheme)

        status = dialog.exec_()

        if status == QDialog.Accepted:
            scheme.working_directory = widgetsscheme.check_working_directory(dialog.workingDirectory())
            scheme.workspace_units = dialog.workspaceUnits()
            os.chdir(scheme.working_directory)

        dialog.deleteLater()

        return status


    def open_canvas_settings(self):
        dlg = OASYSUserSettings(self)
        dlg.setWindowTitle(self.tr("Preferences"))
        if dlg.exec_() == 0:
            self._CanvasMainWindow__update_from_settings()

    def set_menu_registry(self, menu_registry):
        self.menu_registry = menu_registry

        for menu_instance in self.menu_registry.menus():
            try:
                menu_instance.setCanvasMainWindow(self)

                custom_menu = QMenu(menu_instance.name, self)
                sub_menus = menu_instance.getSubMenuNamesList()

                is_open_container = False
                container_menu = None
                action_index = 0

                for index in range(0, len(sub_menus)):
                    if is_open_container:
                        if menu_instance.isSeparator(sub_menus[index]):
                            if container_menu is None: raise Exception("Container Menu has not been defined")

                            container_menu.addSeparator()
                        elif menu_instance.isOpenContainer(sub_menus[index]):
                            raise Exception("Container has already been opened: Open Container Operation is inconsistent")
                        elif menu_instance.isCloseContainer(sub_menus[index]):
                            is_open_container = False
                            container_menu = None
                        else:
                            if container_menu is None:
                                container_menu = QMenu(sub_menus[index], self)

                                custom_menu.addMenu(container_menu)
                            else:
                                action_index = action_index + 1
                                custom_action = \
                                    QAction(sub_menus[index], self,
                                            objectName=sub_menus[index].lower() + "-action",
                                            toolTip=self.tr(sub_menus[index]),
                                            )
                                custom_action.triggered.connect(getattr(menu_instance, 'executeAction_' + str(action_index)))
                                container_menu.addAction(custom_action)
                    else:
                        if menu_instance.isSeparator(sub_menus[index]):
                            custom_menu.addSeparator()
                        elif menu_instance.isOpenContainer(sub_menus[index]):
                            is_open_container = True
                        elif menu_instance.isCloseContainer(sub_menus[index]):
                            raise Exception("Container has not been opened: Close Container Operation is inconsistent")
                        else:
                            action_index = action_index + 1
                            custom_action = \
                                QAction(sub_menus[index], self,
                                        objectName=sub_menus[index].lower() + "-action",
                                        toolTip=self.tr(sub_menus[index]),
                                        )
                            custom_action.triggered.connect(getattr(menu_instance, 'executeAction_' + str(action_index)))
                            custom_menu.addAction(custom_action)

                self.menuBar().addMenu(custom_menu)

            except Exception as exception:
                print("Error in creating Customized Menu: " + str(menu_instance))
                print(str(exception.args[0]))
                continue

    def open_internal_libraries(self, is_app_to_be_closed=False):
        from oasys.application.internal_libraries import InternalLibrariesManagerDialog
        from oasys.application.addons import have_install_permissions
        if not have_install_permissions():
            QMessageBox(QMessageBox.Warning,
                        "Add-ons: insufficient permissions",
                        "Insufficient permissions to install add-ons. Try starting OASYS "
                        "as a system administrator or install OASYS in user folders.",
                        parent=self).exec_()
        dlg = InternalLibrariesManagerDialog(self, windowTitle=self.tr("Internal Libraries"))
        dlg.set_is_app_to_be_closed(is_app_to_be_closed)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        status = dlg.exec_()

        return status

    def open_addons(self, is_app_to_be_closed=False):
        from oasys.application.addons import AddonManagerDialog, have_install_permissions
        if not have_install_permissions():
            QMessageBox(QMessageBox.Warning,
                        "Add-ons: insufficient permissions",
                        "Insufficient permissions to install add-ons. Try starting OASYS "
                        "as a system administrator or install OASYS in user folders.",
                        parent=self).exec_()
        dlg = AddonManagerDialog(self, windowTitle=self.tr("Add-ons"))
        dlg.set_is_app_to_be_closed(is_app_to_be_closed)
        dlg.setAttribute(Qt.WA_DeleteOnClose)
        status = dlg.exec_()

        return status

    def closeSecondaryEvent(self, event):
        """Close the main window.
        """
        document = self.current_document()
        if document.isModifiedStrict():
            if self.ask_save_changes() == QDialog.Rejected:
                # Reject the event
                event.ignore()
                return

        old_scheme = document.scheme()

        # Set an empty scheme to clear the document
        document.setScheme(config.workflow_constructor(parent=self))

        QApplication.sendEvent(old_scheme, QEvent(QEvent.Close))

        old_scheme.deleteLater()

        config.save_config()

        geometry = self.saveGeometry()
        state = self.saveState(version=self.SETTINGS_VERSION)
        settings = QSettings()
        settings.beginGroup("mainwindow")
        settings.setValue("geometry", geometry)
        settings.setValue("state", state)
        settings.setValue("canvasdock/expanded",
                          self.dock_widget.expanded())
        settings.setValue("scheme-margins-enabled",
                          self.scheme_margins_enabled)

        settings.setValue("last-scheme-dir", self.last_scheme_dir)
        settings.setValue("widgettoolbox/state",
                          self.widgets_tool_box.saveState())

        settings.setValue("quick-help/visible",
                          self.canvas_tool_dock.quickHelpVisible())

        settings.endGroup()

        event.accept()

    def closeEvent(self, event):
        if self.is_main:
            super().closeEvent(event)
            if event.isAccepted():
                if self.__pypi_addons_f is not None:
                    self.__pypi_addons_f.cancel()
                self.__executor.shutdown(wait=True)
        else:
            self.closeSecondaryEvent(event)
            if event.isAccepted():
                if self.__pypi_addons_f is not None:
                    self.__pypi_addons_f.cancel()


