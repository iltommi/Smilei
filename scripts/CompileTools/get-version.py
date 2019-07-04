import os, sys, subprocess

proc1 = subprocess.Popen(["git describe --always"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
(out1, err1) = proc1.communicate()
proc2 = subprocess.Popen(["git rev-parse --abbrev-ref HEAD"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
(out2, err2) = proc2.communicate()
if err1 or err2:
	f_name = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ver")
	if os.path.isfile(f_name):
		sys.stderr.write("Version from .version file\n")
		print(open(f_name, 'r').read())
	else:
		sys.stderr.write("Unknown smilei version\n")
		print("??-??")
else:
	print(str(out1.strip())+"-"+str(out2.strip()))


