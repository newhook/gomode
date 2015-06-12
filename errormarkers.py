# The basis of this code came from the SublimeClang plugin.
# https://github.com/quarnster/SublimeClang
import sublime
import sublime_plugin
from collections import defaultdict

from .common import *

def sencode(s):
    return s.encode("utf-8")

def sdecode(s):
    return s

ERRORS = {}
ERROR = "error"

class GoModeNext(sublime_plugin.TextCommand):
    def run(self, edit):
        v = self.view
        fn = sencode(v.file_name())
        line, column = v.rowcol(v.sel()[0].a)
        gotoline = -1
        if fn in ERRORS:
            for errLine in ERRORS[fn]:
                if errLine > line:
                    gotoline = errLine
                    break
        if gotoline != -1:
            v.window().open_file("%s:%d" % (fn, gotoline + 1), sublime.ENCODED_POSITION)
        else:
            sublime.status_message("No more errors or warnings!")

class GoModePrevious(sublime_plugin.TextCommand):
    def run(self, edit):
        v = self.view
        fn = sencode(v.file_name())
        line, column = v.rowcol(v.sel()[0].a)
        gotoline = -1
        if fn in ERRORS:
            for errLine in ERRORS[fn]:
                if errLine < line:
                    gotoline = errLine
        if gotoline != -1:
            v.window().open_file("%s:%d" % (fn, gotoline + 1), sublime.ENCODED_POSITION)
        else:
            sublime.status_message("No more errors or warnings!")

def clear_error_marks():
    global ERRORS
    listdict = lambda: defaultdict(list)
    ERRORS = defaultdict(listdict)

def has_error_marks(view):
    fn = sencode(view.file_name())
    return fn in ERRORS

def clear_error_marks_view(filename):
    global ERRORS
    ERRORS[filename] = defaultdict(list)

def add_error_mark(filename, line, message):
    global ERRORS
    if not filename in ERRORS:
        ERRORS[filename] = defaultdict(list)
    print(filename)
    ERRORS[filename][line].append(message)

def show_error_marks(view):
    '''Adds error marks to view.'''
    erase_error_marks(view)
    outlines = []
    fn = sencode(view.file_name())

    for line in ERRORS[fn].keys():
        outlines.append(view.full_line(view.text_point(line, 0)))

    args = [
        'gomode-outlines-illegal',
        outlines,
        "invalid",
        'dot'
    ]
    args.append(sublime.DRAW_OUTLINED)
    view.add_regions(*args)

def erase_error_marks(view):
    view.erase_regions('gomode-outlines-illegal')

def last_selected_lineno(view):
    return view.rowcol(view.sel()[0].end())[0]

def update_statusbar(view):
    fn = view.file_name()
    if fn is not None:
        fn = sencode(fn)
    lineno = last_selected_lineno(view)

    if fn in ERRORS and lineno in ERRORS[fn]:
        view.set_status('GoMode_line', "Error: %s" % '; '.join(ERRORS[fn][lineno]))
    else:
        view.erase_status('GoMode_line')

class GoStatusbarUpdater(sublime_plugin.EventListener):
    def __init__(self):
        print("HERE")
        self.lastSelectedLineNo = -1

    def is_enabled(self):
        return True

    def on_selection_modified(self, view):
        if view.is_scratch():
            return


        # We only display errors in the status bar for the last line in the current selection.
        # If that line number has not changed, there is no point in updating the status bar.
        lastSelectedLineNo = last_selected_lineno(view)

        if lastSelectedLineNo != self.lastSelectedLineNo:
            self.lastSelectedLineNo = lastSelectedLineNo
            update_statusbar(view)

    def has_errors(self, view):
        fn = view.file_name()
        if fn is None:
            return False
        return sencode(fn) in ERRORS

    def show_errors(self, view):
        if self.has_errors(view) and not get_setting("error_marks_on_panel_only", False, view):
            show_error_marks(view)

    def on_activated(self, view):
        self.show_errors(view)

    def on_load(self, view):
        self.show_errors(view)
