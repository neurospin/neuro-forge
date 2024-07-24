
import os
import os.path as osp
import getpass
import socket
import sys
import subprocess
import locale
import shlex
import time
import re
import json
import traceback
import shutil


def ensure_str(arg, encoding='utf-8', errors='stric'):
    if isinstance(arg, bytes):
        return arg.decode(encoding=encoding, errors=errors)
    return arg


class BBIDaily:
    NONFATAL_BV_MAKER_STEPS = {'doc', 'test'}
    """bv_maker steps whose failure still allows to proceed to further testing."""

    def __init__(self, base_directory, jenkins=None):
        # This environment variable must be set by the caller of BBIDaily, to
        # ensure that all recursively called instances of casa_distro will use
        # the correct base_directory.
        assert os.environ['CASA_BASE_DIRECTORY'] == base_directory
        self.bbe_name = 'BBE-{0}-{1}'.format(getpass.getuser(),
                                             socket.gethostname())
        self.neuro_forge_src = osp.dirname(osp.dirname(
            osp.dirname(__file__)))
        self.casa_distro_cmd = [
            sys.executable,
            osp.join(osp.dirname(__file__), 'run_pixi_env.py')]
        self.casa_distro_cmd_env = {'cwd': base_directory}
        self.jenkins = jenkins
        if self.jenkins:
            if not self.jenkins.job_exists(self.bbe_name):
                self.jenkins.create_job(self.bbe_name)
        self.env_prefix = '{environment_dir}'

    def log(self, environment, task_name, result, log,
            duration=None):
        if self.jenkins:
            self.jenkins.create_build(environment=environment,
                                      task=task_name,
                                      result=result,
                                      log=log+'\n',
                                      duration=duration)
        else:
            name = '{0}:{1}'.format(environment, task_name)
            print()
            print('  /-' + '-' * len(name) + '-/')
            print(' / ' + name + ' /')
            print('/-' + '-' * len(name) + '-/')
            print()
            print(log)

    def call_output(self, args, **kwargs):
        if self.casa_distro_cmd_env:
            kwargs2 = dict(self.casa_distro_cmd_env)
            kwargs2.update(kwargs)
            kwargs = kwargs2
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, bufsize=-1,
                             **kwargs)
        output, nothing = p.communicate()
        if isinstance(output, bytes):
            output = output.decode(encoding=locale.getpreferredencoding(),
                                   errors='backslashreplace')
        log = ['-'*40,
               '$ ' + ' '.join(shlex.quote(ensure_str(arg))
                               for arg in args),
               '-'*40,
               output]

        return p.returncode, '\n'.join(log)

    def update_casa_distro(self):
        start = time.time()
        result, log = self.call_output(['git',
                                        '-C', self.neuro_forge_src,
                                        'pull'])
        duration = int(1000 * (time.time() - start))
        self.log(self.bbe_name, 'update neuro-forge',
                 result, log,
                 duration=duration)
        return result == 0

    def bv_maker(self, config, steps):
        environment = config['name']
        if self.jenkins:
            if not self.jenkins.job_exists(environment):
                self.jenkins.create_job(environment,
                                        **config)
        done = []
        failed = []
        for step in steps:
            start = time.time()
            result, log = self.call_output(self.casa_distro_cmd + [
                'bv_maker',
                'name={0}'.format(config['name']),
                '--',
                step,
            ])
            duration = int(1000 * (time.time() - start))
            self.log(environment, step, result, log, duration=duration)
            if result:
                failed.append(step)
                break  # stop on the first failed step
            else:
                done.append(step)
        return (done, failed)

    def tests(self, test_config, dev_config):
        environment = test_config['name']
        if self.jenkins:
            if not self.jenkins.job_exists(environment):
                self.jenkins.create_job(environment,
                                        **test_config)
        # get test commands dict, and log it in the test config log (which may
        # be the dev log or the user image log)
        tests = self.get_test_commands(dev_config,
                                       log_config_name=test_config['name'])
        successful_tests = []
        failed_tests = []
        env_dir = self.env_prefix.format(
            environment_dir=test_config['directory'])
        srccmdre = re.compile('/casa/host/src/.*/bin/')
        for test, commands in tests.items():
            log = []
            start = time.time()
            success = True
            for command in commands:
                if test_config['type'] in ('run', 'user'):
                    # replace paths in build dir with install ones
                    command = command.replace('/casa/host/build',
                                              '/casa/install')
                    # replace paths in sources with install ones
                    command = srccmdre.sub('/casa/install/bin/', command)
                result, output = self.call_output(self.casa_distro_cmd + [
                    'run',
                    'name={0}'.format(test_config['name']),
                    f'env=BRAINVISA_TEST_RUN_DATA_DIR={env_dir}/tests/test,'
                    f'BRAINVISA_TEST_REF_DATA_DIR={env_dir}/tests/ref',
                    '--',
                    'sh', '-c', command
                ])
                log.append('=' * 80)
                log.append(output)
                log.append('=' * 80)
                if result:
                    success = False
                    if result in (124, 128+9):
                        log.append('TIMED OUT (exit code {0})'.format(result))
                    else:
                        log.append('FAILED with exit code {0}'
                                   .format(result))
                else:
                    log.append('SUCCESS (exit code {0})'.format(result))
            duration = int(1000 * (time.time() - start))
            self.log(environment, test, (0 if success else 1),
                     '\n'.join(log), duration=duration)
            if success:
                successful_tests.append(test)
            else:
                failed_tests.append(test)
        if failed_tests:
            self.log(environment, 'tests failed', 1,
                     'The following tests failed: {0}'.format(
                         ', '.join(failed_tests)))
        return (successful_tests, failed_tests)

    def get_test_commands(self, config, log_config_name=None):
        '''
        Given the config of a dev environment, return a dictionary
        whose keys are name of a test (i.e. 'axon', 'soma', etc.) and
        values are a list of commands to run to perform the test.
        '''
        env_dir = self.env_prefix.format(
            environment_dir=config['directory'])
        cmd = self.casa_distro_cmd + [
            'run',
            'name={0}'.format(config['name']),
            f'cwd={env_dir}/build',
            '--',
            'ctest', '--print-labels'
        ]
        # universal_newlines is the old name to request text-mode (text=True)
        o = subprocess.check_output(cmd, bufsize=-1,
                                    universal_newlines=True)
        labels = [i.strip() for i in o.split('\n')[2:] if i.strip()]
        log_lines = ['$ ' + ' '.join(shlex.quote(arg) for arg in cmd),
                     o, '\n']
        tests = {}
        for label in labels:
            cmd = self.casa_distro_cmd + [
                'run',
                'name={0}'.format(config['name']),
                f'cwd={env_dir}/build',
                'env=BRAINVISA_TEST_REMOTE_COMMAND=echo',
                '--',
                'ctest', '-V', '-L',
                '^{0}$'.format(label)
            ] + config.get('ctest_options', [])
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, bufsize=-1,
                                 universal_newlines=True)
            o, stderr = p.communicate()
            log_lines += ['$ ' + ' '.join(shlex.quote(arg) for arg in cmd),
                          o, '\n']
            if p.returncode != 0:
                # We want to hide stderr unless ctest returns a nonzero exit
                # code. In the case of test filtering where no tests are
                # matched (e.g. with ctest_options=['-R', 'dummyfilter']), the
                # annoying message 'No tests were found!!!' is printed to
                # stderr by ctest, but it exits with return code 0.
                sys.stderr.write(stderr)
                log_lines.append('Error in get_test_commands:')
                log_lines.append('get_test_commands command:')
                log_lines.append("'" + "' '".join(cmd) + "'")
                log_lines.append('Error:')
                log_lines.append(stderr)
                self.log(log_config_name, 'get test commands', 0,
                         '\n'.join(log_lines))
                raise RuntimeError('ctest failed with the above error')
            o = o.split('\n')
            # Extract the third line that follows each line containing ': Test
            # command:'
            commands = []
            cis = [i for i in range(len(o)) if ': Test command:' in o[i]]
            for i, ci in enumerate(cis):
                if i < len(cis) - 1:
                    cinext = cis[i+1]
                else:
                    cinext = len(o)
                command = o[ci][o[ci].find(':')+2:].strip()
                command = command[command.find(':')+2:].strip()
                timeout = None
                for j in range(ci+1, cinext):
                    if 'Test timeout' in o[j]:
                        timeout = o[j][o[j].find(':')+2:].strip()
                        timeout = timeout[timeout.find(':')+2:]
                        timeout = float(timeout)
                        break
                if timeout is not None and timeout < 9.999e+06:
                    command = 'timeout -k 10 %s %s' % (timeout, command)
                commands.append(command)

            if commands:  # skip empty command lists
                tests[label] = commands
        log_lines += ['Final test dictionary:',
                      json.dumps(tests, indent=4, separators=(',', ': '))]

        if log_config_name is None:
            log_config_name = config['name']
        self.log(log_config_name, 'get test commands', 0, '\n'.join(log_lines))
        return tests

    def build_packages(self, config):
        env_dir = self.env_prefix.format(
            environment_dir=config['directory'])
        cmd = ['pixi', 'run', 'soma-forge', 'dev-packages-plan', '--test',
               '0', env_dir]
        log = ['buid packages plan', 'command:', ' '.join(cmd), 'from dir:',
               self.neuro_forge_src]
        environment = config['name']
        self.log(environment, 'buid packages plan', 1,
                 '\n'.join(log), duration=0)
        start = time.time()
        result, output = self.call_output(cmd, cwd=self.neuro_forge_src)
        log = []
        log.append('=' * 80)
        log.append(output)
        log.append('=' * 80)
        success = True
        if result:
            success = False
            if result in (124, 128+9):
                log.append('TIMED OUT (exit code {0})'.format(result))
            else:
                log.append('FAILED with exit code {0}'.format(result))
        else:
            log.append('SUCCESS (exit code {0})'.format(result))

        duration = int(1000 * (time.time() - start))
        self.log(environment, 'packaging', (0 if success else 1),
                 '\n'.join(log), duration=duration)
        if not success:
            self.log(environment, 'packaging failed', 1,
                     'The packaging plan failed.')

        if success:
            # pack
            cmd = ['pixi', 'run', 'soma-forge', 'apply-plan',
                   env_dir]
            log = ['buid packages plan', 'command:', ' '.join(cmd),
                   'from dir:', self.neuro_forge_src]
            self.log(environment, 'buid packages', 1,
                     '\n'.join(log), duration=0)
            start = time.time()
            result, output = self.call_output(cmd, cwd=self.neuro_forge_src)
            log = []
            log.append('=' * 80)
            log.append(output)
            log.append('=' * 80)
            success = True
            if result:
                success = False
                if result in (124, 128+9):
                    log.append('TIMED OUT (exit code {0})'.format(result))
                else:
                    log.append('FAILED with exit code {0}'
                               .format(result))
            else:
                log.append('SUCCESS (exit code {0})'.format(result))

            duration = int(1000 * (time.time() - start))
            self.log(environment, 'packaging', (0 if success else 1),
                     '\n'.join(log), duration=duration)
            if not success:
                self.log(environment, 'packaging failed', 1,
                         'The packaging failed.')

        return success

    def read_packages_list(self, dev_config):
        with open(osp.join(dev_config['directory'], 'conf',
                           'build_info.json')) \
                as f:
            binfo = json.load(f)
        history_f = osp.join(dev_config['directory'], 'plan', 'history.json')
        history = {}
        if osp.exists(history_f):
            with open(history_f) as f:
                history = json.load(f)
        build_str = f'{binfo["build_string"]}_{binfo["build_number"]}'
        packages = {p: {'build': f'{build_str}'} for p in binfo['packages']}
        if history:
            for p, d in packages.items():
                ver = history.get(p)['version']
                d['version'] = ver  # f'{ver}={d["build"]}'
        return packages

    def recreate_user_env(self, user_config, dev_config):
        environment = user_config['name']
        if self.jenkins:
            if not self.jenkins.job_exists(environment):
                self.jenkins.create_job(environment,
                                        **user_config)
        start = time.time()
        env_dir = user_config['directory']
        dev_env_dir = osp.abspath(dev_config['directory'])
        if os.path.exists(env_dir):
            shutil.rmtree(env_dir)
        os.makedirs(env_dir)
        cmd = ['pixi', 'init', '-c', f'file://{dev_env_dir}/packages',
               '-c', 'https://brainvisa.info/neuro-forge',
               '-c', 'nvidia', '-c', 'pytorch', '-c', 'conda-forge']
        log = ['create user environment', 'command:', ' '.join(cmd),
               'from dir:', env_dir]
        self.log(environment, 'create user environment', 1,
                 '\n'.join(log), duration=0)
        result, output = self.call_output(cmd, cwd=env_dir)
        log = []
        log.append('=' * 80)
        log.append(output)
        log.append('=' * 80)
        success = True
        if result:
            success = False
            if result in (124, 128+9):
                log.append('TIMED OUT (exit code {0})'.format(result))
            else:
                log.append('FAILED with exit code {0}'.format(result))
        else:
            log.append('SUCCESS (exit code {0})'.format(result))

        duration = int(1000 * (time.time() - start))
        self.log(environment, 'create user environment',
                 (0 if success else 1),
                 '\n'.join(log), duration=duration)
        if not success:
            self.log(environment, 'create user environment failed', 1,
                     'The enviroment init failed.')

        if success:
            start = time.time()
            packages = self.read_packages_list(dev_config)
            # TODO: I cannot find out how to specify build in
            # install constraints
            packages_list = [f'{p}={packages[p]["version"]}'
                             for p in sorted(packages)]
            cmd = ['pixi', 'add'] + packages_list
            log = ['install packages', 'command:', ' '.join(cmd),
                   'from dir:', env_dir]
            self.log(environment, 'install packages', 1,
                     '\n'.join(log), duration=0)
            result, output = self.call_output(cmd, cwd=env_dir)
            log = []
            log.append('=' * 80)
            log.append(output)
            log.append('=' * 80)
            if result:
                success = False
                if result in (124, 128+9):
                    log.append('TIMED OUT (exit code {0})'.format(result))
                else:
                    log.append('FAILED with exit code {0}'.format(result))
            else:
                log.append('SUCCESS (exit code {0})'.format(result))

            duration = int(1000 * (time.time() - start))
            self.log(environment, 'install packages',
                     (0 if success else 1),
                     '\n'.join(log), duration=duration)
            if not success:
                self.log(environment, 'create user environment failed', 1,
                         'The packages installation failed.')

        return success

    def run_bbi(self, dev_configs, user_configs,
                bv_maker_steps='sources,configure,build,doc',
                dev_tests=True, pack=True, install_packages=True,
                user_tests=True):
        successful_tasks = []
        failed_tasks = []
        try:
            if bv_maker_steps:
                bv_maker_steps = bv_maker_steps.split(',')

            for dev_config, user_config in zip(dev_configs, user_configs):
                # doc_build_success = False
                if bv_maker_steps:
                    successful, failed = self.bv_maker(dev_config,
                                                       bv_maker_steps)
                    successful_tasks.extend(
                        '{0}: {1}'.format(dev_config['name'], i)
                        for i in successful)
                    failed_tasks.extend(
                        '{0}: {1}'.format(dev_config['name'], i)
                        for i in failed)
                    if set(failed) - self.NONFATAL_BV_MAKER_STEPS:
                        # There is no point in running tests
                        # if compilation failed.
                        continue
                    # doc_build_success = ('doc' in successful)

                if dev_tests:
                    successful, failed = self.tests(dev_config, dev_config)
                    successful_tasks.extend(
                        '{0}: {1}'.format(dev_config['name'], i)
                        for i in successful)
                    failed_tasks.extend('{0}: {1}'.format(dev_config['name'],
                                                          i)
                                        for i in failed)

                if pack:
                    success = self.build_packages(dev_config)
                    if success:
                        successful_tasks.append(
                            '{0}: build_packages'.format(dev_config['name']))
                    else:
                        failed_tasks.append(
                            '{0}: build_packages'.format(dev_config['name']))

                if install_packages:
                    success = self.recreate_user_env(user_config, dev_config)

                if user_tests:
                    successful, failed = self.tests(user_config, dev_config)
                    successful_tasks.extend(
                        '{0}: {1}'.format(user_config['name'], i)
                        for i in successful)
                    failed_tasks.extend('{0}: {1}'.format(user_config['name'],
                                                          i)
                                        for i in failed)

        except Exception:
            log = ['Successful tasks']
            log.extend('  - {0}'.format(i) for i in successful_tasks)
            if failed_tasks:
                log .append('Failed tasks')
                log.extend('  - {0}'.format(i) for i in failed_tasks)
            log += ['', 'ERROR:', '', traceback.format_exc()]
            self.log(self.bbe_name, 'error', 1, '\n'.join(log))
        else:
            log = ['Successful tasks']
            log.extend('  - {0}'.format(i) for i in successful_tasks)
            if failed_tasks:
                log .append('Failed tasks')
                log.extend('  - {0}'.format(i) for i in failed_tasks)
            self.log(self.bbe_name, 'finished',
                     (1 if failed_tasks else 0), '\n'.join(log))


