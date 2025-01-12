import time
from rpi_ws281x import *
import argparse


# LED strip configuration:
NUM_STRIPS = 5
NUM_LED_PER_STRIP = 19
LED_COUNT      = NUM_STRIPS*NUM_LED_PER_STRIP      # Number of LED pixels per strip

LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 240     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

NUM_RING = 0 
TRPL_RING = 10
DBL_RING = 1


# Base Functions
def colorWipe(strip, strip_num, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    start_seg, end_seg = getSegIndexes(strip_num) 
    for i in range(start_seg, end_seg):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def clearAll(strip, wait_ms=1): 
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, Color(0,0,0))
        strip.show()
        time.sleep(wait_ms/1000.0)

def numSeg(strip, strip_num, color, wait_ms=5):
    # light up number segment outside of dartboard
    if(strip_num % 2 == 0): #even num strip 
        pixel = NUM_RING + NUM_LED_PER_STRIP*strip_num
    else: # odd num strip 
        pixel = NUM_LED_PER_STRIP*strip_num + (NUM_LED_PER_STRIP - 1)
        
    strip.setPixelColor(pixel, color)
    strip.show()
    time.sleep(wait_ms/1000.0)
    
def tripleSeg(strip, strip_num, color, wait_ms=5):
    # light up triple segment
    if(strip_num % 2 == 0): #even num strip 
        pixel = TRPL_RING + NUM_LED_PER_STRIP*strip_num
    else: # odd num strip 
        pixel = NUM_LED_PER_STRIP*strip_num + (NUM_LED_PER_STRIP - TRPL_RING - 1)
      
    strip.setPixelColor(pixel, color)
    strip.show()
    time.sleep(wait_ms/1000.0)
    
def doubleSeg(strip, strip_num, color, wait_ms=5):
    # light up triple segment
    if(strip_num % 2 == 0): #even num strip 
        pixel = DBL_RING + NUM_LED_PER_STRIP*strip_num
    else: # odd num strip 
        pixel = NUM_LED_PER_STRIP*strip_num + (NUM_LED_PER_STRIP - DBL_RING - 1)
       
    strip.setPixelColor(pixel, color)
    strip.show()
    time.sleep(wait_ms/1000.0)

def outerSingleSeg(strip, strip_num, color, wait_ms=5):
    
    if(strip_num % 2 == 0): #even num strip 
        start_seg = (DBL_RING + NUM_LED_PER_STRIP*strip_num) + 1
        end_seg = TRPL_RING + NUM_LED_PER_STRIP*strip_num
    else: # odd num strip
        end_seg = NUM_LED_PER_STRIP*strip_num + (NUM_LED_PER_STRIP - DBL_RING) - 1
        start_seg = NUM_LED_PER_STRIP*strip_num + (NUM_LED_PER_STRIP - TRPL_RING)
       
    
    for i in range(start_seg, end_seg):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

def innerSingleSeg(strip, strip_num, color, wait_ms=5):
    
    if(strip_num % 2 == 0): #even num strip 
        start_seg = NUM_LED_PER_STRIP*strip_num + TRPL_RING + 1 
        end_seg = NUM_LED_PER_STRIP*strip_num + NUM_LED_PER_STRIP
    else: # odd num strip
        start_seg = NUM_LED_PER_STRIP*strip_num 
        end_seg = NUM_LED_PER_STRIP*strip_num + (NUM_LED_PER_STRIP - TRPL_RING - 1)
       
    
    for i in range(start_seg, end_seg):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms/1000.0)

            
        
# Main program testing 
if __name__ == '__main__':
    # Process arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
    args = parser.parse_args()

    # Create NeoPixel object with appropriate configuration.
    strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
    # Intialize the library (must be called once before other functions).
    strip.begin()

    print ('Press Ctrl-C to quit.')
    if not args.clear:
        print('Use "-c" argument to clear LEDs on exit')
        
    try:
        while True:
            
            strip_num = int(input("Enter the strip number: \n"))
            #colorWipe(strip, strip_num, Color(0,128,0), 5)

            numSeg(strip, strip_num, Color(0, 0, 255))
            tripleSeg(strip, strip_num, Color(0,128, 0))
            doubleSeg(strip, strip_num, Color(0,128, 0))
            
            outerSingleSeg(strip, strip_num, Color(0, 0, 255))            
            innerSingleSeg(strip, strip_num, Color(255, 0, 0))
            
            strip.setBrightness(120) # test 
            



    except KeyboardInterrupt:
        if args.clear:
            clearAll(strip)
