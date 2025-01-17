import sys
import os
import logging
import itertools
import json
import concurrent.futures

from xml.sax.saxutils import escape
from distutils import version

# 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
#              because of deprecation
#import pkg_resources
import importlib_metadata
import requests

try:
    import docutils.core
except ImportError:
    docutils = None

from PyQt5.QtWidgets import (
    QWidget, QDialog, QLabel, QLineEdit, QTreeView, QHeaderView,
    QTextBrowser, QDialogButtonBox, QProgressDialog,
    QVBoxLayout, QHBoxLayout
)

from PyQt5.QtGui import (
    QStandardItemModel, QStandardItem, QPalette, QTextOption
)

from PyQt5.QtCore import (
    QSortFilterProxyModel, QItemSelectionModel,
    Qt, QSize, QTimer, QThread)
from PyQt5.QtCore import pyqtSignal as Signal, pyqtSlot as Slot

from urllib.request import urlopen

from orangecanvas.gui.utils import message_warning, message_information, \
                        message_critical as message_error
from orangecanvas.help.manager import get_dist_meta, trim

from orangecanvas.resources import package_dirname

PYPI_API_JSON = "https://pypi.org/pypi/{name}/json"

#####################################################
# MAKE INTERNAL LIBRARIES DYNAMICAL

# read add-on list

INTERNAL_LIBRARIES = []
MAX_VERSION        = {}

if sys.version[:3]=="3.8": internal_libraries_file = "INTERNAL_LIBRARIES_PY38.txt"
else: internal_libraries_file = "INTERNAL_LIBRARIES_PY37.txt"

for a in open(os.path.join(package_dirname("oasys.application"), "data", internal_libraries_file), "rt"):
    a = a.strip()
    if a:
        a = a.split(sep="==")
        library_name = a[0].lower()
        INTERNAL_LIBRARIES.append(library_name)
        if len(a) == 2:
            MAX_VERSION[library_name] = a[1]
        else:
            MAX_VERSION[library_name] = None

# query PyPI

internal_libraries_list = []
is_auto_update = True

try:
    for package in INTERNAL_LIBRARIES:
        r = urlopen(PYPI_API_JSON.format(name=package)).read().decode("utf-8")
        p = json.loads(r)
        p["releases"] = p["releases"][p["info"]["version"]] # load only the last version

        internal_libraries_list.append(p)
except:
    is_auto_update = False


log = logging.getLogger(__name__)

from oasys.application.addons import Uninstall, Upgrade, Install
from oasys.application.addons import OSX_NSURL_toLocalFile, Installer
from oasys.application.addons import get_meta_from_archive, cleanup, TristateCheckItemDelegate, method_queued, unique
from oasys.application.addons import Installed, Installable, Available

def is_updatable(item):
    if isinstance(item, Available) or isinstance(item, Installable) or item.installable is None:
        return False
    inst, dist = item
    # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
    #              because of deprecation
    try:    project_name = str(dist.name).lower()
    except: project_name = str(dist.project_name).lower()
    try:
        if version.StrictVersion(dist.version) < version.StrictVersion(inst.version):
            if MAX_VERSION[project_name] is None: return True
            else: return version.StrictVersion(MAX_VERSION[project_name]) >= version.StrictVersion(inst.version)
    except ValueError:
        if version.LooseVersion(dist.version) < version.LooseVersion(inst.version):
            if MAX_VERSION[project_name] is None: return True
            else: return version.LooseVersion(MAX_VERSION[project_name]) >= version.LooseVersion(inst.version)

def is_installable(item):
    if isinstance(item, Available) or isinstance(item, Installable) or item.installable is None: return True
    else: return False

