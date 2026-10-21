"""Local PyInstaller hook for the webrtcvad-wheels distribution.

The contrib hook calls copy_metadata('webrtcvad'), but the installed
package is distributed as 'webrtcvad-wheels'. Avoid that mismatched
metadata lookup and include the native extension explicitly.
"""
hiddenimports = ['_webrtcvad']
