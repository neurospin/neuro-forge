
import sys


def help_exit():
    print('''run the pixi command in a given environment dir.
Replicates the basis of casa_distro run, essentiallly with the parameter
name=<environment>.

Ex:

run_pixi_env name=brainvisa-6.0 bv_maker sources

will perform the equivalent of:

cd brainvisa-6.0; pixi run bv_maker sources
''')
    sys.exit(1)


if __name__ == '__main__':
    import os
    import os.path as osp
    import subprocess

    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        help_exit()

    argmax = len(sys.argv)

    if '--' in sys.argv:
        argmax = sys.argv.index('--')

    wd = os.getcwd()
    old_wd = wd
    cd = None
    args = []
    env_dict = {}

    for arg in sys.argv[1:argmax]:
        if arg.startswith('name='):
            env_name = arg[5:]
            wd = osp.join(os.getcwd(), env_name)
            continue
        if arg.startswith('cwd='):
            cd = arg[4:]
            if not osp.isabs(cd):
                cd = osp.join(old_wd, cd)
            continue
        if arg.startswith('env='):
            envs = arg[4:].split(',')
            for e in envs:
                var, val = e.split('=')
                env_dict[var] = val

        args.append(arg)

    args += sys.argv[argmax + 1:]
    if args[0] == 'run':  # the default run action
        args = args[1:]

    cmd = ['pixi', 'run']
    if cd is not None:
        # WARNING quotes are not properly handled
        cmd.append(f'cd {cd}; {" ".join(args)}')
    else:
        cmd += args

    env = dict(os.environ)
    env.update(env_dict)
    subprocess.check_call(cmd, cwd=wd, env=env)
