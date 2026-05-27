import sublime
import sublime_plugin
import subprocess
import os
import threading
import shutil
from functools import partial
from pathlib import PurePath


def get_setting(window_command, setting):
    '''
    Sublime merges everything, including project settings, into view.settings
    Package specific settings can be set via namespaced dot-syntax everywhere
    '''
    defaults = sublime.load_settings("SideBarTools.sublime-settings")
    default_tool = defaults.get(setting)

    try:
        # some views, e.g. of images, don't have settings
        merged_settings = window_command.window.active_view().settings()
        return merged_settings.get('SideBarTools.' + setting, default_tool)
    except Exception:
        return None


class SideBarCommand(sublime_plugin.WindowCommand):

    def is_visible(self, paths=[], context='', style='', **kwargs):
        if context == 'tab' and not get_setting(self, 'tab_context'):
            return False

        paths = self.get_paths(paths, context, **kwargs)
        for path in paths:
            if path is None:
                return False

        return bool(paths)

    def get_paths(self, paths, context='', **kwargs):
        # paths is only filled on side bar context
        # for command palette and tab context we need to find the path
        return paths or [self.get_path(paths, context, **kwargs)]

    def get_path(self, paths=[], context="", group=-1, index=-1):
        try:
            return paths[0]
        except IndexError:
            return self.file_via_window(context, group, index)

    def file_via_window(self, context='', group=-1, index=-1):
        w = self.window
        if context == 'tab':
            try:
                vig = w.views_in_group(group)
                return vig[index].file_name()
            except IndexError:
                sig = w.sheets_in_group(group)
                return sig[index].file_name()
        return w.active_view().file_name()

    def copy_to_clipboard_and_inform(self, paths=[]):
        sublime.set_clipboard('\n'.join(paths))

        lines = len(paths)
        self.window.status_message('Copied {} to clipboard'.format(
            '{} lines'.format(lines) if lines > 1 else '"{}"'.format(paths[0])
        ))

    @staticmethod
    def make_dirs_for(filename):
        destination_dir = os.path.dirname(filename)
        try:
            os.makedirs(destination_dir)
            return True
        except OSError:
            # TODO: It would be nice to surface this error to the user...
            return False


class SideBarCopyNameCommand(SideBarCommand):

    def run(self, paths=[], **kwargs):
        names = [os.path.split(path)[1] for path in self.get_paths(paths, **kwargs)]
        self.copy_to_clipboard_and_inform(names)


class SideBarRenameCommand(SideBarCommand):

    def run(self, paths=[], **kwargs):
        self.window.run_command('rename_path', {'paths': self.get_paths(paths, **kwargs)})


class SideBarCopyAbsolutePathCommand(SideBarCommand):

    def is_visible(self, paths=[], context='', **kwargs):
        # in 4158 ST gets the "copy path" sidebar context entry for single files
        # we also want to keep our command palette and tab context entries
        if len(self.get_paths(paths, context, **kwargs)) <= 1:
            if context not in ['palette', 'tab']:
                if int(sublime.version()) >= 4158:
                    return False
        return super().is_visible(paths, context, **kwargs)

    def run(self, paths=[], **kwargs):
        paths = self.get_paths(paths, **kwargs)
        self.copy_to_clipboard_and_inform(paths)


class SideBarDeleteCommand(SideBarCommand):

    def is_visible(self, paths=[], context='', **kwargs):
        # can only delete files that exist on disk
        for path in self.get_paths(paths, context, **kwargs):
            if path is None:
                return False
            if not os.path.exists(path):
                return False
        return super().is_visible(paths, context, **kwargs)

    def run(self, paths=[], **kwargs):
        paths = self.get_paths(paths, **kwargs)
        self.window.run_command('delete_file', {'files': paths, 'prompt': True})


class SideBarOpenCommand(SideBarCommand):

    def run(self, paths=[], **kwargs):
        for path in self.get_paths(paths, **kwargs):
            self.window.run_command('open_dir', {'dir': os.path.dirname(path), 'file': os.path.basename(path)})


class RemoveFolderListener(sublime_plugin.EventListener):

    def on_post_window_command(self, window, command_name, args):
        if command_name == 'delete_folder':
            for folder in window.project_data()['folders']:
                if not os.path.exists(os.path.expanduser(folder['path'])):
                    window.run_command(
                        'remove_folder',
                        {
                            'dirs': [folder['path']]
                        })
