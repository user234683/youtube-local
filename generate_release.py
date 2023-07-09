# Generate a windows release and a generated embedded distribution of python
# Latest python version is the argument of the script (or oldwin for
# vista, 7 and 32-bit versions)
# Requirements: 7z, git
# wine is required in order to build on Linux

import sys
import urllib
import urllib.request
import subprocess
import shutil
import os
import hashlib

latest_version = sys.argv[1]
if len(sys.argv) > 2:
    bitness = sys.argv[2]
else:
    bitness = '64'

if latest_version == 'oldwin':
    bitness = '32'
    latest_version = '3.7.9'
    suffix = 'windows-vista-7-only'
else:
    suffix = 'windows'

def check(code):
    if code != 0:
        raise Exception('Got nonzero exit code from command')
def check_subp(x):
    if x.returncode != 0:
        raise Exception('Got nonzero exit code from command')

def log(line):
    print('[generate_release.py] ' + line)

# https://stackoverflow.com/questions/7833715/python-deleting-certain-file-extensions
def remove_files_with_extensions(path, extensions):
    for root, dirs, files in os.walk(path):
        for file in files:
            if os.path.splitext(file)[1] in extensions:
                os.remove(os.path.join(root, file))

def download_if_not_exists(file_name, url, sha256=None):
    if not os.path.exists('./' + file_name):
        log('Downloading ' + file_name + '..')
        data = urllib.request.urlopen(url).read()
        log('Finished downloading ' + file_name)
        with open('./' + file_name, 'wb') as f:
            f.write(data)
        if sha256:
            digest = hashlib.sha256(data).hexdigest()
            if digest != sha256:
                log('Error: ' + file_name + ' has wrong hash: ' + digest)
                sys.exit(1)
    else:
        log('Using existing ' + file_name)

def wine_run_shell(command):
    if os.name == 'posix':
        check(os.system('wine ' + command.replace('\\', '/')))
    elif os.name == 'nt':
        check(os.system(command))
    else:
        raise Exception('Unsupported OS')

def wine_run(command_parts):
    if os.name == 'posix':
        command_parts = ['wine',] + command_parts
    if subprocess.run(command_parts).returncode != 0:
        raise Exception('Got nonzero exit code from command')

# ---------- Get current release version, for later ----------
log('Getting current release version')
describe_result = subprocess.run(['git', 'describe', '--tags'], stdout=subprocess.PIPE)
if describe_result.returncode != 0:
    raise Exception('Git describe failed')

release_tag = describe_result.stdout.strip().decode('ascii')


# ----------- Make copy of youtube-local files using git -----------

if os.path.exists('./youtube-local'):
    log('Removing old release')
    shutil.rmtree('./youtube-local')

# Export git repository - this will ensure .git and things in gitignore won't
# be included. Git only supports exporting archive formats, not into
# directories, so pipe into 7z to put it into .\youtube-local (not to be
# confused with working directory. I'm calling it the same thing so it will
# have that name when extracted from the final release zip archive)
log('Making copy of youtube-local files')
check(os.system('git archive --format tar master | 7z x -si -ttar -oyoutube-local'))

if len(os.listdir('./youtube-local')) == 0:
    raise Exception('Failed to copy youtube-local files')


# ----------- Generate embedded python distribution -----------
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'     # *.pyc files double the size of the distribution
get_pip_url = 'https://bootstrap.pypa.io/get-pip.py'
latest_dist_url = 'https://www.python.org/ftp/python/' + latest_version + '/python-' + latest_version
if bitness == '32':
    latest_dist_url += '-embed-win32.zip'
else:
    latest_dist_url += '-embed-amd64.zip'

# I've verified that all the dlls in the following are signed by Microsoft.
# Using this because Microsoft only provides installers whose files can't be
# extracted without a special tool.
if bitness == '32':
    visual_c_runtime_url = 'https://github.com/yuempek/vc-archive/raw/master/archives/vc15_(14.10.25017.0)_2017_x86.7z'
    visual_c_runtime_sha256 = '2549eb4d2ce4cf3a87425ea01940f74368bf1cda378ef8a8a1f1a12ed59f1547'
    visual_c_name = 'vc15_(14.10.25017.0)_2017_x86.7z'
else:
    visual_c_runtime_url = 'https://github.com/yuempek/vc-archive/raw/master/archives/vc15_(14.10.25017.0)_2017_x64.7z'
    visual_c_runtime_sha256 = '4f00b824c37e1017a93fccbd5775e6ee54f824b6786f5730d257a87a3d9ce921'
    visual_c_name = 'vc15_(14.10.25017.0)_2017_x64.7z'

download_if_not_exists('get-pip.py', get_pip_url)

python_dist_name = 'python-dist-' + latest_version + '-' + bitness + '.zip'

download_if_not_exists(python_dist_name, latest_dist_url)
download_if_not_exists(visual_c_name,
    visual_c_runtime_url, sha256=visual_c_runtime_sha256)

