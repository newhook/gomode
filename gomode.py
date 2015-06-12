import sublime, sublime_plugin

import subprocess
import json
import os
import re
import threading
import queue
import atexit

#
# TODO:
# - define gofmt binary.
# - user configuration.
# - Oracle scope from the keyboard (not edit configuration file).
# - syntax to top level?
#

from .errormarkers import clear_error_marks, clear_error_marks_view, add_error_mark, show_error_marks, \
                         update_statusbar, erase_error_marks, has_error_marks

from .common import *

from .thread_progress import *

# Add flymake*.go so we avoid spamming the file view when flymaking.
def update_file_exclude_patterns():
    s = sublime.load_settings("Preferences.sublime-settings")
    file_exclude_patterns = s.get('file_exclude_patterns', [])
    if file_exclude_patterns is None:
        return
    found = False
    for f in file_exclude_patterns:
        if f == "flymake*.go":
            found = True
    if not found:
        file_exclude_patterns.append("flymake*.go")
        s.set('file_exclude_patterns', file_exclude_patterns)
        sublime.save_settings("Preferences.sublime-settings")
update_file_exclude_patterns()

def get_output_view(window):
    view = None
    buff_name = 'Go Mode'

    if get_setting("output", "buffer") == "output_panel":
        view = window.create_output_panel(buff_name)
    else:
        # If the output file is already open, use that.
        for v in window.views():
            if v.name() == buff_name:
                view = v
                break
        # Otherwise, create a new one.
        if view is None:
            view = window.new_file()

    view.set_name(buff_name)
    view.set_scratch(True)
    view_settings = view.settings()
    view_settings.set('line_numbers', False)
    # view.set_syntax_file('Packages/GoMode/GoOracleResults.tmLanguage')

    return view

def sel(view, i=0):
    try:
        s = view.sel()
        if s is not None and i < len(s):
            return s[i]
    except Exception:
        pass

    return sublime.Region(0, 0)

def is_go_source_view(view=None, strict=True):
    if view is None:
        return False

    selector_match = view.score_selector(sel(view).begin(), 'source.go') > 0
    if selector_match:
        return True

    if strict:
        return False

    fn = view.file_name() or ''
    return fn.lower().endswith('.go')

packages = {
     "gocode": "github.com/nsf/gocode",
     "goimports": "golang.org/x/tools/cmd/goimports",
     "godef": "github.com/rogpeppe/godef",
     "oracle": "golang.org/x/tools/cmd/oracle",
     "gorename": "golang.org/x/tools/cmd/gorename",
     "goflymake": "github.com/dougm/goflymake",
}
# "github.com/golang/lint/golint",
#             "github.com/kisielk/errcheck",
#             "github.com/jstemmer/gotags",

import time

def install_packages(view):
    for k in packages:
        view.run_command('go_mode_output_insert', {'text': "Installing %s\n" % (k)})
        args = ["go", "get", "-u", "-v", "-f", packages[k] ]
        view.run_command('go_mode_output_insert', {'text': " ".join(args)})
        view.run_command('go_mode_output_insert', {'text': "\n"})
        try:
            env = getenv()
            child = subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = child.communicate()
            if child.returncode != 0:
                err = stderr.decode('utf-8')
                view.run_command('go_mode_output_insert', {'text': "Failed %s\n" % (err)})
            view.run_command('go_mode_output_insert', {'text': stdout.decode('utf-8')})
            view.run_command('go_mode_output_insert', {'text': "\n"})
        except Exception as e:
            view.run_command('go_mode_output_insert', {'text': "Failed %s\n" % (e)})

class GoModeInstallBinaries(sublime_plugin.WindowCommand):
    def run(self):
            t = threading.Thread(target=install_packages, args=(get_output_view(self.window),))
            t.start()
            ThreadProgress(t, "installing binaries", "installing GoMode binaries complete")

