"""
Orange Canvas main entry point

"""

import os
import gc
import re
import logging
import optparse
import pickle
import shlex
import shutil
import signal
import time
import platform

# 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
#              because of deprecation
#import pkg_resources
import importlib_resources

from PyQt5 import QtCore
from PyQt5.QtGui import QFont, QColor
from PyQt5.QtCore import Qt, QDir, QThread, QObject
from PyQt5.QtWidgets import QStyleFactory
try: # necessary for XRayServer under Linux
    from PyQt5.QtWebEngineWidgets import QWebEngineView as QWebView
except:
    pass

import orangecanvas
from orangecanvas.application.application import CanvasApplication
from orangecanvas.application.outputview import TextStream, ExceptHook

from orangecanvas.gui.splashscreen import SplashScreen
from orangecanvas.utils.redirect import redirect_stdout, redirect_stderr
from orangecanvas.utils.qtcompat import QSettings
from orangecanvas import config
from orangecanvas.utils.settings import config_slot

from orangecanvas.registry import cache, qt
from orangecanvas.registry import WidgetRegistry, set_global_registry

from oasys.canvas.mainwindow import OASYSMainWindow
from oasys.canvas import conf

log = logging.getLogger(__name__)

def running_in_ipython():
    try:
        __IPYTHON__
        return True
    except NameError:
        return False


# Allow termination with CTRL + C
signal.signal(signal.SIGINT, signal.SIG_DFL)


def fix_osx_10_9_private_font():
    """Temporary fix for QTBUG-32789."""
    from PyQt5.QtCore import QSysInfo, QT_VERSION
    if sys.platform == "darwin":
        try:
            QFont.insertSubstitution(".Helvetica Neue DeskInterface",
                                     "Helvetica Neue")
            if QSysInfo.MacintoshVersion > QSysInfo.MV_10_8 and \
                            QT_VERSION < 0x40806:
                QFont.insertSubstitution(".Lucida Grande UI",
                                         "Lucida Grande")
        except AttributeError:
            pass


def fix_win_pythonw_std_stream():
    """
    On windows when running without a console (using pythonw.exe) the
    std[err|out] file descriptors are invalid and start throwing exceptions
    when their buffer is flushed (`http://bugs.python.org/issue706263`_)

    """
    if sys.platform == "win32" and \
            os.path.basename(sys.executable) == "pythonw.exe":
        if sys.stdout is not None and sys.stdout.fileno() < 0:
            sys.stdout = open(os.devnull, "wb")
        if sys.stdout is not None and sys.stderr.fileno() < 0:
            sys.stderr = open(os.devnull, "wb")

import warnings
from matplotlib import MatplotlibDeprecationWarning

warnings.filterwarnings("ignore",category=MatplotlibDeprecationWarning)
warnings.filterwarnings("ignore",category=RuntimeWarning)

import sys