if os.path.exists('./python'):
    log('Removing old python distribution')
    shutil.rmtree('./python')


log('Extracting python distribution')

check(os.system(r'7z -y x -opython ' + python_dist_name))

log('Executing get-pip.py')
wine_run(['./python/python.exe', '-I', 'get-pip.py'])

'''
# Explanation of .pth, ._pth, and isolated mode

## Isolated mode
    We want to run in what is called isolated mode, given by the switch -I.
This mode prevents the embedded python distribution from searching in
global directories for imports

    For example, if a user has `C:\Python37` and the embedded distribution is
the same version, importing something using the embedded distribution will
search `C:\Python37\Libs\site-packages`. This is not desirable because it
means I might forget to distribute a dependency if I have it installed
globally and I don't see any import errors. It also means that an outdated
package might override the one being distributed and cause other problems.

    Isolated mode also means global environment variables and registry
entries will be ignored

## The trouble with isolated mode
    Isolated mode also prevents the current working directory (cwd) from
being added to `sys.path`. `sys.path` is the list of directories python will
search in for imports. In non-isolated mode this is automatically populated
with the cwd, `site-packages`, the directory of the python executable, etc.

# How to get the cwd into sys.path in isolated mode
    The hack to get this to work is to use a .pth file. Normally, these files
are just an additional list of directories to be added to `sys.path`.
However, they also allow arbitrary code execution on lines beginning with
`import ` (see https://docs.python.org/3/library/site.html). So, we simply
add `import sys; sys.path.insert(0, '')` to add the cwd to path. `''` is
shorthand for the cwd. See https://bugs.python.org/issue33698#msg318272

# ._pth files in the embedded distribution
A python37._pth file is included in the embedded distribution. The presence
of tis file causes the embedded distribution to always use isolated mode
(which we want). They are like .pth files, except they do not allow the
arbitrary code execution trick. In my experimentation, I found that they
prevent .pth files from loading. So the ._pth file will have to be removed
and replaced with a .pth. Isolated mode will have to be specified manually.
'''

log('Removing ._pth')
major_release = latest_version.split('.')[1]
os.remove(r'./python/python3' + major_release + '._pth')

log('Adding path_fixes.pth')
with open(r'./python/path_fixes.pth', 'w', encoding='utf-8') as f:
    f.write("import sys; sys.path.insert(0, '')\n")


'''# python3x._pth file tells the python executable where to look for files
#  Need to add the directory where packages are installed,
# and the parent directory (which is where the youtube-local files are)
major_release = latest_version.split('.')[1]
with open('./python/python3' + major_release + '._pth', 'a', encoding='utf-8') as f:
    f.write('.\\Lib\\site-packages\n')
    f.write('..\n')'''

log('Inserting Microsoft C Runtime')
check_subp(subprocess.run([r'7z', '-y', 'e', '-opython', 'vc15_(14.10.25017.0)_2017_x86.7z', 'runtime_minimum/System']))

log('Installing dependencies')
wine_run(['./python/python.exe', '-I', '-m', 'pip', 'install', '--no-compile', '-r', './requirements.txt'])

log('Uninstalling unnecessary gevent stuff')
wine_run(['./python/python.exe', '-I', '-m', 'pip', 'uninstall', '--yes', 'cffi', 'pycparser'])
shutil.rmtree(r'./python/Lib/site-packages/gevent/tests')
shutil.rmtree(r'./python/Lib/site-packages/gevent/testing')
remove_files_with_extensions(r'./python/Lib/site-packages/gevent', ['.html']) # bloated html documentation

log('Uninstalling pip and others')
wine_run(['./python/python.exe', '-I', '-m', 'pip', 'uninstall', '--yes', 'pip', 'wheel'])

log('Removing pyc files')   # Have to do this because get-pip and some packages don't respect --no-compile
remove_files_with_extensions(r'./python', ['.pyc'])

log('Removing dist-info and __pycache__')
for root, dirs, files in os.walk(r'./python'):
    for dir in dirs:
        if dir == '__pycache__' or dir.endswith('.dist-info'):
            shutil.rmtree(os.path.join(root, dir))


'''log('Removing get-pip.py and zipped distribution')
os.remove(r'.\get-pip.py')
os.remove(r'.\latest-dist.zip')'''

print()
log('Finished generating python distribution')

# ----------- Copy generated distribution into release folder -----------
log('Copying python distribution into release folder')
shutil.copytree(r'./python', r'./youtube-local/python')

# ----------- Create release zip -----------
output_filename = 'youtube-local-' + release_tag + '-' + suffix + '.zip'
if os.path.exists('./' + output_filename):
    log('Removing previous zipped release')
    os.remove('./' + output_filename)
log('Zipping release')
check(os.system(r'7z -mx=9 a ' + output_filename + ' ./youtube-local'))

print('\n')
log('Finished')
