# UNO Q USB webcam gesture recognition

Run hand gesture recognition on the **Arduino UNO Q's Linux processor**, selecting Arduino's integrated model or MediaPipe through `python/config.json`. A stable **raised open palm turns all eight Modulino Pixels and all four onboard RGB indicators red and plays two short beeps**. A stable **thumbs-up turns them green and plays one short beep**. Other gestures or no hand turn the lights off and silence the buzzer. Beeps play once when a gesture becomes stable, not on every frame; losing and showing the gesture again plays them again.

The camera connects directly to the UNO Q. No Windows host camera server is used. Timestamped terminal logs show gestures, confidence, LED colors, module detection, and errors; JSON events remain available on stdout.

This project targets **UNO Q**, not the classic ATmega328P UNO or an Arduino Nano. No separate computer is needed for inference after deployment.

**Using Arduino IDE instead of App Lab:** open the [Arduino IDE version](arduino-ide/README.md). It includes an IDE sketch plus a standalone Linux app with both backends selected through `arduino-ide/config.json`. Build its complete ZIP with `python scripts/prepare_ide.py` after fetching both models with `python scripts/download_ide_models.py`.

## Hardware setup

1. Set up and update the UNO Q with Arduino App Lab, including its board software and Bricks.
2. Connect a USB webcam through a **USB-C hub with power delivery**. Supply the hub with suitable 5 V / 3 A power. The camera plugs into the hub; the hub plugs into the UNO Q.
3. Connect App Lab to the board in **Network mode** over your LAN, or work directly on the board in SBC mode.
   Connect **UNO Q Qwiic → Modulino Pixels → Modulino Buzzer** with Qwiic cables (either module order works). The MCU sketch uses `Wire1` and the **Arduino_Modulino 0.9.1** library, declared in `sketch/sketch.yaml`. All pixels use 25% brightness; change `PIXEL_BRIGHTNESS` in the sketch to adjust it. The built-in blue matrix is not used.
4. In the board's terminal, identify the webcam capture node:

   ```sh
   ls -l /dev/v4l/by-id/
   v4l2-ctl --list-devices
   ```

   If `v4l2-ctl` is unavailable, install Debian's `v4l-utils` package. A camera may expose several `/dev/video*` nodes; select its video capture node, not its metadata node. A `/dev/v4l/by-id/...-video-index0` path is usually more stable than a number across reboots. Set `camera.device` in the config to that path.

## Choose a backend

Edit this field in **`python/config.json`**:

```json
"backend": "integrated"
```

or:

```json
"backend": "mediapipe"
```

| Output gesture | Arduino integrated model | MediaPipe model |
| --- | --- | --- |
| `Open_Palm` | `five` | Supported |
| `Thumb_Up` | `good` | Supported |
| `Closed_Fist` | `neut` | Supported |
| `Victory` | `peace` | Supported |
| `Thumb_Down` | Not available | Supported |
| `Pointing_Up` | Not available | Supported |
| `ILoveYou` | Not available | Supported |

`integrated` uses the **Object Detection brick with Arduino's bundled `hand-gestures` Edge Impulse model**. Its four raw labels are mapped to shared names. It does not report left/right handedness. MediaPipe runs the official **Gesture Recognizer Tasks API**, reports handedness, and uses its `.task` model locally.

Arduino's separate `arduino:gesture_recognition` brick currently declares **Ventuno Q** support, so this UNO Q implementation uses the supported `hand-gestures` model instead. See the [Arduino model catalog](https://github.com/arduino/app-bricks-py/blob/main/models/models-list.yaml) and [gesture brick definition](https://github.com/arduino/app-bricks-py/blob/main/src/arduino/app_bricks/gesture_recognition/brick_config.yaml).

## Build and run in App Lab

Run these commands from this source project's folder. They need only Python 3.10+ on the development computer; **on Windows use `py -3.11` in place of `python3`**.

```sh
python3 python/main.py --check-config
```

For MediaPipe, fetch the official model once before packaging:

