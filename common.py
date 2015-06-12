import sublime
import os
import subprocess

def get_settings():
    return sublime.load_settings("GoMode.sublime-settings")

def get_setting(key, default=None, view=None):
    try:
        if view == None:
            view = sublime.active_window().active_view()
        s = view.settings()
        if s.has("go_%s" % key):
            return s.get("go_%s" % key)
    except:
        pass
    return get_settings().get(key, default)

def getenv():
    env = os.environ.copy()
    userenv = get_setting("env")
    for k in userenv:
        env[k] = os.path.expandvars(userenv[k])
    return env

def openProcess(args,env=None,cwd=None,stdin=None,stdout=None,stderr=None):
    startupinfo = None

    if os.name == 'nt':
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    proc = subprocess.Popen(args,bufsize=-1,env=env,cwd=cwd,stdin=stdin,stdout=stdout,stderr=stderr,startupinfo=startupinfo)
    return proc
