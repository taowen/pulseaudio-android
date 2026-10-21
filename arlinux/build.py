#!/usr/bin/env python3
"""Build the Android audio product with the host's NDK, CMake and Ninja."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(*command):
    subprocess.run([str(x) for x in command], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ndk', type=Path, required=True)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--cmake', required=True)
    parser.add_argument('--ninja', required=True)
    parser.add_argument('--api', type=int, default=28)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    host = 'windows-x86_64' if os.name == 'nt' else 'linux-x86_64'
    suffix = '.exe' if os.name == 'nt' else ''
    tools = args.ndk / 'toolchains/llvm/prebuilt' / host / 'bin'
    tracked = subprocess.check_output(['git', '-C', str(root), 'ls-files', '--recurse-submodules', '-z', '--',
                                      'arlinux/build.py', 'arlinux/native', 'pulseaudio',
                                      'libsndfile', 'libtool', 'pulseaudio-module']).decode().split('\0')
    inputs = {name: sha(root / name) for name in tracked if name and (root / name).is_file()}
    inputs.update(api=args.api, host=host, ndk=sha(args.ndk / 'source.properties'),
                  clang=sha(tools / ('clang' + suffix)), cmake=sha(args.cmake), ninja=sha(args.ninja))
    identity = hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest()
    args.output.mkdir(parents=True, exist_ok=True)
    # One owner per local product, including simultaneous Debug/Release requests.
    with (args.output / '.build.lock').open('a+b') as lock:
        if os.name == 'nt':
            import msvcrt
            if lock.tell() == 0:
                lock.write(b'\0'); lock.flush()
            lock.seek(0)
            deadline = time.monotonic() + 600
            while True:
                try:
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError('Audio product build lock timed out')
                    time.sleep(.25)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX)
        receipt = args.output / 'build-receipt.json'
        clean = False
        try:
            previous = json.loads(receipt.read_text())
            if not previous['files']:
                raise ValueError('Empty audio receipt')
            invalid = []
            for name, digest in previous['files'].items():
                product = args.output / name
                product.resolve().relative_to(args.output.resolve())
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('Invalid audio receipt path')
                if not product.is_file() or sha(product) != digest:
                    invalid.append(product)
            if previous['inputs'] == inputs and not invalid:
                print('OK Android audio inputs and output hashes unchanged; native cache reused', flush=True)
                return
            # A changed output must be relinked, even when its timestamp is newer
            # than every object. Never bless corrupted bytes with a new receipt.
            for product in invalid:
                product.unlink(missing_ok=True)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            clean = True
        # Keep compiler objects across source edits. The full input identity
        # validates the product; Ninja owns incremental source dependencies.
        toolchain = {k: inputs[k] for k in ('api', 'host', 'ndk', 'clang', 'cmake', 'ninja')}
        work = args.work / hashlib.sha256(json.dumps(toolchain, sort_keys=True).encode()).hexdigest()
        run(args.cmake, '-S', root / 'arlinux/native', '-B', work, '-G', 'Ninja',
            '-DCMAKE_MAKE_PROGRAM=' + str(Path(args.ninja).resolve()),
            '-DCMAKE_TOOLCHAIN_FILE=' + str(args.ndk / 'build/cmake/android.toolchain.cmake'),
            '-DANDROID_ABI=arm64-v8a', '-DANDROID_PLATFORM=android-' + str(args.api),
            '-DCMAKE_BUILD_TYPE=Release', '-DPython3_EXECUTABLE=' + sys.executable,
            '-DOUTPUT=' + str(args.output.resolve()))
        run(args.cmake, '--build', work, *(['--clean-first'] if clean else []),
            '--parallel', str(min(os.cpu_count() or 4, 16)))
        products = [Path(p) for p in (work / 'product-files.txt').read_text().splitlines()]
        for product in products:
            product.resolve().relative_to(args.output.resolve())
        for product in products:
            run(tools / ('llvm-strip' + suffix), '--strip-unneeded', product)
        files = {p.relative_to(args.output).as_posix(): sha(p) for p in products}
        temporary = receipt.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(format=1, inputs=inputs, identity=identity, files=files), indent=2) + '\n')
        temporary.replace(receipt)
        print('OK built Android audio with ' + host + ' NDK: ' + str(args.output), flush=True)


if __name__ == '__main__':
    main()
