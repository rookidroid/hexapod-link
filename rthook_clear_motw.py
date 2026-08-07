"""PyInstaller runtime hook: clear the Mark of the Web from the bundled DLLs.

Windows stamps a downloaded .zip with a Zone.Identifier alternate data stream,
and Explorer copies that stamp onto every file it extracts. The .NET Framework
then refuses to load a managed assembly carrying it: Assembly.LoadFrom returns
nothing rather than raising, which surfaces from pythonnet as

    RuntimeError: Failed to resolve Python.Runtime.Loader.Initialize from
    ...\\_internal\\pythonnet\\runtime\\Python.Runtime.dll

That is the whole window failing to open, because pywebview's Windows backend
is winforms through pythonnet. The same block applies to the WebView2 interop
assemblies in webview/lib, which the backend loads by path as well.

So it only ever bites people who ran the published build rather than one they
built themselves -- and every file in the bundle, not just the app itself, has
to be unblocked. Dropping the stream is exactly what the Unblock checkbox in
the file properties dialog does; nothing else about the file changes.

Runtime hooks run before the main script, so this happens before anything
imports webview.
"""

import os
import sys


def clear_motw(directory):
    """Remove the Zone.Identifier stream from every DLL under `directory`."""
    for root, _directories, names in os.walk(directory):
        for name in names:
            if not name.lower().endswith(".dll"):
                continue
            try:
                os.remove(os.path.join(root, name) + ":Zone.Identifier")
            except OSError:
                # Almost always "no such stream", i.e. the file was never
                # marked. It can also be a read-only install directory, where
                # there is nothing to be done and failing here would be worse
                # than letting the app try to start.
                pass


if sys.platform == "win32" and getattr(sys, "frozen", False):
    clear_motw(sys._MEIPASS)
