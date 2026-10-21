# Android audio

The Android workstation entry is ARLinux's root `build.ps1`; its `audio` command
builds this component, and both Debug and Release invoke the same implementation.
The workstation uses native Windows Python, Android NDK, SDK CMake and SDK Ninja.
There is no Autotools, MSYS, WSL or GitHub release lookup in that path.

`arlinux/build.py` is the component worker invoked by the entry. Its required
arguments are `--ndk`, `--cmake`, `--ninja`, `--work` and `--output`; `--api`
defaults to 28. `arlinux/native/CMakeLists.txt` owns the complete target graph.
The same worker supports the Linux NDK for the independent Wine producer;
`arlinux/build.sh` only adapts that producer's existing invocation to this worker.

PulseAudio is a pinned nested submodule. libsndfile, libltdl and the AAudio sink
are repository sources. The native recipe reads upstream source declarations,
uses NDK compile/link probes for target capabilities, generates headers and
libltdl preload tables with Python, and compiles the existing native protocol,
server and AAudio modules. It does not restore configured Linux build trees.

The output retains `jni/arm64-v8a`, `assets/pulseaudio` and `build-receipt.json`.
CMake declares the produced files; the worker hashes sources, host tools, NDK
identity and output binaries. Only a matching input identity and complete output
hash verification skip the build. Ninja retains objects across source changes.
There are no mutable release manifests or remotely selected version combinations
in the workstation cache. The APK packaging check validates ELF64/16 KB alignment
and the producing receipt.

Acceptance requires the installed APK on a physical Android device, a fresh Linux
instance, application playback through the native protocol and AAudio, close,
restart and repeated playback. Build success and cached output hashes do not
establish audible playback. Keep device identifiers, build hashes, screenshots,
process/AAudio evidence and wearer/listener confirmation in private run evidence.
