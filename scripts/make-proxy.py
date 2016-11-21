import os, sys, re, subprocess
from distutils.spawn import find_executable
from string import Template


def cls():
    # os specific "clear"
    method = 'cls' if os.name == 'nt' else 'clear'
    os.system(method)

def move():
    method = 'MOVE -Y' if os.name == 'nt' else 'mv'
    return method

def delete():
    method = 'DEL' if os.name == 'nt' else 'rm'
    return method

def tsv(type='NONE', desc="No description", value='', extra=''):
    return "%s\t%s\t%s\t%s" % (type.ljust(8), desc, value, extra)

def sizeof_fmt(num, suffix='B'):
    for unit in ['','K','M','G','T','P','E','Z']:
        if abs(num) < 1024.0:
            return "%3.2f %s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

# the FFMPEG parameters
def get_ffmpeg_array(i='$INPUT', o='$OUTPUT'):
    command = ["\"%s\"" % (which_ffmpeg)]
    command += ['-i', ('"%s"' % i)]
    command += ['-strict', '-2']
    command += ['-c:a', 'copy']
    command += ['-c:v', which_prores]
    command += ['-profile:v', which_profile]
    command += ['-qscale:v', which_quality]
    command += ['-s', which_size]
    command += ['-threads', '0', '-hide_banner', '-y']

    command += ['-metadata comment="ORIGINAL: %s"' % (i)]
    command += ['-metadata composer="FFMPEG: encoder=%s quality=%s"' % (which_prores, which_quality)]
    command += ['-metadata description="Made with make-proxy.py (http://github.com/fliptopbox/)"']
    command += [('"%s.part.mov"' % (o))]
    return command;

def get_bash_script(i, o):
    ffmpeg_command = get_ffmpeg_array()
    bash_string = []
    bash_string += [Template(' '.join(ffmpeg_command)).substitute(INPUT=i, OUTPUT=o)]
    bash_string += ['%s "%s.part.mov" "%s"' % (move(), o, o)]
    bash_string += ['%s -f "%s.ffmpeg"' % (delete(), o)]
    return ' && '.join(bash_string);

def create_output_assets():

    global file_count
    global total_bytes

    for root, subdirs, files in os.walk(footage):
        for file in files:

            # skip dot files (eg ._myVideoFile.MOV)
            if re.compile("^\.").match(file):
                continue

            # process video media
            if is_video.match(file):

                input_filename = "%s/%s" % (root, file)
                input_extension = re.search('([a-z0-9]+)$', input_filename, re.IGNORECASE).group(0)

                input_file_size = os.path.getsize(input_filename)

                base =  input_filename.replace(footage, "")

                output_folder = ("%s%s" % (proxy, base)).replace(file, '')
                output_extension = re.compile('mov', re.IGNORECASE).match(input_extension) and input_extension or 'mov'
                output_filename = output_folder + re.sub('([^\.]{2,})$', output_extension, file)

                # skip large files
                if (byte_limit > 0) and (input_file_size > byte_limit):
                    errors.append(tsv("WARN", "Size limit exceeded", base, sizeof_fmt(input_file_size)))
                    continue

                # skip existing transcoded files
                if skip_existing_files and os.path.isfile(output_filename):
                    errors.append(tsv("SKIP", "Output media exists", output_filename))
                    continue

                # is this a transcode (ie input does not match output)
                if input_extension.lower() != output_extension.lower():
                    errors.append(tsv("TRANS", "Transcode media", input_filename , "%s to %s" % (input_extension,output_extension)))

                # create proxy output folder(s)
                if not os.path.isdir(output_folder):
                    # print "Create folder:", output_folder
                    try:
                        os.makedirs(output_folder)
                    except:
                        msg = tsv("ERROR", "Can't create folder", output_folder)
                        if not errors.count(msg):
                            errors.append(msg)
                        continue

                # create the ffmpeg command file, if the output media does not exist
                if os.path.isdir(output_folder) and not os.path.isfile(output_filename):
                    # print "Create bash file: %s.ffmpeg" % (output_filename)
                    try:
                        bash_file = open("%s.ffmpeg" % (output_filename), 'w')
                        bash_string = get_bash_script(input_filename, output_filename)
                        bash_file.write(bash_string)
                        bash_file.close()
                        stack.append(bash_string)
                        file_count += 1
                        total_bytes += input_file_size
                    except:
                        # errors.append("Can't create file (%s.ffmpeg)" % (output_filename))
                        errors.append(tsv("ERROR", "Can't create file", "%s.ffmpeg" % (output_filename)))

    info.append(tsv("INFO", "File count", file_count))
    info.append(tsv("INFO", "Total bytes", sizeof_fmt(total_bytes)))

    return;

