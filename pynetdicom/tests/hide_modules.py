"""Hide modules from import

 ModuleHider - import finder hook and context manager
 hide_modules - decorator using ModuleHider

https://github.com/roryyorke/py-hide-modules
"""

# Copyright (c) 2019 Rory Yorke
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

try:
    import importlib.abc
    # py>=3.3 has MetaPathFinder
    _ModuleHiderBase = getattr(importlib.abc, 'MetaPathFinder',
                               importlib.abc.Finder)
except ImportError:
    # py2
    _ModuleHiderBase = object


class ModuleHider(_ModuleHiderBase):
    """Import finder hook to hide specified modules
    ModuleHider(hidden_modules) -> instance
    hidden_modules is a list of strings naming modules to hide.
    """

    def __init__(self, hidden):
        self.hidden = hidden
        self.hidden_modules = {}

    # python <=3.3
    def find_module(self, fullname, path=None):
        return self.find_spec(fullname, path)

    # python >=3.4
    def find_spec(self, fullname, path, target=None):
        if fullname in self.hidden:
            raise ImportError('No module named {}'.format(fullname))

    def hide(self):
        "Starting hiding modules"
        import sys
        if self in sys.meta_path:
            raise RuntimeError("Already hiding modules")
        # must be first to override standard finders
        sys.meta_path.insert(0, self)
        # remove hidden modules to force reload
        for m in self.hidden:
            if m in sys.modules:
                self.hidden_modules[m] = sys.modules[m]
                del sys.modules[m]

    def unhide(self):
        "Unhide modules"
        import sys
        sys.meta_path.remove(self)
        sys.modules.update(self.hidden_modules)
        self.hidden_modules.clear()

    def __enter__(self):
        self.hide()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unhide()

    # there's much point in __del__: sys.meta_path will keep a
    # reference to an object on which .unhide() is not called, so
    # refcount will only go to 0 if the object is removed from
    # sys.meta_path somehow (in which case deletion doesn't
    # matter), or when Python exits (ditto)


def hide_modules(hidden):
    """hide_modules(hidden_modules) -> decorator

    When decorated function is called, the specified list of modules
    will be hidden; once the function exits, the modules will be
    unhidden.
    """
    def applydec(f):
        def decf(*args, **kwargs):
            with ModuleHider(hidden):
                f(*args, **kwargs)
        # carry across name so that nose still finds the test
        decf.__name__ = f.__name__
        # and carry across doc for test descriptions (etc.)
        decf.__doc__ = f.__doc__
        return decf
    return applydec