class GoModeGoFmtCommand(sublime_plugin.TextCommand):
    def is_enabled(self):
        return is_go_source_view(self.view)

    def run(self, edit, saving=False):
        # Get the content of the current window from the text editor.
        selection = sublime.Region(0, self.view.size())
        content = self.view.substr(selection)

        try:
            env = getenv()
            child = subprocess.Popen(["goimports"], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = child.communicate(input=content.encode('utf-8'))
            if child.returncode != 0:
                err = stderr.decode('utf-8')
                print("goimports failed: %s" % (err))
                return

            # Put the result back.
            self.view.replace(edit, selection, stdout.decode('utf8'))
        except Exception as e:
            print(e)

class GoModeOutputInsertCommand(sublime_plugin.TextCommand):
    def run(self, edit, text):
        self.view.insert(edit, self.view.size(), text)

class GoModeGoRenameCommand(sublime_plugin.WindowCommand):
    def run(self):
        view = self.window.active_view()
        filename = view.file_name()

        region = view.sel()[0]
        if region.empty():
            self.window.run_command('find_under_expand') # super+d
            region = view.sel()[0]

        if region.empty(): # the cursor is on whitespace not bordering any word
            sublime.message_dialog('Select an identifier you would like to rename and try again.')
            return

        current_selection = view.substr(region)
        # TODO: should we try to detect if the selected region could not be an actual renamable identifier?
        
        def on_done(new_name):
            if new_name == current_selection:
                return
            try:
                offset = filename + ':#{0}'.format(region.begin())
                env = getenv()
                args = ['gorename', '-offset', offset, '-to', new_name]
                p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = p.communicate()
                if p.returncode != 0:
                    view = get_output_view(self.window)
                    self.window.focus_view(view)
                    view.run_command('go_mode_output_insert', {'text': "go rename failed\n%s\n" % (str(e))})
            except Exception as e:
                view = get_output_view(self.window)
                self.window.focus_view(view)
                view.run_command('go_mode_output_insert', {'text': "go rename not found: %s\n" % (e)})

        self.window.show_input_panel("New name:", current_selection, on_done, None, None)


navigation_stack = []

class GoModeBack(sublime_plugin.TextCommand):
    def run(self, edit):
        if len(navigation_stack) > 0:
            self.view.window().open_file(
                navigation_stack.pop()[0], sublime.ENCODED_POSITION)

    def is_enabled(self):
        return is_go_source_view(sublime.active_window().active_view()) and len(navigation_stack) > 0

    def is_visible(self):
        return is_go_source_view(sublime.active_window().active_view())

def format_current_file(view):
    row, col = view.rowcol(view.sel()[0].a)
    return "%s:%d:%d" % (view.file_name(), row + 1, col + 1)

def navigation_stack_open(view, target):
    navigation_stack.append((format_current_file(view), target))
    view.window().open_file(target, sublime.ENCODED_POSITION)

class GoModeGoDefCommand(sublime_plugin.WindowCommand):
    def run(self):
        try:
            view = self.window.active_view()
            select = view.sel()[0]
            string_before = view.substr(sublime.Region(0, select.begin()))
            string_before.encode("utf-8")
            offset = len(bytearray(string_before, encoding = "utf8"))

            filename = view.file_name()

            args = [ "godef", "-f", filename, "-o", str(offset) ]
            env = getenv()
            p = subprocess.Popen(args, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()
            if p.returncode != 0:
                err = stderr.decode('utf-8')
                print("godef failed: %s" % (err))
                return

            location = stdout.decode("utf-8").rstrip().split(":")
            if len(location) == 3:
                navigation_stack_open(view, (location[0] + ":" + location[1] + ":" + location[2]))
        except Exception as e:
            print(e)

def log_output(out, view):
    for line in iter(out.readline, b''):
        view.run_command('go_mode_output_insert', {'text': line.decode('utf-8') })

class GoModeGoCodeDaemon:
    def __init__(self):
        self.p = None

    def fork_gocode(self):
        print("fork_gocode")
        kill_gocode()

        outputView = get_output_view(sublime.active_window())
        env = getenv()
        try:
            addr = get_setting("gocode_address", "-addr=localhost:37777")
            debug = get_setting("gocode_debug", "false")
            # XXX: Parameterize gocode addr.
            self.p = subprocess.Popen(["gocode", "-sock=tcp", addr, "-s=true", "-debug=%s" % (debug)], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            t = threading.Thread(target=log_output, args=(self.p.stdout, outputView))
            t.daemon = True # thread dies with the program
            t.start()
            t = threading.Thread(target=log_output, args=(self.p.stderr, outputView))
            t.daemon = True # thread dies with the program
            t.start()

        except Exception as e:
            outputView.run_command('go_mode_output_insert', {'text': "cannot fork gocode\n%s" % (e) })

    def kill_gocode(self):
        env = getenv()
        addr = get_setting("gocode_address", "-addr=localhost:37777")
        p = subprocess.Popen(["gocode", "-sock=tcp", addr, "close"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode != 0:
            if not self.p is None:
                self.p.terminate()
        if not self.p is None:
            self.p.wait()
            self.p = None

daemon = GoModeGoCodeDaemon()
sublime.set_timeout(lambda: daemon.fork_gocode(), 0)

def kill_gocode():
    daemon.kill_gocode()
atexit.register(kill_gocode)

class GoModeRestartGoCode(sublime_plugin.WindowCommand):
    def run(self):
        daemon.fork_gocode()

class GoModeAutocomplete(sublime_plugin.EventListener):
    def on_query_completions(self, view, prefix, locations):
        results = []
        try:
            pos = locations[0]
            env = getenv()
            p = subprocess.Popen(["gocode", "-sock=tcp", "-addr=localhost:37777", "-f=json", "autocomplete", view.file_name().encode('utf-8'), str(pos)], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            src = view.substr(sublime.Region(0, view.size()))
            stdout, stderr = p.communicate(input=src.encode())
            if p.returncode != 0:
                err = stderr.decode('utf-8')
                print("gocode failed: %s" % (err))
                return []

            try:
                j = json.loads(stdout.decode("utf8"))
            except ValueError:
                print("Not valid JSON")
                return []

            if len(j) == 2:
                for r in j[1]:
                    #results.append(['trigger': r['name'], 'contents': r['name']])
                    results.append([ r['name'], r['name']])
        except Exception as e:
            print(e)
        return results

    def on_pre_save(self, view):
        view.run_command("go_mode_go_fmt")

class GoModeCompiler:
    def __init__(self):
        self.lock = threading.Lock()
        self.targets = {}
        self.queue = queue.Queue(maxsize=0)
        self.worker = threading.Thread(target=self.do_compile)
        self.worker.setDaemon(True)
        self.worker.start()
        self.recompile_timer = None
        self.recompile_delay = 0.1

    # Run in main thread.
    def show_results(self, view, returncode, stdout, stderr):
        # clear_error_marks()       
        file_name = view.file_name().encode('utf-8')
        outputView = get_output_view(view.window())
        outputView.run_command('go_mode_output_insert', {'text': "%s\n%s" % (view.file_name(), stdout.decode("utf-8"))})

        # print("show results: view=%s file=%s" % (view, file_name))
        # print("stdout\n%s" %(stdout.decode("utf-8")))
        clear_error_marks_view(file_name)
        print(stdout.decode("utf-8"))
        lines = stdout.decode("utf-8").split('\n') 
        for l in lines:
            # XXX: Compile.
            #
            # Building tests with flymake results in file:line:col:error
            # Building a regular file with flymake results in file:line:error
            m = re.search('^([^:]+):(\d+):(?:\d+:){0,1} (.*)', l)
            if m is None:
                continue
            f = m.group(1)
            base = os.path.basename(f)
            if len(base) > len("flymake_") and base[:len("flymake_")] == "flymake_":
                base = base[len("flymake_"):]
            # All files must be in the same directory as the view.file_name()
            f = os.path.join(os.path.dirname(view.file_name()), base)
            add_error_mark(f.encode('utf-8'), int(m.group(2))-1, m.group(3))
        show_error_marks(view)

    # Run in worker thread.
    def do_compile(self):
        while True:
            (filename, view, data) = self.queue.get()
            try:
                print("-> compiling %s" %(filename))
                dirname = os.path.dirname(filename)
                flyname = "flymake_" + os.path.basename(filename)
                target_name = os.path.join(dirname, flyname)

                print("flymake `%s'" % (target_name))

                target = open(target_name, "w")
                target.truncate()
                target.write(data)
                target.close()

                args = ["goflymake", flyname]
                env = getenv()
                p = subprocess.Popen(args, cwd=dirname, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
                stdout, stderr = p.communicate()
                os.unlink(target_name)

                sublime.set_timeout(lambda view=view, code=p.returncode: self.show_results(view, code, stdout, stderr), 0)

            except Exception as e:
                print("compilation aborted: %s" % (filename))

            self.lock.acquire(True)
            del self.targets[filename]
            print("<- compiling %s - targets=%s" %(filename, self.targets))
            self.lock.release()

            self.queue.task_done()

    # Content is filename, view, string
    def compile(self, content):
        (filename, view, data) = content
        try:
            self.lock.acquire(True)
            if content[0] in self.targets:
                print("COMPILE")
                print(self.targets)
                return False

            self.targets[content[0]] = True
            self.queue.put(content)
            return True
        finally:
            self.lock.release()

c = GoModeCompiler()

# XXX: Missing some cases.
class GoModeGoFlymake(sublime_plugin.EventListener):
    def __init__(self):
        # view isn't hashable, so this is filename->view.
        self.views = {}
        self.recompile_timer = None
        # Seconds
        self.recompile_delay = 1.0

    def restart_recompile_timer(self, timeout):
        # Do a recompile now, but not another for 5s.
        if self.recompile_timer == None:
            self.recompile()
        elif self.recompile_timer != None:
            self.recompile_timer.cancel()
        self.recompile_timer = threading.Timer(timeout, sublime.set_timeout,
                                               [self.recompile, 0])
        self.recompile_timer.start()

    # Block recompiles while a compilation is in progress.
    def recompile(self):
        erase = []
        for k in self.views:
            view = self.views[k]
            if c.compile((view.file_name(), view, view.substr(sublime.Region(0, view.size())))):
                erase.append(k)
            else:
                self.restart_recompile_timer(1.0)
        for k in erase:
            del self.views[k]
        print(self.views)

    def on_modified(self, view):
        if not is_go_source_view(view):
            return

        self.views[view.file_name()] = view
        self.restart_recompile_timer(self.recompile_delay)

    def show_errors(self, view):
        if not is_go_source_view(view):
            return

        if has_error_marks(view):
            show_error_marks(view)

    def on_activated(self, view):
        self.show_errors(view)

    def on_load(self, view):
        self.show_errors(view)