def present_warnings():
    if len(errors):
        print "-------------------------------------------"
        print " WARNINGS that occured while preparing"
        print "-------------------------------------------"
        print "\n - " + ('\n - '.join(errors))

        log_file = open("%s/warning.log" % (proxy), 'w')
        log_file.write('\n'.join(info) + '\n' + '\n'.join(errors))
        log_file.close()

    return;

def create_proxy_footage():
    if len(stack):
        print "\n\n\nThere are %d items ready to transcode." % (len(stack))

        if raw_input("Do you want to continue: (y/N) ") == 'y':
            i = 0
            n = len(stack)
            for cmd in stack:
                i += 1
                cls()
                print "Executing %d of %d (%d)\n\n" % (i, n, int((float(i-1)/float(n)) * 100))
                subprocess.call(cmd, shell=True)


# derive the in/out folders from the sys arguments
# 1 = input (footage) root folder, 2=output (proxy) root folder
try:
    footage = sys.argv[1]
except:
    footage = ''

try:
    proxy = sys.argv[2]
except:
    proxy = ''

footage = footage or "/media/bruce/mega/solo-on-moto/media/footage"
proxy = proxy or "/media/bruce/data/soloonmoto/proxy"


# the most common video extensions to match and convert
is_video = re.compile('.*(mp4|mov|qt|avi|wmv|m4v|mpeg|3gp|mxf|mkv)$', re.IGNORECASE)

byte_limit = 20 # basically 20 Gigs
gigabyte = 1024**3

stack = [] # the FFMPEG execution stack
errors = [] # the collated runtime errors
file_count = 0
total_bytes = 0
skip_existing_files = True


# the FFMPEG options
which_ffmpeg = find_executable("ffmpeg")
which_prores = 'prores_ks' # 'prores' 'prores_ks' (supports 4444) 'prores_aw'
which_size = '1920x1080'
which_profile = '0' # 0:Proxy, 1:LT, 2:SQ and 3:HQ
which_quality = '9' # huge file: [0 |||||| 9-13 |||||||| 32] terrible quality

# get the user input

cls()
footage = raw_input("Original folder(%s): " % (footage)) or footage
proxy = raw_input("Desitination folder (%s)" % (proxy)) or proxy

which_prores = raw_input("Which prores encoder (%s) 'prores', 'prores_ks', 'prores_aw': " % (which_prores) ) or which_prores
which_profile = raw_input("Which prores profile (%s) 0:Proxy, 1:LT, 2:SQ and 3:HQ: " % (which_profile) ) or which_profile
which_quality = raw_input("Quality (%s) 0:high to 32:low: " % (which_quality) ) or which_quality
which_size = raw_input("Output dimenstions (%s): " % (which_size) ) or which_size
new_byte_limit = raw_input("Skip large files (%s GB): " % (byte_limit) )
byte_limit = float(new_byte_limit or byte_limit) * gigabyte

info = [
    tsv("TYPE", "DESCRIPTION", "VALUE", "COMMENT"),
    tsv("INFO", "input", footage),
    tsv("INFO", "output", proxy),
    tsv("INFO", "prores", which_prores),
    tsv("INFO", "profile", which_profile),
    tsv("INFO", "quality", which_quality),
    tsv("INFO", "dimensions", which_size),
    tsv("INFO", "size limit", byte_limit, sizeof_fmt(byte_limit))
]


create_output_assets()
present_warnings()
create_proxy_footage()