class InternalLibrariesManagerWidget(QWidget):

    statechanged = Signal()

    def __init__(self, parent=None, **kwargs):
        super(InternalLibrariesManagerWidget, self).__init__(parent, **kwargs)
        self.__items = []
        self.setLayout(QVBoxLayout())

        self.__header = QLabel(
            wordWrap=True,
            textFormat=Qt.RichText
        )
        self.__search = QLineEdit(
            placeholderText=self.tr("Filter")
        )

        self.tophlayout = topline = QHBoxLayout()
        topline.addWidget(self.__search)
        self.layout().addLayout(topline)

        self.__view = view = QTreeView(
            rootIsDecorated=False,
            editTriggers=QTreeView.NoEditTriggers,
            selectionMode=QTreeView.SingleSelection,
            alternatingRowColors=True
        )
        self.__view.setItemDelegateForColumn(0, TristateCheckItemDelegate())
        self.layout().addWidget(view)

        self.__model = model = QStandardItemModel()
        model.setHorizontalHeaderLabels(["", "Name", "Version", "Action"])
        model.dataChanged.connect(self.__data_changed)
        self.__proxy = proxy = QSortFilterProxyModel(
            filterKeyColumn=1,
            filterCaseSensitivity=Qt.CaseInsensitive
        )
        proxy.setSourceModel(model)
        self.__search.textChanged.connect(proxy.setFilterFixedString)

        view.setModel(proxy)
        view.selectionModel().selectionChanged.connect(
            self.__update_details
        )
        header = self.__view.header()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        self.__details = QTextBrowser(
            frameShape=QTextBrowser.NoFrame,
            readOnly=True,
            lineWrapMode=QTextBrowser.WidgetWidth,
            openExternalLinks=True,
        )

        self.__details.setWordWrapMode(QTextOption.WordWrap)
        palette = QPalette(self.palette())
        palette.setColor(QPalette.Base, Qt.transparent)
        self.__details.setPalette(palette)
        self.layout().addWidget(self.__details)

    def set_items(self, items):
        self.__items = items
        model = self.__model
        model.clear()
        model.setHorizontalHeaderLabels(["", "Name", "Version", "Action"])

        for item in items:
            if isinstance(item, Installed):
                installed = True
                ins, dist = item
                # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
                #              because of deprecation
                #name = dist.project_name
                try:    name = dist.name
                except: name = dist.project_name
                summary = get_dist_meta(dist).get("Summary", "")
                version = ins.version if ins is not None else dist.version
            else:
                installed = False
                (ins,) = item
                dist = None
                name = ins.name
                summary = ins.summary
                version = ins.version

            updatable = is_updatable(item)

            item1 = QStandardItem()
            item1.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable |
                           Qt.ItemIsUserCheckable |
                           (Qt.ItemIsTristate if updatable else 0))
            item1.setEnabled(False)

            item1.setCheckState(Qt.Checked)

            #if installed and updatable:
            #    item1.setCheckState(Qt.Checked)
            #elif installed:
            #    item1.setCheckState(Qt.Checked)
            #else:
            #    item1.setCheckState(Qt.Unchecked)

            item2 = QStandardItem(cleanup(name))

            item2.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            item2.setToolTip(summary)
            item2.setData(item, Qt.UserRole)

            if updatable:
                version = "{} < {}".format(dist.version, ins.version)

            item3 = QStandardItem(version)
            item3.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            item4 = QStandardItem()
            item4.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)

            if updatable:
                item4.setText("Update")
            elif not installed:
                item4.setText("Install")

            model.appendRow([item1, item2, item3, item4])

        self.__view.resizeColumnToContents(0)
        self.__view.setColumnWidth(
            1, max(150, self.__view.sizeHintForColumn(1)))
        self.__view.setColumnWidth(
            2, max(150, self.__view.sizeHintForColumn(2)))

        if self.__items:
            self.__view.selectionModel().select(
                self.__view.model().index(0, 0),
                QItemSelectionModel.Select | QItemSelectionModel.Rows
            )

    def item_state(self):
        steps = []
        for i, item in enumerate(self.__items):
            modelitem = self.__model.item(i, 0)
            state = modelitem.checkState()
            if modelitem.flags() & Qt.ItemIsTristate and state == Qt.Checked:
                steps.append((Upgrade, item))
            elif isinstance(item, Available) and state == Qt.Checked:
                steps.append((Install, item))
            elif isinstance(item, Installed) and state == Qt.Unchecked:
                steps.append((Uninstall, item))

        return steps

    def __selected_row(self):
        indices = self.__view.selectedIndexes()
        if indices:
            proxy = self.__view.model()
            indices = [proxy.mapToSource(index) for index in indices]
            return indices[0].row()
        else:
            return -1

    def set_install_projects(self, names):
        """Mark for installation the add-ons that match any of names"""
        model = self.__model
        for row in range(model.rowCount()):
            item = model.item(row, 1)
            if item.text() in names:
                model.item(row, 0).setCheckState(Qt.Checked)

    def __data_changed(self, topleft, bottomright):
        rows = range(topleft.row(), bottomright.row() + 1)
        for i in rows:
            modelitem = self.__model.item(i, 0)
            actionitem = self.__model.item(i, 3)
            item = self.__items[i]

            state = modelitem.checkState()
            flags = modelitem.flags()

            if flags & Qt.ItemIsTristate and state == Qt.Checked:
                actionitem.setText("Update")
            elif isinstance(item, Available) and state == Qt.Checked:
                actionitem.setText("Install")
            elif isinstance(item, Installed) and state == Qt.Unchecked:
                actionitem.setText("Uninstall")
            else:
                actionitem.setText("")
        self.statechanged.emit()

    def __update_details(self):
        index = self.__selected_row()
        if index == -1:
            self.__details.setText("")
        else:
            item = self.__model.item(index, 1)
            item = item.data(Qt.UserRole)
            assert isinstance(item, (Installed, Available))
            text = self._detailed_text(item)
            self.__details.setText(text)

    def _detailed_text(self, item):
        if isinstance(item, Installed):
            remote, dist = item
            if remote is None:
                meta = get_dist_meta(dist)
                description = meta.get("Description") or meta.get('Summary')
            else:
                description = remote.description
        else:
            description = item[0].description

        if docutils is not None:
            try:
                html = docutils.core.publish_string(
                    trim(description),
                    writer_name="html",
                    settings_overrides={
                        "output-encoding": "utf-8",
                        # "embed-stylesheet": False,
                        # "stylesheet": [],
                        # "stylesheet_path": []
                    }
                ).decode("utf-8")

            except docutils.utils.SystemMessage:
                html = "<pre>{}<pre>".format(escape(description))
            except Exception:
                html = "<pre>{}<pre>".format(escape(description))
        else:
            html = "<pre>{}<pre>".format(escape(description))
        return html

    def sizeHint(self):
        return QSize(480, 420)