if __name__ == '__main__':

    import argparse

    base_directory = os.getcwd()
    jenkins_server = None
    jenkins_auth = '{base_directory}/jenkins_auth'

    parser = argparse.ArgumentParser(
        description='run tests for a Conda-based build of BrainVisa, and log '
        'to a Jenkins server. Can also test installed packages.')
    parser.add_argument('-b', '--base_directory',
                        help='environment directory. default: '
                        f'{base_directory}',
                        default=base_directory)
    parser.add_argument('-e', '--environment', action='append',
                        help='environment dirs to run BBI on. '
                        'default: [<current_dir>]', default=[])
    parser.add_argument('-j', '--jenkins_server',
                        help='Jenkins server URL.',
                        default=jenkins_server)
    parser.add_argument('-a', '--jenkins_auth',
                        help=f'Jenkins auth file. default: {jenkins_auth}',
                        default=jenkins_auth)
    parser.add_argument('--bv_maker_steps',
                        help='Coma separated list of bv_maker commands to '
                        'perform on dev environments. May be empty to do '
                        'nothing. default: sources,configure,build,doc',
                        default='sources,configure,build,doc')
    parser.add_argument('--dev_tests',
                        action=argparse.BooleanOptionalAction,
                        help='Perform dev build tree tests. default: true',
                        default=True)
    parser.add_argument('--pack',
                        action=argparse.BooleanOptionalAction,
                        help='Perform dev build tree packaging. '
                        'default: true', default=True)
    parser.add_argument('--install_packages',
                        action=argparse.BooleanOptionalAction,
                        help='Install packages in a user environment. '
                        'default: true', default=True)
    parser.add_argument('--user_tests',
                        action=argparse.BooleanOptionalAction,
                        help='Perform installed packages tests (as a user '
                        'install). default: true',
                        default=True)

    args = parser.parse_args(sys.argv[1:])

    base_directory = args.base_directory
    jenkins_server = args.jenkins_server
    jenkins_auth = args.jenkins_auth
    environments = args.environment
    bv_maker_steps = args.bv_maker_steps
    dev_tests = args.dev_tests
    user_tests = args.user_tests
    pack = args.pack
    install_packages = args.install_packages
    if len(environments) == 0:
        environments = [osp.basename(os.getcwd())]
        base_directory = osp.dirname(os.getcwd())
    base_directory = osp.abspath(base_directory)
    # print('base:', base_directory)
    # print('jenkins:', jenkins_server)
    # print('auth:', jenkins_auth)
    # print('envs:', environments)
    # print('dev tests:', dev_tests)
    # print('pack:', dev_tests)

    # Ensure that all recursively called instances of casa_distro will use
    # the correct base_directory.
    os.environ['CASA_BASE_DIRECTORY'] = base_directory

    if jenkins_server:
        # Import jenkins only if necessary to avoid dependency
        # on requests module
        try:
            from .jenkins import BrainVISAJenkins
        except ImportError:
            sys.path.append(osp.dirname(osp.dirname(osp.dirname(__file__))))
            from neuro_forge.soma_forge.jenkins import BrainVISAJenkins

        jenkins_auth = jenkins_auth.format(base_directory=base_directory)
        with open(jenkins_auth) as f:
            jenkins_login, jenkins_password = [i.strip() for i in
                                               f.readlines()[:2]]
        jenkins = BrainVISAJenkins(jenkins_server, jenkins_login,
                                   jenkins_password)
    else:
        jenkins = None

    dev_configs = [{'name': osp.basename(e),
                    'directory': osp.join(base_directory, e),
                    'type': 'dev'}
                   for e in environments]
    user_configs = [{'name': e['name'] + '_user',
                     'directory': e['directory'] + '_user',
                     'type': 'user'}
                    for e in dev_configs]

    bbi_daily = BBIDaily(base_directory, jenkins=jenkins)
    bbi_daily.run_bbi(dev_configs, user_configs, bv_maker_steps, dev_tests,
                      pack, install_packages, user_tests)
