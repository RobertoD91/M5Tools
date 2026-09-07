#!/usr/bin/env python3
"""Assemble the GitHub Pages site of the web flasher.

Expects one directory per PlatformIO environment under --firmware-dir, each
holding the files written by scripts/flash_images.py (flash_images.json plus
the images it lists).  Produces:

  <out>/manifest.json   the ESP Web Tools manifest, one build per chip family
  <out>/index.html      web/index.html with the build information filled in

Build metadata is taken from the environment (set by the workflow) and, when
missing, from git.  Run it from the repository root:

  python3 scripts/make_site.py --firmware-dir site/firmware --out site
"""

import argparse
import datetime
import html
import json
import os
import subprocess
import sys

CHIP_FAMILY = {
    "esp32": "ESP32",
    "esp32s2": "ESP32-S2",
    "esp32s3": "ESP32-S3",
    "esp32c2": "ESP32-C2",
    "esp32c3": "ESP32-C3",
    "esp32c5": "ESP32-C5",
    "esp32c6": "ESP32-C6",
    "esp32c61": "ESP32-C61",
    "esp32h2": "ESP32-H2",
    "esp32p4": "ESP32-P4",
}

# Friendly names for the environments of platformio.ini.
ENV_TITLE = {
    "m5tools_core2_tough": "M5Stack Core2 / Tough",
    "m5tools_tough_c5": "M5Stack ToughC5",
}


def git(*args):
    try:
        return subprocess.check_output(["git"] + list(args), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def load_builds(firmware_dir):
    builds = []
    for name in sorted(os.listdir(firmware_dir)):
        info_path = os.path.join(firmware_dir, name, "flash_images.json")
        if not os.path.isfile(info_path):
            continue
        with open(info_path) as fp:
            info = json.load(fp)
        info["dir"] = name
        builds.append(info)
    if not builds:
        sys.exit("no flash_images.json found under %s" % firmware_dir)
    return builds


def manifest(builds, version):
    entries = []
    for info in builds:
        chip = info["chip"]
        family = CHIP_FAMILY.get(chip)
        if family is None:
            sys.exit("unknown chip %r in %s" % (chip, info["dir"]))
        entries.append({
            "chipFamily": family,
            "parts": [
                {"path": "firmware/%s/%s" % (info["dir"], image["file"]), "offset": int(image["offset"], 0)}
                for image in info["images"]
            ],
        })
    return {
        "name": "M5Tools",
        "version": version,
        "new_install_prompt_erase": True,
        "builds": entries,
    }


def human_size(size):
    return "%.0f KB" % (size / 1024.0) if size >= 1024 else "%d B" % size


def build_section(info):
    base = "firmware/%s/" % info["dir"]
    rows = []
    for image in info["images"]:
        rows.append(
            '        <tr><td class="num"><code>%s</code></td>'
            '<td><a href="%s%s">%s</a></td><td class="num">%s</td></tr>'
            % (image["offset"], base, image["file"], image["file"], human_size(image["size"]))
        )
    merged = info["merged"]
    title = ENV_TITLE.get(info["env"], info["env"])
    esptool = "esptool --chip %s --port PORT write-flash 0x0 %s" % (info["chip"], merged["file"])
    return "\n".join([
        '  <div class="card">',
        "    <h3>%s <span class=\"sub\">(%s, %s, flash %s %s @ %s)</span></h3>" % (
            html.escape(title), html.escape(info["env"]), html.escape(CHIP_FAMILY.get(info["chip"], info["chip"])),
            html.escape(info["flash_size"]), html.escape(info["flash_mode"]), html.escape(info["flash_freq"])),
        "    <table>",
        "      <thead><tr><th>Offset</th><th>File</th><th>Size</th></tr></thead>",
        "      <tbody>",
        "\n".join(rows),
        '        <tr><td class="num"><code>0x0</code></td>'
        '<td><a href="%s%s">%s</a> <span class="sub">(all of the above in one image)</span></td>'
        '<td class="num">%s</td></tr>' % (base, merged["file"], merged["file"], human_size(merged["size"])),
        "      </tbody>",
        "    </table>",
        "    <pre>%s</pre>" % html.escape(esptool),
        '    <p class="sub">esptool 5 syntax; older releases spell it <code>write_flash</code>.</p>',
        "  </div>",
    ])


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--firmware-dir", required=True, help="directory with one sub-directory per environment")
    parser.add_argument("--template", default="web/index.html")
    parser.add_argument("--out", required=True, help="site output directory (must contain --firmware-dir)")
    args = parser.parse_args()

    env = os.environ
    repo_url = env.get("REPO_URL") or "https://github.com/RobertoD91/M5Tools"
    commit = env.get("COMMIT_SHA") or git("rev-parse", "HEAD") or "unknown"
    ref = env.get("REF_NAME") or git("rev-parse", "--abbrev-ref", "HEAD") or "unknown"
    commit_title = env.get("COMMIT_TITLE") or git("log", "-1", "--format=%s")
    run_url = env.get("RUN_URL") or repo_url + "/actions"
    run_number = env.get("RUN_NUMBER") or "-"
    build_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    version = "%s@%s" % (ref, commit[:7])

    builds = load_builds(args.firmware_dir)

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "manifest.json"), "w") as fp:
        json.dump(manifest(builds, version), fp, indent=2)
        fp.write("\n")

    with open(args.template) as fp:
        page = fp.read()
    values = {
        "REPO_URL": html.escape(repo_url),
        "REF": html.escape(ref),
        "COMMIT_SHORT": html.escape(commit[:7]),
        "COMMIT_URL": html.escape("%s/commit/%s" % (repo_url, commit)),
        "COMMIT_TITLE": html.escape(commit_title),
        "BUILD_DATE": html.escape(build_date),
        "RUN_URL": html.escape(run_url),
        "RUN_NUMBER": html.escape(str(run_number)),
        "BUILD_SECTIONS": "\n".join(build_section(info) for info in builds),
    }
    for key, value in values.items():
        page = page.replace("{{%s}}" % key, value)
    leftover = [key for key in values if "{{%s}}" % key in page]
    if "{{" in page:
        sys.exit("unfilled placeholder left in template: %s" % page[page.index("{{"):page.index("{{") + 40])
    assert not leftover
    with open(os.path.join(args.out, "index.html"), "w") as fp:
        fp.write(page)

    # Pages should never try to build the site with Jekyll.
    open(os.path.join(args.out, ".nojekyll"), "w").close()

    print("site written to %s: %d build(s), version %s" % (args.out, len(builds), version))
    for info in builds:
        print("  %-22s %-9s %s" % (info["env"], info["chip"], ", ".join(i["file"] for i in info["images"])))


if __name__ == "__main__":
    main()