class InternalLibrariesManagerDialog(QDialog):
    _packages = None

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent, acceptDrops=True, **kwargs)
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)

        self.internallibrarieswidget = InternalLibrariesManagerWidget()
        self.layout().addWidget(self.internallibrarieswidget)

        info_bar = QWidget()
        info_layout = QHBoxLayout()
        info_bar.setLayout(info_layout)
        self.layout().addWidget(info_bar)

        container = QWidget()
        container.setLayout(QHBoxLayout())

        buttons = QDialogButtonBox(
            orientation=Qt.Horizontal,
            standardButtons=QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
        )

        empty = QWidget()
        empty.setFixedWidth(1)

        container.layout().addWidget(buttons)
        container.layout().addWidget(empty)

        buttons.accepted.connect(self.__accepted)
        buttons.rejected.connect(self.__rejected)

        empty = QWidget()
        empty.setFixedHeight(1)

        self.layout().addWidget(container)
        self.layout().addWidget(empty)

        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        if InternalLibrariesManagerDialog._packages is None:
            self._f_pypi_addons = self._executor.submit(list_available_versions)
        else:
            self._f_pypi_addons = concurrent.futures.Future()
            self._f_pypi_addons.set_result(InternalLibrariesManagerDialog._packages)

        self._f_pypi_addons.add_done_callback(
            method_queued(self._set_packages, (object,))
        )

        self.__progress = None  # type: Optional[QProgressDialog]
        self.__thread = None
        self.__installer = None

        if not self._f_pypi_addons.done():
            self.__progressDialog()

        self.__is_app_to_be_closed = False

    def set_is_app_to_be_closed(self, is_app_to_be_closed=True):
        self.__is_app_to_be_closed = is_app_to_be_closed

    @Slot(str, str)
    def __show_error_for_query(self, text, error_details):
        message_error(text, title="Error", details=error_details)

    @Slot(object)
    def add_package(self, installable):
        # type: (Installable) -> None
        if installable.name in {p.name for p in self._packages}:
            return
        else:
            packages = self._packages + [installable]
        self.set_packages(packages)

    def __progressDialog(self):
        if self.__progress is None:
            self.__progress = QProgressDialog(
                self,
                minimum=0, maximum=0,
                labelText=self.tr("Retrieving package list"),
                sizeGripEnabled=False,
                windowTitle="Progress",
            )
            self.__progress.setWindowModality(Qt.WindowModal)
            self.__progress.canceled.connect(self.reject)
            self.__progress.hide()

        return self.__progress

    @Slot(object)
    def _set_packages(self, f):
        if self.__progress is not None:
            self.__progress.hide()
            self.__progress.deleteLater()
            self.__progress = None

        try:
            packages = f.result()
        except Exception as err:
            message_warning(
                "Could not retrieve package list",
                title="Error",
                informative_text=str(err),
                parent=self
            )
            log.error(str(err), exc_info=True)
            packages = []
        else:
            InternalLibrariesManagerDialog._packages = packages

        self.set_packages(packages)

    @Slot(object)
    def set_packages(self, installable):
        # type: (List[Installable]) -> None
        self._packages = packages = installable  # type: List[Installable]
        installed = list_installed_internal_libraries()
        # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
        #              because of deprecation
        #dists = {dist.project_name: dist for dist in installed}
        try:    dists = {dist.name: dist for dist in installed}
        except: dists = {dist.project_name: dist for dist in installed}
        packages = {pkg.name: pkg for pkg in packages}

        # For every pypi available distribution not listed by
        # list_installed_addons, check if it is actually already
        # installed.
        # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
        #              because of deprecation
        '''
        ws = pkg_resources.WorkingSet()
        for pkg_name in set(packages.keys()).difference(set(dists.keys())):
            try:
                d = ws.find(pkg_resources.Requirement.parse(pkg_name))
            except pkg_resources.VersionConflict:
                pass
            except ValueError:
                # Requirements.parse error ?
                pass
            else:
                if d is not None:
                    dists[d.project_name] = d
        '''
        for pkg_name in set(packages.keys()).difference(set(dists.keys())):
            try:
                d = importlib_metadata.distribution(pkg_name)
            except importlib_metadata.PackageNotFoundError:
                pass
            except importlib_metadata.VersionConflict:
                pass
            except ValueError:
                pass
            else:
                if d is not None:
                    dists[d.metadata['Name']] = d

        project_names = unique(
            itertools.chain(packages.keys(), dists.keys())
        )

        items = []
        for name in project_names:
            if name in dists and name in packages:
                item = Installed(packages[name], dists[name])
            elif name in dists:
                item = Installed(None, dists[name])
            elif name in packages:
                item = Available(packages[name])
            else:
                assert False
            items.append(item)

        self.internallibrarieswidget.set_items(items)

    def showEvent(self, event):
        super().showEvent(event)

        if not self._f_pypi_addons.done() and self.__progress is not None:
            QTimer.singleShot(0, self.__progress.show)

    def done(self, retcode):
        super().done(retcode)
        self._f_pypi_addons.cancel()
        self._executor.shutdown(wait=False)
        if self.__thread is not None:
            self.__thread.quit()
            self.__thread.wait(1000)

    def closeEvent(self, event):
        super().closeEvent(event)
        if self.__progress is not None:
            self.__progress.hide()
        self._f_pypi_addons.cancel()
        self._executor.shutdown(wait=False)

        if self.__thread is not None:
            self.__thread.quit()
            self.__thread.wait(1000)

    ADDON_EXTENSIONS = ('.zip', '.whl', '.tar.gz')

    def dragEnterEvent(self, event):
        urls = event.mimeData().urls()
        if any((OSX_NSURL_toLocalFile(url) or url.toLocalFile())
               .endswith(self.ADDON_EXTENSIONS) for url in urls):
            event.acceptProposedAction()

    def dropEvent(self, event):
        """Allow dropping add-ons (zip or wheel archives) on this dialog to
        install them"""
        packages = []
        names = []
        for url in event.mimeData().urls():
            path = OSX_NSURL_toLocalFile(url) or url.toLocalFile()
            if path.endswith(self.ADDON_EXTENSIONS):
                name, vers, summary, descr = (get_meta_from_archive(path) or
                                              (os.path.basename(path), '', '', ''))
                names.append(cleanup(name))
                packages.append(
                    Installable(name, vers, summary,
                                descr or summary, path, [path]))
        future = concurrent.futures.Future()
        future.set_result((InternalLibrariesManagerDialog._packages or []) + packages)
        self._set_packages(future)
        self.internallibrarieswidget.set_install_projects(names)

    def __rejected(self):
        self.reject()

    def __accepted(self):
        steps = self.internallibrarieswidget.item_state()

        if steps:
            # Move all uninstall steps to the front
            steps = sorted(
                steps, key=lambda step: 0 if step[0] == Uninstall else 1
            )
            self.__installer = Installer(steps=steps)
            self.__thread = QThread(self)
            self.__thread.start()

            self.__installer.moveToThread(self.__thread)
            self.__installer.finished.connect(self.__on_installer_finished)
            self.__installer.error.connect(self.__on_installer_error)

            progress = self.__progressDialog()
            self.__installer.installStatusChanged.connect(progress.setLabelText)
            progress.show()
            progress.setLabelText("Installing")

            self.__installer.start()
        else:
            self.accept()

    def __on_installer_error(self, command, pkg, retcode, output):
        message_error(
            "An error occurred while running a subprocess", title="Error",
            informative_text="{} exited with non zero status.".format(command),
            details="".join(output),
            parent=self
        )
        self.reject()

    def __on_installer_finished(self):
        if self.__is_app_to_be_closed:
            message = "Click Ok to restart OASYS for changes to take effect."
            message_information(message, parent=self)
            self.accept()
            sys.exit(0)
        else:
            self.accept()