```sh
python3 scripts/download_model.py
```

Then build the app selected by your configuration:

```sh
python3 scripts/prepare.py
```

Import the resulting **`dist/uno-q-gesture-integrated.zip`** or **`dist/uno-q-gesture-mediapipe.zip`** into Arduino App Lab, connect to your UNO Q, and press **Run**. App Lab installs dependencies, starts the necessary service, and flashes the included sketch. Hold a raised palm or thumbs-up steadily for three processed frames for the corresponding color and beeps. Lower your hand or make another gesture to clear the output. Re-upload/re-import the updated sketch together with Python: the feedback RPC has changed.

**After changing backends, rebuild and import the ZIP again.** App Lab decides service and dependency installation from `app.yaml` before Python starts; `prepare.py` generates those files from the same configuration. Only the selected inference backend is instantiated, and the MediaPipe package starts no Edge Impulse service. Camera and threshold edits can also be made in the imported app's `python/config.json`; stop and restart after editing. Changes are read at startup, not live.

The checked-in root `app.yaml` is ready for integrated mode if you work directly from the source folder on the board. For a MediaPipe deployment, use the generated package, which includes its model and requirements. Keep the source project for rebuilding; generated ZIPs contain only the runtime app.

## Configuration and behavior

- `camera.device`: Linux device path, or an integer webcam index for a desktop test. Default `/dev/video0` is a starting point; verify it on your board.
- `camera.width`, `height`, `fps`: start with 640 × 480 at 15 FPS. FPS limits processing, and camera modes are requested rather than guaranteed. Actual recognition speed depends on hardware, camera, and backend.
- `camera.mirror`: flips frames before recognition. Keep `false` initially; flipping can change MediaPipe handedness labels.
- `recognition.min_confidence`: probability in `[0,1]`, applied consistently across both backends. Arduino's percentage output is converted to this scale.
- `recognition.stable_frames`: number of consecutive processed frames with the same strongest gesture/hand. Empty, unknown, low-confidence, or changing results reset stability. If multiple hands are visible, the **highest-confidence gesture** controls this demo.
- `recognition.repeat_seconds`: limits repeated console messages for a held gesture. A change is reported immediately after stabilization; losing the gesture emits `None` once.
- `mediapipe.model_path`: resolved relative to the configuration file, independent of the working directory. Packaging embeds the selected file under `python/models/`.
- `led.enabled`: enable all four onboard RGB indicators and the eight Modulino Pixels. `led.gesture_colors` maps `Open_Palm` to `red` and `Thumb_Up` to `green`. Unmapped gestures turn the LEDs off. This replaces the old `led.on_gestures` list.
- `buzzer.enabled`: enable the Modulino Buzzer. Red feedback plays two 100 ms beeps at 1 kHz; green plays one 100 ms beep at 1.8 kHz. Set this to `false` for silent operation.

The webcam is opened by one capture thread and only the latest frame is retained. Inference never reuses a frame to satisfy the stability count. MediaPipe uses synchronous VIDEO mode with increasing monotonic timestamps for tracking. Inference failures exit with an error; there is no silent backend fallback.

The sketch's heartbeat expires after **1.5 seconds** if Python stops responding, clearing MCU indicators LED3/LED4, Modulino Pixels, and the buzzer. An inference rate slower than that can cause flicker and repeat beeps; reduce camera resolution or try the other backend. The sketch provides `set_gesture_feedback(color, lights, sound)` through `Arduino_RouterBridge`, with color codes 0=off, 1=red, 2=green. It returns which Modulino modules were found at startup and schedules beeps without blocking the loop.

Linux controls LED1/LED2 through `/sys/class/leds`; they clear on gesture loss and normal shutdown, but do not have the MCU's hardware timeout if Python is forcibly killed. Standalone mode temporarily disables their system triggers and restores them on exit (Wi-Fi/Bluetooth status may resume). App Lab manages triggers outside its container. The runtime needs write access to those LED files.

Example console event:

