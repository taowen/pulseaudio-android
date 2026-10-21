"""Translate upstream source declarations and generated headers for the NDK build."""
import ast
from pathlib import Path
import re
import sys

root, out = map(Path, sys.argv[1:])
out.mkdir(parents=True, exist_ok=True)
pulse = root / 'pulseaudio'


def write(path, content):
    if not path.is_file() or path.read_text() != content:
        path.write_text(content)


def sources(path, variable):
    text = path.read_text(encoding='utf-8')
    value = re.search(r'^' + re.escape(variable) + r'\s*=\s*(\[.*?^\])', text, re.M | re.S)
    return [path.parent / p for p in ast.literal_eval(value[1]) if p.endswith('.c')]


groups = {
    'pulsecommon': sources(pulse / 'src/meson.build', 'libpulsecommon_sources'),
    'pulse': sources(pulse / 'src/pulse/meson.build', 'libpulse_sources'),
    'pulsecore': sources(pulse / 'src/pulsecore/meson.build', 'libpulsecore_sources')
                 + [pulse / 'src/pulsecore/database-simple.c'],
    'daemon': sources(pulse / 'src/daemon/meson.build', 'pulseaudio_sources'),
}
# The common library owns these fallback implementations when the target's
# libc does not provide them. CMake selects them after its NDK feature probes.
cmake = []
for name, paths in groups.items():
    cmake.append('set(' + name + '_sources\n' + '\n'.join('  "' + p.as_posix() + '"' for p in paths) + '\n)')

text = (root / 'libsndfile/src/Makefile.am').read_text().replace('\\\n', ' ')
snd_sources = []
for variable in ['FILESPECIFIC', 'libcommon_la_SOURCES', 'GSM610_libgsm_la_SOURCES',
                 'G72x_libg72x_la_SOURCES', 'ALAC_libalac_la_SOURCES']:
    value = re.search(r'^' + variable + r'\s*=\s*(.*)', text, re.M)[1]
    snd_sources.extend(root / 'libsndfile/src' / p for p in value.split() if p.endswith('.c'))
cmake.append('set(sndfile_sources\n' + '\n'.join('  "' + p.as_posix() + '"' for p in snd_sources) + '\n)')
write(out / 'sources.cmake', '\n'.join(cmake) + '\n')

headers = {
    out / 'pulse/version.h': (pulse / 'src/pulse/version.h.in', {
        'PA_MAJOR': '13', 'PA_MINOR': '0', 'PA_API_VERSION': '12', 'PA_PROTOCOL_VERSION': '33'}),
    out / 'sndfile/sndfile.h': (root / 'libsndfile/src/sndfile.h.in', {
        'TYPEOF_SF_COUNT_T': 'int64_t', 'SF_COUNT_MAX': 'INT64_MAX'}),
}
for destination, (source, values) in headers.items():
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = source.read_text()
    for name, value in values.items():
        data = data.replace('@' + name + '@', value)
    if re.search(r'@[A-Za-z_]+@', data):
        raise ValueError('Unresolved generated-header parameter: ' + str(source))
    write(destination, data)

# Libtool normally generates this preload table with its host shell tools.
# Register the real upstream dlopen loader, not an alternate loader shim.
write(out / 'ltdl-preload.c', '''#include <ltdl.h>
#include <libltdl/lt_dlloader.h>
extern lt_dlvtable *dlopen_LTX_get_vtable(lt_user_data);
const lt_dlsymlist lt_libltdl_LTX_preloaded_symbols[] = {
  {"libltdl", 0}, {"dlopen.a", 0},
  {"get_vtable", (void *)dlopen_LTX_get_vtable}, {0, 0}
};
''')
write(out / 'program-preload.c', '''#include <ltdl.h>
const lt_dlsymlist lt__PROGRAM__LTX_preloaded_symbols[] = {
  {"@PROGRAM@", 0}, {0, 0}
};
''')
