
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


def ensure_str(arg, encoding='utf-8', errors='stric'):
    if isinstance(arg, bytes):
        return arg.decode(encoding=encoding, errors=errors)
    return arg


class BBIDaily:
    def __init__(self, base_directory, jenkins=None):
        # This environment variable must be set by the caller of BBIDaily, to
        # ensure that all recursively called instances of casa_distro will use
        # the correct base_directory.
        assert os.environ['CASA_BASE_DIRECTORY'] == base_directory
        self.bbe_name = 'BBE-{0}-{1}'.format(getpass.getuser(),
                                             socket.gethostname())
        self.neuro_forge_src = osp.dirname(osp.dirname(
            osp.dirname(__file__)))
        self.casa_distro_cmd = ['pixi', 'run']
        self.casa_distro_cmd_env = {'cwd': base_directory}
        self.jenkins = jenkins
        if self.jenkins:
            if not self.jenkins.job_exists(self.bbe_name):
                self.jenkins.create_job(self.bbe_name)

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
                    'env=BRAINVISA_TEST_RUN_DATA_DIR=/casa/host/tests/test,'
                    'BRAINVISA_TEST_REF_DATA_DIR=/casa/host/tests/ref',
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
        cmd = self.casa_distro_cmd + [
            'run',
            'name={0}'.format(config['name']),
            'cwd=/casa/host/build',
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
                'cwd=/casa/host/build',
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
            commands = [o[i+2][o[i+2].find(':')+2:].strip()
                        for i in range(len(o))
                        if ': Test command:' in o[i]]
            timeouts = [o[i+1][o[i+1].find(':')+2:].strip()
                        for i in range(len(o))
                        if ': Test command:' in o[i]]
            timeouts = [x[x.find(':')+2:] for x in timeouts]
            if commands:  # skip empty command lists
                for i, command in enumerate(commands):
                    if float(timeouts[i]) < 9.999e+06:
                        command = 'timeout -k 10 %s %s' % (timeouts[i],
                                                           command)
                        commands[i] = command
                tests[label] = commands
        log_lines += ['Final test dictionary:',
                      json.dumps(tests, indent=4, separators=(',', ': '))]

        if log_config_name is None:
            log_config_name = config['name']
        self.log(log_config_name, 'get test commands', 0, '\n'.join(log_lines))
        return tests