def main(argv=None):

    # prevents OASYS to crash on large worskpaces (too many widgets)
    sys.setrecursionlimit(10000)

    # PREVENTS MESSAGING FROM THREADING PROBLEMS IN MATPLOTLIB:
    # The process has forked and you cannot use this CoreFoundation functionality safely. You MUST exec().
    # Break on __THE_PROCESS_HAS_FORKED_AND_YOU_CANNOT_USE_THIS_COREFOUNDATION_FUNCTIONALITY___YOU_MUST_EXEC__() to debug.
    #
    # This problem cause the continous appearing of Popup Windows "Python Quit Unexpectedly", with no reason.
    #
    if platform.system() == "Darwin":
        crash_report = os.popen("defaults read com.apple.CrashReporter DialogType").read().strip()
        os.system("defaults write com.apple.CrashReporter DialogType none")

    try:
        if argv is None:
            argv = sys.argv

        usage = "usage: %prog [options] [workflow_file]"
        parser = optparse.OptionParser(usage=usage)

        parser.add_option("--no-discovery",
                          action="store_true",
                          help="Don't run widget discovery "
                               "(use full cache instead)")
        parser.add_option("--force-discovery",
                          action="store_true",
                          help="Force full widget discovery "
                               "(invalidate cache)")
        parser.add_option("--clear-widget-settings",
                          action="store_true",
                          help="Remove stored widget setting")
        parser.add_option("--no-welcome",
                          action="store_true",
                          help="Don't show welcome dialog.")
        parser.add_option("--no-splash",
                          action="store_true",
                          help="Don't show splash screen.")
        parser.add_option("-l", "--log-level",
                          help="Logging level (0, 1, 2, 3, 4)",
                          type="int", default=1)
        parser.add_option("--no-redirect",
                          action="store_true",
                          help="Do not redirect stdout/err to canvas output view.")
        parser.add_option("--style",
                          help="QStyle to use",
                          type="str", default="Fusion")
        parser.add_option("--stylesheet",
                          help="Application level CSS style sheet to use",
                          type="str", default="orange.qss")
        parser.add_option("--qt",
                          help="Additional arguments for QApplication",
                          type="str", default=None)
        parser.add_option("--no-update",
                          action="store_true",
                          help="Stop automatic update internal libraries")

        (options, args) = parser.parse_args(argv[1:])

        levels = [logging.CRITICAL,
                  logging.ERROR,
                  logging.WARN,
                  logging.INFO,
                  logging.DEBUG]

        # Fix streams before configuring logging (otherwise it will store
        # and write to the old file descriptors)
        fix_win_pythonw_std_stream()

        # Try to fix fonts on OSX Mavericks
        fix_osx_10_9_private_font()

        # File handler should always be at least INFO level so we need
        # the application root level to be at least at INFO.

        root_level = min(levels[options.log_level], logging.INFO)
        rootlogger = logging.getLogger(orangecanvas.__name__)
        rootlogger.setLevel(root_level)
        oasyslogger = logging.getLogger("oasys")
        oasyslogger.setLevel(root_level)

        # Standard output stream handler at the requested level
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(level=levels[options.log_level])
        rootlogger.addHandler(stream_handler)
        oasyslogger.addHandler(stream_handler)

        config.set_default(conf.oasysconf)
        log.info("Starting 'OASYS' application.")

        qt_argv = argv[:1]

    #     if options.style is not None:
        qt_argv += ["-style", options.style]

        if options.qt is not None:
            qt_argv += shlex.split(options.qt)

        qt_argv += args

        if options.clear_widget_settings:
            log.debug("Clearing widget settings")
            shutil.rmtree(config.widget_settings_dir(), ignore_errors=True)

        log.debug("Starting CanvasApplicaiton with argv = %r.", qt_argv)
        app = CanvasApplication(qt_argv)

        t = ("startup/no-update-inner-libraries", bool, False, "No auto-update inner libraries")
        config.spec.append(config_slot(*t))

        # NOTE: config.init() must be called after the QApplication constructor
        config.init()

        file_handler = logging.FileHandler(
            filename=os.path.join(config.log_dir(), "canvas.log"),
            mode="w"
        )

        file_handler.setLevel(root_level)
        rootlogger.addHandler(file_handler)

        # intercept any QFileOpenEvent requests until the main window is
        # fully initialized.
        # NOTE: The QApplication must have the executable ($0) and filename
        # arguments passed in argv otherwise the FileOpen events are
        # triggered for them (this is done by Cocoa, but QApplicaiton filters
        # them out if passed in argv)

        open_requests = []

        def onrequest(url):
            log.info("Received an file open request %s", url)
            open_requests.append(url)

        app.fileOpenRequest.connect(onrequest)

        settings = QSettings()

        stylesheet = options.stylesheet
        stylesheet_string = None

        if stylesheet != "none":
            if os.path.isfile(stylesheet):
                stylesheet_string = open(stylesheet, "rb").read()
            else:
                if not os.path.splitext(stylesheet)[1]:
                    # no extension
                    stylesheet = os.path.extsep.join([stylesheet, "qss"])

                pkg_name = orangecanvas.__name__
                resource = "styles/" + stylesheet

                # 17 Jan 2025: replaced pkg_resources with importlib (for now the third party version)
                #              because of deprecation
                '''
                if pkg_resources.resource_exists(pkg_name, resource):
                    stylesheet_string = \
                        pkg_resources.resource_string(pkg_name, resource).decode()

                    base = pkg_resources.resource_filename(pkg_name, "styles")

                    pattern = re.compile(
                        r"^\s@([a-zA-Z0-9_]+?)\s*:\s*([a-zA-Z0-9_/]+?);\s*$",
                        flags=re.MULTILINE
                    )

                    matches = pattern.findall(stylesheet_string)

                    for prefix, search_path in matches:
                        QDir.addSearchPath(prefix, os.path.join(base, search_path))
                        log.info("Adding search path %r for prefix, %r",
                                 search_path, prefix)

                    stylesheet_string = pattern.sub("", stylesheet_string)

                else:
                    log.info("%r style sheet not found.", stylesheet)
                '''

                ref = importlib_resources.files(pkg_name).joinpath(resource)
                with importlib_resources.as_file(ref) as stylesheet_file:
                    if os.path.exists(str(stylesheet_file)):
                        stylesheet_string = ref.read_bytes().decode()

                        ref = importlib_resources.files(pkg_name) / "styles"
                        with importlib_resources.as_file(ref) as base:
                            pattern = re.compile(
                                r"^\s@([a-zA-Z0-9_]+?)\s*:\s*([a-zA-Z0-9_/]+?);\s*$",
                                flags=re.MULTILINE
                            )

                            matches = pattern.findall(stylesheet_string)

                            for prefix, search_path in matches:
                                QDir.addSearchPath(prefix, os.path.join(str(base), search_path))
                                log.info("Adding search path %r for prefix, %r", search_path, prefix)

                        stylesheet_string = pattern.sub("", stylesheet_string)
                    else:
                        log.info("%r style sheet not found.", stylesheet)

        # Add the default canvas_icons search path
        dirpath = os.path.abspath(os.path.dirname(orangecanvas.__file__))
        QDir.addSearchPath("canvas_icons", os.path.join(dirpath, "icons"))

        if not options.no_update is None: no_update = options.no_update
        else: no_update = QSettings().value("startup/no-update-inner-libraries", False, type=bool)

        canvas_window = OASYSMainWindow(parent=None, no_update=no_update)
        canvas_window.setWindowIcon(config.application_icon())

        if stylesheet_string is not None:
            canvas_window.setStyleSheet(stylesheet_string)

        if not options.force_discovery:
            reg_cache = cache.registry_cache()
        else:
            reg_cache = None

        widget_registry = qt.QtWidgetRegistry()

        widget_discovery = config.widget_discovery(
            widget_registry, cached_descriptions=reg_cache)
        menu_registry = conf.menu_registry()

        want_splash = \
            settings.value("startup/show-splash-screen", True, type=bool) and \
            not options.no_splash

        if want_splash:
            pm, rect = config.splash_screen()
            splash_screen = SplashScreen(pixmap=pm, textRect=rect)
            splash_screen.setFont(QFont("Helvetica", 12))
            color = QColor("#FFD39F")

            def show_message(message):
                splash_screen.showMessage(message, color=color)

            widget_registry.category_added.connect(show_message)

        log.info("Running widget discovery process.")

        cache_filename = os.path.join(config.cache_dir(), "widget-registry.pck")

        if options.no_discovery:
            widget_registry = pickle.load(open(cache_filename, "rb"))
            widget_registry = qt.QtWidgetRegistry(widget_registry)
        else:
            if want_splash:
                splash_screen.show()
            widget_discovery.run(config.widgets_entry_points())
            if want_splash:
                splash_screen.hide()
                splash_screen.deleteLater()

            # Store cached descriptions
            cache.save_registry_cache(widget_discovery.cached_descriptions)
            with open(cache_filename, "wb") as f:
                pickle.dump(WidgetRegistry(widget_registry), f)

        set_global_registry(widget_registry)

        canvas_window.set_widget_registry(widget_registry)
        canvas_window.set_menu_registry(menu_registry)

        # automatic save

        automatic_saver_thread = QThread()
        automatic_saver = SaveWorkspaceObj(canvas_window, )
        automatic_saver.moveToThread(automatic_saver_thread)
        automatic_saver.finished.connect(automatic_saver_thread.quit)
        automatic_saver_thread.started.connect(automatic_saver.long_running)
        automatic_saver_thread.finished.connect(app.exit)
        automatic_saver_thread.start()

        canvas_window.show()
        canvas_window.raise_()

        want_welcome = True or \
            settings.value("startup/show-welcome-screen", True, type=bool) \
            and not options.no_welcome

        app.setStyle(QStyleFactory.create('Fusion'))

        # Process events to make sure the canvas_window layout has
        # a chance to activate (the welcome dialog is modal and will
        # block the event queue, plus we need a chance to receive open file
        # signals when running without a splash screen)
        app.processEvents()

        app.fileOpenRequest.connect(canvas_window.open_scheme_file)

        close_app = False

        if open_requests:
            if "pydevd.py" in str(open_requests[0].path()): # PyCharm Debugger on
                open_requests = []

        if want_welcome and not args and not open_requests:
            if not canvas_window.welcome_dialog():
                log.info("Welcome screen cancelled; closing application")
                close_app = True

        elif args:
            log.info("Loading a scheme from the command line argument %r",
                     args[0])
            canvas_window.load_scheme(args[0])
        elif open_requests:
            log.info("Loading a scheme from an `QFileOpenEvent` for %r",
                     open_requests[-1])
            canvas_window.load_scheme(open_requests[-1].toLocalFile())

        stdout_redirect = \
            settings.value("output/redirect-stdout", True, type=bool)

        stderr_redirect = \
            settings.value("output/redirect-stderr", True, type=bool)

        # cmd line option overrides settings / no redirect is possible
        # under ipython
        if options.no_redirect or running_in_ipython():
            stderr_redirect = stdout_redirect = False

        output_view = canvas_window.output_view()

        if stdout_redirect:
            stdout = TextStream()
            stdout.stream.connect(output_view.write)
            if sys.stdout is not None:
                # also connect to original fd
                stdout.stream.connect(sys.stdout.write)
        else:
            stdout = sys.stdout

        if stderr_redirect:
            error_writer = output_view.formated(color=Qt.red)
            stderr = TextStream()
            stderr.stream.connect(error_writer.write)
            if sys.stderr is not None:
                # also connect to original fd
                stderr.stream.connect(sys.stderr.write)
        else:
            stderr = sys.stderr

        if stderr_redirect:
            sys.excepthook = ExceptHook()
            sys.excepthook.handledException.connect(output_view.parent().show)

        if not close_app:
            with redirect_stdout(stdout), redirect_stderr(stderr):
                log.info("Entering main event loop.")
                try:
                    status = app.exec_()
                except BaseException:
                    log.error("Error in main event loop.", exc_info=True)

            canvas_window.deleteLater()
            app.processEvents()
            app.flush()
            del canvas_window
        else:
            status = False

        if automatic_saver_thread.isRunning():
            automatic_saver_thread.deleteLater()

        # Collect any cycles before deleting the QApplication instance
        gc.collect()

        del app

        # RESTORE INITIAL USER SETTINGS
        if platform.system() == "Darwin":
            os.system("defaults write com.apple.CrashReporter DialogType " + crash_report)

        return status
    except Exception as e:
        # RESTORE INITIAL USER SETTINGS
        if platform.system() == "Darwin":
            os.system("defaults write com.apple.CrashReporter DialogType "  + crash_report)

        raise e


class SaveWorkspaceObj(QObject):
    finished = QtCore.pyqtSignal()

    def __init__(self, canvas_window):
       QObject.__init__(self)
       self.canvas_window = canvas_window

    def long_running(self):
            while True:
                minutes = self.get_minutes(QSettings().value("output/automatic-save-minutes", 0, type=int))

                if minutes == 0:
                    time.sleep(10) # in order to not waste CPU
                else:
                    time.sleep(60*minutes)
                    self.canvas_window.automatic_save.emit()

            self.finished.emit()

    def get_minutes(self, minutes_index):
        if minutes_index == 0:
            return 0
        elif minutes_index == 1:
            return 5
        elif minutes_index == 2:
            return 10
        elif minutes_index == 3:
            return 30
        elif minutes_index == 4:
            return 60
        else:
            return 0


if __name__ == "__main__":
    sys.exit(main())
