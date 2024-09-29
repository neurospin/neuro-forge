# def test_ref():
#     test_ref_data_dir = os.environ.get("BRAINVISA_TEST_REF_DATA_DIR")
#     if not test_ref_data_dir:
#         print("No value for BRAINVISA_TEST_REF_DATA_DIR", file=sys.stderr, flush=True)
#         return 1
#     os.makedirs(test_ref_data_dir, exists_ok=True)


# def test(name):
#     test_commands = get_test_commands()
#     if name is None:
#         print(", ".join(test_commands))
#     else:
#         test_run_data_dir = os.environ.get("BRAINVISA_TEST_RUN_DATA_DIR")
#         if not test_run_data_dir:
#             print(
#                 "No value for BRAINVISA_TEST_RUN_DATA_DIR", file=sys.stderr, flush=True
#             )
#             return 1
#         os.makedirs(test_run_data_dir, exists_ok=True)

#         commands = test_commands.get(name)
#         if commands is None:
#             print("ERROR: No test named", name, file=sys.stderr, flush=True)
#             return 1
#         for command in commands:
#             try:
#                 subprocess.check_call(command, shell=True)
#             except subprocess.CalledProcessError:
#                 print(
#                     "ERROR command failed:",
#                     command,
#                     file=sys.stderr,
#                     flush=True,
#                 )
#                 return 1
