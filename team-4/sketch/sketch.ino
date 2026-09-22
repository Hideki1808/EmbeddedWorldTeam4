#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>

ModulinoPixels pixels;
ModulinoBuzzer buzzer;

int frequency = 440;

// Used for both leds and buzzer
long duration = 500;

long last_led_time = 0;
bool leds_on = false;

void setup() {
    Bridge.begin();

    Bridge.provide_safe("raised_palm", raised_palm);
    Bridge.provide_safe("thumbs_up", thumbs_up);
    Bridge.provide_safe("swipe", swipe);

    Monitor.begin();
    Modulino.begin(Wire1);

    if (!pixels.begin()) Monitor.println("Pixels not found!");
    if (!buzzer.begin()) Monitor.println("Buzzer not found!");
}

void show_gesture(ModulinoColor color) {
    delay(1):
    for (int i = 0; i < 8; i++) {
        pixels.set(i, color);
        delay(1);
    }
    pixels.show();
    buzzer.tone(frequency, duration);
    long current_time = millis();
    last_led_time = current_time;
    leds_on = true;
}

void raised_palm() {
    Monitor.println("Raised Palm");
    show_gesture(RED);
}

void thumbs_up() {
    Monitor.println("Thumbs up");
    show_gesture(BLUE);
}

void swipe() {
    Monitor.println("Swipe");
    show_gesture(GREEN);
}

void loop() {
    long current_time = millis();

    if (leds_on && current_time - last_led_time >= duration) {
        pixels.clear();
        delay(1);
        pixels.show();
        leds_on = false;
    }
}

