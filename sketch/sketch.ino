#include <Arduino_
#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>

ModulinoPixels pixels;
ModulinoBuzzer buzzer;

int frequency = 440;

// Used for both leds and buzzer
long duration = 500;

long last_led_time = 0;

void setup() {
    Bridge.begin();

    Bridge.provide("raised_palm", raised_palm);
    Bridge.provide("thumbs_up", thumbs_up);
    Bridge.provide("swipe", swipe);

    // Initialize Modulino I2C communication
    Modulino.begin(Wire1);

    pixels.begin();
    buzzer.begin();
}

void show_gesture(ModulinoColor color) {
    pixels.clear();
    for (int i = 0; i < 8; i++) {
        pixels.set(0, color);
    }
    pixels.show();
    buzzer.tone(frequency, duration);
    long current_time = millis();
    last_led_time = current_time;
}

void raised_palm() {
    show_gesture(RED);
}

void thumbs_up() {
    show_gesture(BLUE);
}

void swipe() {
    show_gesture(GREEN);
}

void loop() {
    long current_time = millis();

    if (current_time - last_led_time >= duration) {
        pixels.clear();
        pixels.show();
    }
}

