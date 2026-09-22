from arduino.app_utils import *
import time

def test_loop():
    Bridge.call("raised_palm");
    sleep(1);
    Bridge.call("thumbs_up");
    sleep(1);
    Bridge.call("swipe");
    sleep(1);

App.run(user_loop=test_loop)