import platform

def list_available_internal_libraries():
    if is_auto_update:

        system, node, release, version, machine, processor = platform.uname()

        packages = []
        for library in internal_libraries_list:
            try:
                info = library["info"]

                if not ("Debian 3" in version and info["name"]=="PyQt5"):
                    packages.append(
                    Installable(info["name"], info["version"],
                                info["summary"], info["description"],
                                info["package_url"],
                                info["package_url"])
                )
            except (TypeError, KeyError):
                continue  # skip invalid packages

        return packages

def list_available_versions():
    """
    List add-ons available.
    """

    if is_auto_update:
        internal_libraries = internal_libraries_list
    else:
        internal_libraries = []

    # query pypi.org for installed add-ons that are not in our list
    installed = list_installed_internal_libraries()
    # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
    #              because of deprecation
    #missing = set(dist.project_name for dist in installed) - \
    #          set(a.get("info", {}).get("name", "") for a in internal_libraries)
    try: missing = set(dist.name for dist in installed) - \
                   set(a.get("info", {}).get("name", "") for a in internal_libraries)
    except: missing = set(dist.project_name for dist in installed) - \
                      set(a.get("info", {}).get("name", "") for a in internal_libraries)
    for p in missing:
        response = requests.get(PYPI_API_JSON.format(name=p))
        if response.status_code != 200:
            continue
        internal_libraries.append(response.json())

    packages = []
    for internal_library in internal_libraries:
        try:
            info = internal_library["info"]
            packages.append(
                Installable(info["name"], info["version"],
                            info["summary"], info["description"],
                            info["package_url"],
                            info["package_url"])
            )
        except (TypeError, KeyError):
            continue  # skip invalid packages

    return packages

def list_installed_internal_libraries():
    '''
    workingset = pkg_resources.WorkingSet(sys.path)

    installed_internal_libraries = []

    for internal_library in INTERNAL_LIBRARIES:
        try:
            installed_internal_libraries.append(workingset.by_key[internal_library.lower()])
        except KeyError:
            pass
    '''

    installed_internal_libraries = []
    # Iterate over all distributions available in the current environment
    for dist in importlib_metadata.distributions():
        # Check if the distribution's name matches any of the internal libraries
        if dist.metadata['Name'].lower() in (lib.lower() for lib in INTERNAL_LIBRARIES):
            installed_internal_libraries.append(dist)

    return installed_internal_libraries
