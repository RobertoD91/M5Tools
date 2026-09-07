# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Arduino/PlatformIO firmware for M5Stack Core2, Tough, and ToughC5: a touch-driven diagnostic tool with eight
pages (WiFi scan, ESP-NOW touch sharing, I2C scan, GPIO DAC/PWM-to-ADC loopback, UART bridge, TF card listing,
RTC set/timer sleep, power/PMIC control). Built on M5Unified + M5GFX.

## Build

```
pio run -e m5tools_core2_tough        # default env; one binary serves both Core2 and Tough
pio run -e m5tools_tough_c5           # ESP32-C5 (pioarduino platform, custom no-OTA partition table)
pio run -e <env> -t upload
pio device monitor                    # 115200 baud
```

There is no test suite and no linter; a clean build of both environments is the check. The Arduino IDE
is also supported by opening `src/src.ino` (the sketch folder is `src/`, which is why the sketch is named
`src.ino` and the assets live under `src/src/`).

`platformio.ini` pins one pioarduino platform release for every env on purpose: mixing platforms makes the
envs fight over the framework directory, and newer arduino-core releases overflow IRAM on classic ESP32.
M5Unified is pinned to a specific develop commit. Do not bump either without a reason recorded in the ini
comments.

## Source layout and the single-translation-unit rule

`src/src.ino` includes `main.hpp` and every `Page*.hpp`. Those headers define real globals and non-inline
functions (`tp[]`, `loopCount`, `clickSound()`, `updateTouch()`, page instances, ring buffers, ...), so they
must be included exactly once, from `src.ino`. A new `.cpp` that includes `main.hpp` or a page header will
produce duplicate-symbol link errors. Separate `.cpp` files (`ft6336_fw_updater.cpp`, `tlsc6x_updater.cpp`,
`iram_tail_heap_workaround.c`) include only `M5Unified.h`/IDF headers and expose one entry point that
`src.ino` declares by prototype.

`src/src/img/*.c` are RGB565 `const unsigned char gImage_*[]` arrays, often sprite sheets indexed as
`base + i * w * h`; `src/src/wav/*.c` are 8-bit 16 kHz PCM. Each page declares the assets it uses with
`extern` and records the dimensions in a comment next to the declaration. Pin labels and board-specific
text are drawn in code rather than baked into background images.

## Runtime model

- **Pages.** `PageBase` has `setup()`, `loop()`, `end()`. `src.ino` holds a fixed array of eight page
  instances; the bottom tab bar (y > 200, 40 px per tab) selects the index. `PageDefault` is the idle page.
  The content area is 286x172 at (17,32) and is cleared to white before `setup()` of the new page.
- **Main loop.** `loop()` in `src.ino` calls `updateTouch()` once, handles tab switches and the top-right
  sleep-slider gesture (`x - y > 240`), then delegates to `selectedPage->loop()`.
- **Touch state is global.** `updateTouch()` refreshes `tp[]`, `touchPoints`, `prev_touchPoints`,
  `justTouch`, and `flickDiffX/Y`. Pages that block for a while (SD listing, RTC flick editing, retries)
  call `updateTouch()` themselves and treat a new touch as cancel. `contain(x,y,w,h)` hit-tests `tp[0]`.
- **`end()` must release everything the page claimed**: ESP-NOW/WiFi, SD card and TF power, LEDC PWM and
  continuous ADC, serial ports, canvases, PMIC pin functions. It runs on every tab switch and also right
  before deep sleep from the slider, so leaked hardware state survives into sleep/wake.
- **Board dispatch.** `M5TOOLS_TARGET_ESP32C5` (derived from `CONFIG_IDF_TARGET_ESP32C5` in `main.hpp`) is
  the compile-time switch for ToughC5 differences; `M5.getBoard()` distinguishes Core2 from Tough at
  runtime inside the shared binary. Prefer `M5.getPin(m5::pin_name_t::...)` over literal pin numbers.
- **Boot-time touch-panel firmware updaters.** `tlsc6x_tp_dect()` (Tough, Telink) and
  `ft6336_fw_updater()` (Core2, FocalTech) run from `setup()`. These and their firmware blobs
  (`tlsc6x_boot.h`, `ft6336_fw_v17_app.h`) are vendor-derived code; leave formatting and logic alone unless
  fixing a real bug.

## Hardware constraints to respect

- `M5.Lcd.startWrite()` is held for the whole runtime. Anything else on the shared SPI bus (the SD card)
  must `endWrite()` first and `startWrite()` afterward. Before redrawing into a canvas that was just pushed
  with `pushSprite`, call `M5.Lcd.waitDMA()`.
- The internal I2C bus (`M5.In_I2C`) is shared by touch, RTC, IO expander, and PMIC, is polled from the
  main loop every cycle, and has no mutex. Do not access it from another task. Probe addresses with a
  1-byte read, never an empty write, because that disturbs firmware-based slaves and the touch controller.
- Long synchronous work in `loop()` stalls touch and display. The established pattern is to do one unit per
  loop (I2C scans one address per pass) or go async and poll (WiFi scan).
- On ToughC5 the click/error sounds are PM1 PWM buzzer tones timed by `buzzerService()` from
  `updateTouch()`; call `buzzerFlush()` before starting a long draw so a short tone is not stretched.
  On ESP32-C5 there is no DAC and no classic Bluetooth; PortA is the internal I2C bus.
- `iram_tail_heap_workaround.c` reserves the unused IRAM tail on classic ESP32 to dodge a probabilistic
  heap-init abort that depends on link layout. Keep it in the build.

## Conventions

Explanatory comments are written in Japanese and record why a hardware workaround exists (measured
values, failure modes). Keep them, and add the same kind of rationale next to any new hardware quirk.
Commit messages are short imperative English, often prefixed with the page or file they touch.
