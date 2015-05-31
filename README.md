GoMode
=======

Intro
-----

A new GoMode for [SublimeText](http://www.sublimetext.com/). Only Sublime Text 3 is supported, and I've
only tested on OSX.

Features
--------

* godef
* gorename
* gofmt/goimports
* oracle
* gocode (for code completion)
* goflymake for syntax checking as you type

Installation
------------

Use Sublime Package Control (if you haven't done so already) from http://wbond.net/sublime_packages/package_control.

You must also have godef, oracle, gorename, gocode and goflymake in your path. If you don't have them installed
you can use the `GoMode: Install Binaries' command to "go get" the binaries.

Settings
--------

You can customize the behaviour of GoMode by creating a settings file in your `User` package. This can be accessed from within SublimeText by going to the menu `Preferences > Browse Packages...`. Create a file named `GoMode.sublime-settings` or alternatively copy the default settings file `Packages/GoMode/GoMode.sublime-settings` to your `User` package and edit it to your liking.

The most important thing is to set your PATH and GOPATH in the settings file:

    "env": {
		"GOPATH": "$HOME/src/gostuff",
		"PATH": "/usr/local/bin:$HOME/src/services/bin:$PATH"
	},

Copyright, License & Contributors
=================================

GoMode is released under the 3 clause BSD license. See [LICENSE.md](LICENSE.md)

The code is derived (sometimes substantially) from the following packages:

* https://github.com/DisposaBoy/GoSublime
* https://github.com/buaazp/Godef
* https://github.com/smartystreets/sublime-gorename
* https://github.com/quarnster/SublimeClang
* https://github.com/waigani/GoOracle
* https://github.com/wbond/package_control