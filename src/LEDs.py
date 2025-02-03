

"""
LEDs.py 

Function: 
This file is holds the functions to control the LED strips for the dartboard. 
"""

import time
from rpi_ws281x import *
import argparse

class LEDs:

    def __init__(self):
        # LED strip configuration:
        self.NUM_STRIPS = 5
        self.NUM_LED_PER_STRIP = 19
        self.LED_COUNT      = self.NUM_STRIPS*self.NUM_LED_PER_STRIP      # Number of LED pixels per strip

        self.LED_PIN        = 18      # GPIO pin connected to the pixels (18 uses PWM!).
        self.LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
        self.LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
        self.LED_BRIGHTNESS = 240     # Set to 0 for darkest and 255 for brightest
        self.LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
        self.LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

        self.NUM_RING = 0 
        self.TRPL_RING = 10
        self.DBL_RING = 1

        # Initialize the LED strip
        self.strip = Adafruit_NeoPixel(
            self.LED_COUNT, self.LED_PIN, self.LED_FREQ_HZ,
            self.LED_DMA, self.LED_INVERT, self.LED_BRIGHTNESS, self.LED_CHANNEL
        )
        self.strip.begin()

    def getSegIndexes(self, strip_num):
    
        start_seg = strip_num*self.NUM_LED_PER_STRIP
        end_seg = start_seg + self.NUM_LED_PER_STRIP
        
        return start_seg, end_seg 
    
    # Sweep colors across strip     
    def colorWipe(self, strip_num, color, wait_ms=50):
        start_seg, end_seg = self.getSegIndexes(strip_num) 
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, color)
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    # Turn off all LEDs
    def clearAll(self, wait_ms=1): 
        for i in range(self.strip.numPixels()):
            self.strip.setPixelColor(i, Color(0,0,0))
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    # Lights up number segment on outer circumference of dartboard 
    def numSeg(self, strip_num, color, wait_ms=5):
        # light up number segment outside of dartboard
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.NUM_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - 1)
            
        self.strip.setPixelColor(pixel, color)
        self.strip.show()
        time.sleep(wait_ms/1000.0)
        
    # Lights up triple segment 
    def tripleSeg(self, strip_num, color, wait_ms=5):
        # light up triple segment
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.TRPL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)
        
        self.strip.setPixelColor(pixel, color)
        self.strip.show()
        time.sleep(wait_ms/1000.0)
        
    # Lights up double segment 
    def doubleSeg(self, strip_num, color, wait_ms=5):
        # light up triple segment
        if(strip_num % 2 == 0): #even num strip 
            pixel = self.DBL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip 
            pixel = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING - 1)
        
        self.strip.setPixelColor(pixel, color)
        self.strip.show()
        time.sleep(wait_ms/1000.0)

    # Lights up outer single segment (closest to circumference)
    def outerSingleSeg(self, strip_num, color, wait_ms=5):
        
        if(strip_num % 2 == 0): #even num strip 
            start_seg = (self.DBL_RING + self.NUM_LED_PER_STRIP*strip_num) + 1
            end_seg = self.TRPL_RING + self.NUM_LED_PER_STRIP*strip_num
        else: # odd num strip
            end_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.DBL_RING) - 1
            start_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING)
        
        
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, color)
            self.strip.show()
            time.sleep(wait_ms/1000.0)

    # Lights up inner single segment (furthest from circumference)
    def innerSingleSeg(self, strip_num, color, wait_ms=5):
        
        if(strip_num % 2 == 0): #even num strip 
            start_seg = self.NUM_LED_PER_STRIP*strip_num + self.TRPL_RING + 1 
            end_seg = self.NUM_LED_PER_STRIP*strip_num + self.NUM_LED_PER_STRIP
        else: # odd num strip
            start_seg = self.NUM_LED_PER_STRIP*strip_num 
            end_seg = self.NUM_LED_PER_STRIP*strip_num + (self.NUM_LED_PER_STRIP - self.TRPL_RING - 1)
        
        
        for i in range(start_seg, end_seg):
            self.strip.setPixelColor(i, color)
            self.strip.show()
            time.sleep(wait_ms/1000.0)

                    
        
# # Main program testing 
# if __name__ == '__main__':
#     # Process arguments
#     parser = argparse.ArgumentParser()
#     parser.add_argument('-c', '--clear', action='store_true', help='clear the display on exit')
#     args = parser.parse_args()

#     # Create NeoPixel object with appropriate configuration.
#     strip = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
#     # Intialize the library (must be called once before other functions).
#     strip.begin()

#     print ('Press Ctrl-C to quit.')
#     if not args.clear:
#         print('Use "-c" argument to clear LEDs on exit')
        
#     try:
#         while True:
            
#             strip_num = int(input("Enter the strip number: \n"))
#             #colorWipe(strip, strip_num, Color(0,128,0), 5)

#             numSeg(strip, strip_num, Color(0, 0, 255))
#             tripleSeg(strip, strip_num, Color(0,128, 0))
#             doubleSeg(strip, strip_num, Color(0,128, 0))
            
#             outerSingleSeg(strip, strip_num, Color(0, 0, 255))            
#             innerSingleSeg(strip, strip_num, Color(255, 0, 0))
            
#             strip.setBrightness(120) # test 
            



#     except KeyboardInterrupt:
#         if args.clear:
#             clearAll(strip)
