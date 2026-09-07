# PlatformIO post-build script, enabled with `extra_scripts = post:scripts/flash_images.py`.
#
# After firmware.bin is produced it gathers every image that `pio run -t upload`
# would write to the flash (bootloader, partition table, boot_app0, application):
#   * images that live outside the build directory (for example boot_app0.bin from
#     the framework package) are copied next to firmware.bin, so the build
#     directory holds everything needed to flash the device;
#   * flash_images.json records the chip, the flash parameters and the offset of
#     every image;
#   * firmware_merged.bin is the whole flash content from offset 0, made with
#     `esptool merge-bin`, for flashing with a single command.
# The CI workflow uploads these files and the web flasher manifest is generated
# from flash_images.json, so the browser flashes exactly what PlatformIO flashes.

import json
import os
import shutil
import subprocess

Import("env")  # noqa: F821 - provided by PlatformIO/SCons

MERGED_NAME = "firmware_merged.bin"
INFO_NAME = "flash_images.json"


def _unquote(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _esptool_command(env):
    # pioarduino points $UPLOADER at an esptool executable inside its Python
    # venv; the classic platform-espressif32 points it at esptool.py instead.
    uploader = _unquote(env.subst("$UPLOADER"))
    if uploader.lower().endswith(".py"):
        return [_unquote(env.subst("$PYTHONEXE")), uploader]
    return [uploader]


def _flash_param(env, expression, default="keep"):
    # These callables are what the platform itself passes to `write-flash`.
    try:
        value = env.subst(expression).strip()
    except Exception:  # pylint: disable=broad-except
        value = ""
    return value or default


def _flash_images(env):
    images = []
    for offset, path in env.get("FLASH_EXTRA_IMAGES", []):
        images.append((env.subst(str(offset)), env.subst(str(path))))
    images.append((env.subst("$ESP32_APP_OFFSET"), env.subst("$BUILD_DIR/${PROGNAME}.bin")))
    return sorted(images, key=lambda item: int(item[0], 0))


def _run_merge(cmd):
    try:
        subprocess.check_call(cmd)
    except subprocess.CalledProcessError:
        # esptool < 5 spells the command and its options with underscores.
        legacy = [arg.replace("merge-bin", "merge_bin").replace("--flash-", "--flash_") for arg in cmd]
        if legacy == cmd:
            raise
        subprocess.check_call(legacy)


def make_flash_images(source, target, env):
    build_dir = env.subst("$BUILD_DIR")
    board = env.BoardConfig()
    chip = board.get("build.mcu")

    entries = []
    for offset, path in _flash_images(env):
        name = os.path.basename(path)
        local = os.path.join(build_dir, name)
        if os.path.abspath(path) != os.path.abspath(local):
            shutil.copyfile(path, local)
        entries.append({
            "offset": "0x%x" % int(offset, 0),
            "file": name,
            "size": os.path.getsize(local),
        })

    flash_mode = _flash_param(env, "${__get_board_flash_mode(__env__)}")
    flash_freq = _flash_param(env, "${__get_board_f_image(__env__)}")
    flash_size = board.get("upload.flash_size", "keep")
    if flash_size == "detect":
        flash_size = "keep"

    merged_path = os.path.join(build_dir, MERGED_NAME)
    cmd = _esptool_command(env) + [
        "--chip", chip,
        "merge-bin", "-o", merged_path,
        "--flash-mode", flash_mode,
        "--flash-freq", flash_freq,
        "--flash-size", flash_size,
    ]
    for entry in entries:
        cmd += [entry["offset"], os.path.join(build_dir, entry["file"])]
    _run_merge(cmd)

    info = {
        "env": env["PIOENV"],
        "board": env.subst("$BOARD"),
        "chip": chip,
        "flash_mode": flash_mode,
        "flash_freq": flash_freq,
        "flash_size": flash_size,
        "images": entries,
        "merged": {"file": MERGED_NAME, "size": os.path.getsize(merged_path)},
    }
    with open(os.path.join(build_dir, INFO_NAME), "w") as fp:
        json.dump(info, fp, indent=2)
        fp.write("\n")

    print("Flash images for %s (%s):" % (info["env"], chip))
    for entry in entries:
        print("  %-8s %-18s %7d bytes" % (entry["offset"], entry["file"], entry["size"]))
    print("  merged   %-18s %7d bytes" % (MERGED_NAME, info["merged"]["size"]))


# Make sure the extra images (partition table in particular) exist before the
# post action runs, whatever order SCons picks for the targets.
env.Depends(
    "$BUILD_DIR/${PROGNAME}.bin",
    [env.subst(str(path)) for _, path in env.get("FLASH_EXTRA_IMAGES", [])],
)
env.AddPostAction("$BUILD_DIR/${PROGNAME}.bin", make_flash_images)
