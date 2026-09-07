# M5Tools
### M5Stack Tough and Core2 tools .

# Support framework
 - Arduino for ESP32 1.0.6
 - PlatformIO espressif32 4.4.0 / Arduino for ESP32 2.0.3
 - PlatformIO pioarduino espressif32 / Arduino for ESP32 3.x for ESP32-C5

# Web flasher

[![Build](https://github.com/RobertoD91/M5Tools/actions/workflows/build.yml/badge.svg)](https://github.com/RobertoD91/M5Tools/actions/workflows/build.yml)

The firmware can be flashed from a browser, without installing anything, at
https://robertod91.github.io/M5Tools/ (Chrome, Edge or Opera on a desktop OS,
which provide Web Serial). The page detects the chip and picks the Core2 /
Tough or the ToughC5 build. It also offers the raw images and a merged image
for `esptool`.

The page is rebuilt by the Build workflow on every push to the default branch
(or manually from the Actions tab). The same workflow builds both environments
on every push and stores the images as artifacts of the run.

One-time setup for a fork: in the repository settings open *Pages* and set
*Build and deployment → Source* to *GitHub Actions*, otherwise the deploy job
fails with "Get Pages site failed".

# PlatformIO build

```
pio run -e m5tools_core2_tough
pio run -e m5tools_tough_c5
```

Besides `firmware.bin`, each build leaves in `.pio/build/<env>/` every image
that `pio run -t upload` would flash (bootloader, partition table, boot_app0),
`firmware_merged.bin` with all of them merged from offset 0, and
`flash_images.json` describing the layout.

The `m5tools_core2_tough` environment uses the `m5stack-core2` board definition
and builds the same firmware for M5Stack Core2 and M5Stack Tough.

The `m5tools_tough_c5` environment uses the pioarduino ESP32-C5 platform and
the `develop` branches of M5Unified and M5GFX. It uses a no-OTA 3MB application
partition because the firmware does not fit in the default 4MB board app slot.

On ESP32-C5, classic Bluetooth and DAC GPIO output are not available and are
disabled. The board has no I2S speaker either, so the click and error sounds
are single tones from the PM1 PWM buzzer instead of the WAV assets that the
other boards play through `M5.Speaker`.

# Support device
 - M5Stack Core2 / Tough
 - M5Stack ToughC5

# License
 - [MIT](LICENSE)