```json
{"backend":"integrated","timestamp":1780000000.0,"gesture":"Thumb_Up","confidence":0.91,"hand":null,"raw_label":"good","led_color":"green"}
```

Human-readable logs go to stderr and JSON events go to stdout; both appear when run in a terminal. For example: `14:05:02 INFO gesture_app.output: Gesture=Open_Palm confidence=91% hand=right LEDs=red`. Use `--log-level WARNING` to suppress routine logs. Images are processed locally and are not saved or uploaded. Internet access is needed for initial package/model installation.

## Standalone MediaPipe test

The MediaPipe backend can also run in a Python environment on a development computer. Set **both `led.enabled` and `buzzer.enabled` to `false`** for this test. On Windows set `camera.device` to `0`. This is local capture for testing, not a camera server.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-mediapipe.txt
python scripts/download_model.py
python python/main.py --camera-test
python python/main.py
```

Set `backend` to `mediapipe` before the last command. On Windows use `.venv\Scripts\python.exe` for the commands after creating the environment; activation is optional. No GUI preview is required. Press Ctrl+C to stop.

MediaPipe is pinned to **1.0.1**, whose published wheels include Linux AArch64. Older MediaPipe versions and older board software may have different compatibility. Use a supported 64-bit board OS and up-to-date App Lab; don't attempt to install MediaPipe onto the MCU. See [MediaPipe's published distributions](https://pypi.org/project/mediapipe/1.0.1/) and [Python setup guide](https://developers.google.com/edge/mediapipe/solutions/setup_python).

## Troubleshooting and validation

- **Camera cannot open:** verify the capture node, powered hub, and device permissions. Close other apps using the webcam. Run `python python/main.py --camera-test` inside the same runtime to isolate capture from inference.
- **Model missing / wrong labels:** integrated mode must use `hand-gestures`, not the default general object detector. Update App Lab and board software if that model is absent. MediaPipe mode needs the `.task` file included by `prepare.py`.
- **Feedback Bridge call fails:** flash the updated sketch with `set_gesture_feedback`, or disable both LED and buzzer output for a desktop test.
- **Pixels/Buzzer missing:** check the Qwiic chain and restart the sketch with both modules connected. Module detection happens at sketch startup.
- **Linux RGB permission error:** use App Lab or run the standalone app with permission to write the six UNO Q LED brightness/trigger files. If your board requires elevated access, run the same command with `sudo` and the explicit `.venv/bin/python` path.
- **No recognized gesture:** face your palm toward the camera, use steady lighting and a plain background, and hold the gesture. Try a lower `min_confidence`; gestures unsupported by the selected model cannot be enabled by changing a threshold.

Python tests need only the standard library. If `g++` is available, the suite also runs both sketches against simulated hardware to verify beep timing, colors, and timeout behavior; otherwise that test is skipped.

```sh
python3 -m unittest discover -s tests -v
```

With MediaPipe installed and the model downloaded, `python scripts/smoke_mediapipe.py` also tests real inference on empty frames. Pass `--image path/to/gesture.jpg --expect Thumb_Up` to test a known gesture image. The downloader pins the official version-1 model URL and verifies SHA-256 before publishing it.

Tests cover config validation, backend selection, label mapping, confidence units, stability, red/green/off feedback, terminal logging, Linux RGB channels and trigger restoration, shutdown, and deployment contents. Hardware validation requires a physical UNO Q, webcam, Modulino Pixels, and Modulino Buzzer: check palm/red/two beeps, thumbs-up/green/one beep, held gestures without repeated beeps, hand removal, and shutdown. Test both backends on the same camera.

Official references: [UNO Q hardware](https://docs.arduino.cc/hardware/uno-q/), [Arduino Object Detection API](https://github.com/arduino/app-bricks-py/blob/main/src/arduino/app_bricks/object_detection/README.md), [Arduino App specification](https://github.com/arduino/arduino-app-cli/blob/main/docs/app-specification.md), [MediaPipe Gesture Recognizer](https://developers.google.com/edge/mediapipe/solutions/vision/gesture_recognizer/python).
