import os
from subprocess import Popen, PIPE
from tempfile import gettempdir
from uuid import uuid4
from ..conf import settings
from ..const import ARGUMENT_PLACEHOLDER, USER_COMMAND_MARK
from ..utils import DEVNULL, memoize
from .generic import Generic

branch_coverage = {
    "instant_mode_alias_if": False,  # if THEFUCK_INSTANT_MODE is 'true'
    "instant_mode_alias_else": False,  # if THEFUCK_INSTANT_MODE is not 'true'
    "how_to_configure_if": False,  # if ~/.bashrc exists
    "how_to_configure_elif": False,  # if ~/.bash_profile exists
    "how_to_configure_else": False  # if neither ~/.bashrc nor ~/.bash_profile exists
}


class Bash(Generic):
    friendly_name = 'Bash'

    def print_coverage(self):
        covered = 0
        total_branches = len(branch_coverage)

        for key in branch_coverage:
            if branch_coverage[key]:
                covered += 1

        coverage_percentage = (covered / total_branches) * 100

        print("\n")
        for branch, hit in branch_coverage.items():
            print(f"{branch} was {'HIT' if hit else 'not hit'}\n")
        print(f"\nBranch coverage: {coverage_percentage:.2f}%\n")


    def app_alias(self, alias_name):
        # It is VERY important to have the variables declared WITHIN the function
        return '''
            function {name} () {{
                TF_PYTHONIOENCODING=$PYTHONIOENCODING;
                export TF_SHELL=bash;
                export TF_ALIAS={name};
                export TF_SHELL_ALIASES=$(alias);
                export TF_HISTORY=$(fc -ln -10);
                export PYTHONIOENCODING=utf-8;
                TF_CMD=$(
                    thefuck {argument_placeholder} "$@"
                ) && eval "$TF_CMD";
                unset TF_HISTORY;
                export PYTHONIOENCODING=$TF_PYTHONIOENCODING;
                {alter_history}
            }}
        '''.format(
            name=alias_name,
            argument_placeholder=ARGUMENT_PLACEHOLDER,
            alter_history=('history -s $TF_CMD;'
                           if settings.alter_history else ''))

    def instant_mode_alias(self, alias_name):
        if os.environ.get('THEFUCK_INSTANT_MODE', '').lower() == 'true':
            branch_coverage["instant_mode_alias_if"] = True
            mark = USER_COMMAND_MARK + '\b' * len(USER_COMMAND_MARK)
            return '''
                export PS1="{user_command_mark}$PS1";
                {app_alias}
            '''.format(user_command_mark=mark,
                       app_alias=self.app_alias(alias_name))
        else:
            branch_coverage["instant_mode_alias_else"] = True
            log_path = os.path.join(
                gettempdir(), 'thefuck-script-log-{}'.format(uuid4().hex))
            return '''
                export THEFUCK_INSTANT_MODE=True;
                export THEFUCK_OUTPUT_LOG={log};
                thefuck --shell-logger {log};
                rm {log};
                exit
            '''.format(log=log_path)

    def _parse_alias(self, alias):
        name, value = alias.replace('alias ', '', 1).split('=', 1)
        if value[0] == value[-1] == '"' or value[0] == value[-1] == "'":
            value = value[1:-1]
        return name, value

    @memoize
    def get_aliases(self):
        raw_aliases = os.environ.get('TF_SHELL_ALIASES', '').split('\n')
        return dict(self._parse_alias(alias)
                    for alias in raw_aliases if alias and '=' in alias)

    def _get_history_file_name(self):
        return os.environ.get("HISTFILE",
                              os.path.expanduser('~/.bash_history'))

    def _get_history_line(self, command_script):
        return u'{}\n'.format(command_script)

    def how_to_configure(self):
        if os.path.join(os.path.expanduser('~'), '.bashrc'):
            branch_coverage["how_to_configure_if"] = True
            config = '~/.bashrc'
        elif os.path.join(os.path.expanduser('~'), '.bash_profile'):
            branch_coverage["how_to_configure_elif"] = True
            config = '~/.bash_profile'
        else:
            branch_coverage["how_to_configure_else"] = True
            config = 'bash config'

        return self._create_shell_configuration(
            content=u'eval "$(thefuck --alias)"',
            path=config,
            reload=u'source {}'.format(config))

    def _get_version(self):
        """Returns the version of the current shell"""
        proc = Popen(['bash', '-c', 'echo $BASH_VERSION'],
                     stdout=PIPE, stderr=DEVNULL)
        return proc.stdout.read().decode('utf-8').strip()