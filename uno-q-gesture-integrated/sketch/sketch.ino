#include <Arduino_RouterBridge.h>
#include <Modulino.h>

// MCU RGB indicators and Modulino modules share the main-loop context.
constexpr unsigned long FEEDBACK_TIMEOUT_MS = 1500;
constexpr unsigned long BEEP_MS = 100;
constexpr unsigned long BEEP_INTERVAL_MS = 200;
constexpr uint8_t PIXEL_BRIGHTNESS = 25;  // Percent, applied to all eight LEDs.
const int RGB_PINS[] = {LED3_R, LED3_G, LED3_B, LED4_R, LED4_G, LED4_B};
ModulinoPixels pixels;
ModulinoBuzzer buzzer;
bool pixelsReady = false;
bool buzzerReady = false;
unsigned long lastHeartbeat = 0;
unsigned long lastBeep = 0;
int gestureColor = 0;  // RPC protocol: 0=off, 1=red, 2=green, 3=blue.
int displayedColor = 0;
int remainingBeeps = 0;
bool soundEnabled = false;

void stop_buzzer() {
  remainingBeeps = 0;
  if (buzzerReady) {
    buzzer.noTone();
  }
}

void show_color(int color) {
  // LED3 and LED4 are active-low. Clear every channel before changing color.
  for (int pin : RGB_PINS) {
    digitalWrite(pin, HIGH);
  }
  if (color == 1) {
    digitalWrite(LED3_R, LOW);
    digitalWrite(LED4_R, LOW);
  } else if (color == 2) {
    digitalWrite(LED3_G, LOW);
    digitalWrite(LED4_G, LOW);
  } else if (color == 3) {
    digitalWrite(LED3_B, LOW);
    digitalWrite(LED4_B, LOW);
  }
  if (pixelsReady) {
    for (int i = 0; i < 8; ++i) {
      pixels.set(i, color == 1 ? 255 : 0, color == 2 ? 255 : 0,
                 color == 3 ? 255 : 0, PIXEL_BRIGHTNESS);
    }
    pixels.show();
  }
  displayedColor = color;
}

void play_beep() {
  const int frequency = gestureColor == 1 ? 1000 : gestureColor == 2 ? 1800 : 1400;
  buzzer.tone(frequency, BEEP_MS);
  lastBeep = millis();
}

int set_gesture_feedback(int color, bool lights, bool sound) {
  if (color < 0 || color > 3) {
    color = 0;
  }
  const bool changed = color != gestureColor;
  lastHeartbeat = millis();
  gestureColor = color;
  if ((lights ? color : 0) != displayedColor) {
    show_color(lights ? color : 0);
  }
  if (color == 0 || !sound) {
    stop_buzzer();
  } else if (buzzerReady && (changed || !soundEnabled)) {
    stop_buzzer();
    remainingBeeps = color == 1 ? 1 : color == 3 ? 2 : 0;
    play_beep();
  }
  soundEnabled = sound;
  // Heartbeats repeat color, but do not restart a held gesture's beeps.
  return (pixelsReady ? 1 : 0) | (buzzerReady ? 2 : 0);
}

void setup() {
  for (int pin : RGB_PINS) {
    pinMode(pin, OUTPUT);
    digitalWrite(pin, HIGH);
  }
  Modulino.begin(Wire1);  // UNO Q Qwiic connector, not the header I2C bus.
  pixelsReady = pixels.begin();
  buzzerReady = buzzer.begin();
  show_color(0);
  stop_buzzer();
  Bridge.begin();
  Bridge.provide_safe("set_gesture_feedback", set_gesture_feedback);
}

void loop() {
  if (gestureColor != 0 && millis() - lastHeartbeat >= FEEDBACK_TIMEOUT_MS) {
    gestureColor = 0;
    show_color(0);
    stop_buzzer();
  }
  if (remainingBeeps > 0 && millis() - lastBeep >= BEEP_INTERVAL_MS) {
    --remainingBeeps;
    play_beep();
  }
  delay(10);
}
