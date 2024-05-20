#!/usr/bin/env python3

# API information can be found here
# https://www.aviationweather.gov/help

import json
import time
import requests
import datetime
#import tkinter as tk
import re
import threading
import os

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from PIL import ImageFont
from DisplayWX import DisplayWX

'''
###########################################
# PURPOSE: gets weather data from KSLC    #
#          and Teal HQ, then translates   #
#          that data to text for          #
#          DisplayWX.py                   #
# AUTHOR : Asael Horne                    #
#          Jeff McGrath                   #
# VERSION: November 25, 2023              #
###########################################
'''
class WX_Controller:

    # initialize class fields
    wait = 5
    
    KSLC_Fields = [None] * 8    # KSLC_Fields = [K_ceiling, K_visib, K_windspd, K_gustSpd, K_winddir, K_temp, K_dewp, K_metar]
    TealHQ_Fields = [None] * 5  # TealHQ_Fields = [T_windSpeed, T_gustSpeed, T_temp, T_windDir, T_dewPoint]

    driver = None               # The driver for the web scraper
    service = None              # The service for the web scraper

    background_color = 'grey'
    word_colors = [None] * 4    # [ceiling, visib, wind_speed, gust_speed]

    status = 'Error'            # Start the status out as Error because I feel like it

    TealWind = False            # Are we going to use the wind value from KSLC or Teal?
    TealGust = True             # Are we going to use the gust value from KSLC or Teal? Starts out as true because it doesn't look like KSLC reports it anymore...



    ####################
    ## Helper Methods ##

    '''
    Makes a request to a website. If it fails, it tries again.
    '''
    def Make_Request(self, url):

        response = None
        tries = 5

        # try to get the website
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()  # Check for HTTP errors

        # if that fails, print an appropriate message and then try again in five seconds. Try five times
        except:
            if tries <= 0:
                print("Failed to connect and query the website after 5 attempts. Giving up...")
            else:
                print(f"Failed to connect and query the website. {tries} attempts left.")
                tries = tries - 1
                time.sleep(5)
                self.Make_Request(url)

        return response
    
    '''
    Checks to see if it's the Ceiling is above the legal limit. If it is, returns true. 
    If the ceiling reported is extrenuous, throws a value error. If nothing is reported, throws a type error. Tries to make sure there is no plus sign 
    on the end of the number using regex

    Parameter:
        c is the integer representation of the ceiling in feet
    '''  
    def High_Enough_Ceiling(self):

        c = self.KSLC_Fields[0]

        if c is None:
            raise TypeError("Expecting an Int")
        
        try:
            d = re.sub(r'[a-zA-Z-+]', '', c)
        except:
            d = c

        if (d < 0) or (d > 100000):
            raise ValueError("Int 0 to 90000 expected") 
        
        # True if we have the 500 foot clearance
        if d != 99999:
            if d > 499:
                return True
            else:
                return False
        else:
            return True
        
    '''
    Checks to see if it's the visibility is above the legal limit. True if 3sm or more. Throws exceptions if nothing is reported or an extrenuous value is reported.

    Parameter:
        v is the integer representation of the number of miles of visibility (None is default)
    '''
    def Good_Visibility(self):
        
        v = self.KSLC_Fields[1]

        if v is None:
            raise TypeError("Expecting an string")
        
        try:
            vis = int(v)
        except:
            temp_vis = re.sub(r'[a-zA-Z-+ ]', '', v)
            vis = int(temp_vis)

        if (vis < 0) or (vis > 100):
            raise ValueError("Int 0 to 100 expected") 

        # Checks to make sure Visibility is greater than or equal to 3sm
        if vis >= 3:
            return True
        else:
            return False

    ## End of Helper Methods ##
    ###########################



    '''
    Initializes an instance of this class.
    '''
    def __init__(self):
        print("Initializing...")

        options = Options()
        options.add_argument('--headless')
        geckodriver_path = "/home/ahorne/Downloads/Weather/geckodriver-v0.34.0-linux64/geckodriver"
        self.service = Service(geckodriver_path)
        self.driver = webdriver.Firefox(service=self.service, options=options)
        print("Ready")

    '''
    Closes the driver.
    '''
    def __del__(self):
        if self.driver != None:
            self.driver.quit()

    '''
    Makes requests to weather and parses the data
    '''
    def Pull(self):
         
        #-------------------------------------------------------------#
        #-- Get the conditions from Salt Lake International Airport --#
        #-------------------------------------------------------------#

        # get the response from the FAA's API
        response = self.Make_Request('https://aviationweather.gov/api/data/metar?ids=KSLC&format=geojson&taf=false')

        # if the response is empty, set all the KSLC fields to zeros; otherwise, get the data from the website
        if (response is None):
            return(0, 0, "0", 0.0, 0, 0.0, 0.0, 0.0)
        else:
            data = json.loads(response.content.decode())

        # set the fields from the retrieved data
        for feature in data['features']:
            
            # loop through the desired properties
            for key, value in feature['properties'].items():
                # ceiling
                if key == 'ceil':
                    try:
                        self.KSLC_Fields[0] = value * 100
                    except KeyError as e:
                        self.KSLC_Fields[0] = 99999
                    except Exception as e:
                        self.KSLC_Fields[0] = -99999
                        print('Ceiling is not being reported.')

                # visibility
                elif key == 'visib':
                    self.KSLC_Fields[1] = value

                # wind speed        
                elif key == 'wspd':
                    self.KSLC_Fields[2] = value    

                # gust speed
                elif key == 'wgst':
                    self.KSLC_Fields[3] = value 
                    
                # wind direction (coming from this angle)    
                elif key == 'wdir':    
                    self.KSLC_Fields[4] = value

                # temperature
                elif key == 'temp':    
                    self.KSLC_Fields[5] = value

                # dew point
                elif key == 'dewp':    
                    self.KSLC_Fields[6] = value

                # raw metar
                elif key == "rawOb":
                    self.KSLC_Fields[7] = value

        # it doesn't look like gust speed is reported anymore...
        if self.KSLC_Fields[3] is None:
            self.KSLC_Fields[3] = 'Not Reported'

        #-------------------------------------#
        #-- Get the conditions from Teal HQ --#
        #-------------------------------------#

        waitTime = WebDriverWait(self.driver, self.wait)

        self.driver.get("https://www.weatherlink.com/embeddablePage/show/a12ef9fcb99e41efa78329699223a163/summary")
        
        try:
            # wind speed
            avgWind_10min = waitTime.until(EC.presence_of_element_located((By.XPATH,"/html/body/div/div/div/div[2]/div[1]/div/div[2]/table/tbody/tr[2]/td[3]")))
            self.TealHQ_Fields[0] = avgWind_10min.text
            
            # gust speed
            avgGust_10min = waitTime.until(EC.presence_of_element_located((By.XPATH,"/html/body/div/div/div/div[2]/div[1]/div/div[2]/table/tbody/tr[3]/td[3]")))
            self.TealHQ_Fields[1] = avgGust_10min.text
            
            # temperature
            tempElement = waitTime.until(EC.presence_of_element_located((By.XPATH,"/html/body/div/div/div/div[2]/div[1]/div/div[1]/table/tbody/tr[2]/td[2]")))
            self.TealHQ_Fields[2] = tempElement.text
            
            # wind direction
            windDirectionElement = waitTime.until(EC.presence_of_element_located((By.XPATH,"/html/body/div/div/div/div[2]/div[1]/div/div[1]/table/tbody/tr[16]/td[2]")))
            self.TealHQ_Fields[3] = windDirectionElement.text
            
            # dew point
            dewpointElement = waitTime.until(EC.presence_of_element_located((By.XPATH,"/html/body/div/div/div/div[2]/div[1]/div/div[1]/table/tbody/tr[8]/td[2]")))
            self.TealHQ_Fields[4] = dewpointElement.text
            
        except:
            self.TealHQ_Fields = "0","0","0","0","UPDATE ERROR"


    '''
    Takes text and determines status/conditions
    '''
    def Analyze(self):

        # whatever weather is worse sets the status - pick the worse weather and then get the status info using that weather data
        try:
            if (self.KSLC_Fields[2] >= float(self.TealHQ_Fields[0].replace(' mph', ''))):
                wind = self.KSLC_Fields[2]
                self.TealWind = False
            elif (self.KSLC_Fields[2] < float(self.TealHQ_Fields[0].replace(' mph', ''))):
                wind = float(self.TealHQ_Fields[0].replace(' mph', '')) / 1.151     # converting mph to knots
                self.TealWind = True

            if (self.KSLC_Fields[3] >= float(self.TealHQ_Fields[1].replace(' mph', ''))):
                gust = self.KSLC_Fields[3]
                self.TealGust = False
            elif (self.KSLC_Fields[3] < float(self.TealHQ_Fields[1].replace(' mph', ''))):
                gust = float(self.TealHQ_Fields[1].replace(' mph', ''))  / 1.151    # converting mph to knots
                self.TealGust = True
        except:
            wind = 99999
            gust = 99999

        # you can fly freely if the conditions are HIGH Ceiling, HIGH Visibility, LOW Wind Speed, LOW Gust Speed
        if self.High_Enough_Ceiling() and self.Good_Visibility() and (self.KSLC_Fields[0] > 899) and (wind < 9.6) and (gust < 15.6):
            self.background_color = 'green'
            self.status = "Good to Fly \u2191"

        ## HIGH ceilings
        elif self.High_Enough_Ceiling() and (self.KSLC_Fields[0] > 899): 

            ## HIGH Visibility 
            if self.Good_Visibility():

                # be careful if the conditions are HIGH Ceiling, HIGH Visibility, LOW Wind Speed, MEDIUM Gust Speed
                if  (wind < 9.6) and (gust >= 15.6) and (gust < 21.7):
                    self.background_color = 'yellow'
                    self.status = "Okay to Fly with Restrictions \u2194"
                    self.word_colors[3] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, HIGH Visibility, LOW Wind Speed, HIGH Gust Speed
                elif (wind < 9.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # be careful if the conditions are HIGH Ceiling, HIGH Visibility, MEDIUM Wind Speed, LOW Gust Speed
                elif (wind >= 9.6) and (wind < 15.6) and (gust < 15.6):
                    self.background_color = 'yellow'
                    self.status = "Okay to Fly with Restrictions \u2194"
                    self.word_colors[2] = "orange"

                # be careful if the conditions are HIGH Ceiling, HIGH Visibility, MEDIUM Wind Speed, MEDIUM Gust Speed
                elif (wind >= 9.6) and (wind < 15.6) and (gust >= 15.6) and (gust < 21.7):
                    self.background_color = 'yellow'
                    self.status = "Okay to Fly with Restrictions \u2194"
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, HIGH Visibility, MEDIUM Wind Speed, HIGH Gust Speed
                elif (wind >= 9.6) and (wind < 15.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'pink'

                # don't fly if the conditions are HIGH Ceiling, HIGH Visibility, HIGH Wind Speed, LOW Gust Speed
                elif (wind >= 15.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[2] = 'pink'

                # don't fly if the conditions are HIGH Ceiling, HIGH Visibility, HIGH Wind Speed, MEDIUM Gust Speed
                elif (wind >= 15.6) and (gust >= 15.6) and (gust < 21.7):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, HIGH Visibility, HIGH Wind Speed, HIGH Gust Speed
                elif (wind >= 15.6) and (gust > 21.7):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'pink'

            ## LOW Visibility
            else:
                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, HIGH Wind Speed, HIGH Gust Speed
                if (wind >= 15.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, HIGH Wind Speed, MEDIUM Gust Speed
                elif (wind >= 15.6) and (gust >= 15.6) and (gust < 21.7):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, HIGH Wind Speed, LOW Gust Speed
                elif (wind >= 15.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'pink'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, MEDIUM Wind Speed, HIGH Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'pink'
                    self.word_colors[2] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, MEDIUM Wind Speed, MEDIUM Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'orange'
                    self.word_colors[2] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, MEDIUM Wind Speed, LOW Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, LOW Wind Speed, HIGH Gust Speed
                elif (wind < 9.6) and (gust > 21.7):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'pink'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, LOW Wind Speed, MEDIUM Gust Speed
                elif (wind < 9.6) and (gust <= 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'orange'

                # don't fly if the conditions are HIGH Ceiling, LOW Visibility, LOW Wind Speed, LOW Gust Speed
                elif (wind < 9.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.status = "Do Not Fly \u2193"
                    self.word_colors[1] = 'pink'

        ## MEDIUM Ceilings
        elif self.High_Enough_Ceiling() and (self.KSLC_Fields[0] < 899) and (self.KSLC_Fields[0] > 500):

            ## HIGH Visibility
            if self.Good_Visibility():

                # don't fly if the conditions are MEDIUM Ceiling, HIGH Visibility, HIGH Wind Speed, HIGH Gust Speed
                if (wind >= 15.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, HIGH Visibility, HIGH Wind Speed, MEDIUM Gust Speed
                elif (wind >= 15.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3]= 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, HIGH Visibility, HIGH Wind Speed, LOW Gust Speed
                elif (wind >= 15.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[2] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, HIGH Visibility, MEDIUM Wind Speed, HIGH Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # be careful if the conditions are MEDIUM Ceiling, HIGH Visibility, MEDIUM Wind Speed, MEDIUM Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'yellow'
                    self.word_colors[0] = 'orange'
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'orange'
                    self.status = "Okay To Fly With Restrictions \u2194"

                # be careful if the conditions are MEDIUM Ceiling, HIGH Visibility, MEDIUM Wind Speed, LOW Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 15.6):
                    self.background_color = 'yellow'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'orange'
                    self.status = "Okay To Fly With Restrictions \u2194"

                # don't fly if the conditions are MEDIUM Ceiling, HIGH Visibility, LOW Wind Speed, HIGH Gust Speed
                elif (wind < 9.6) and (gust > 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # be careful if the conditions are MEDIUM Ceiling, HIGH Visibility, LOW Wind Speed, MEDIUM Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 15.6):
                    self.background_color = 'yellow'
                    self.word_colors[0] = 'orange'
                    self.word_colors[3] = 'orange'
                    self.status = "Okay To Fly With Restrictions \u2194"

                # be careful if the conditions are MEDIUM Ceiling, HIGH Visibility, LOW Wind Speed, LOW Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 15.6):
                    self.background_color = 'yellow'
                    self.word_colors[0] = 'orange'
                    self.status = "Okay To Fly With Restrictions \u2194"

            ## LOW Visibility
            else:
                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, HIGH Wind Speed, HIGH Gust Speed
                if (wind >= 15.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3]= 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, HIGH Wind Speed, MEDIUM Gust Speed
                elif (wind >= 15.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, HIGH Wind Speed, LOW Gust Speed
                elif (wind >= 15.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, MEDIUM Wind Speed, HIGH Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, MEDIUM Wind Speed, MEDIUM Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, MEDIUM Wind Speed, LOW Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, LOW Wind Speed, HIGH Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, LOW Wind Speed, MEDIUM Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are MEDIUM Ceiling, LOW Visibility, LOW Wind Speed, low Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"

        ## LOW Ceiling
        elif not self.High_Enough_Ceiling():

            ## HIGH Visibility
            if self.Good_Visibility():

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, HIGH Wind Speed, HIGH Gust Speed
                if (wind >= 15.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, HIGH Wind Speed, MEDIUM Gust Speed
                elif (wind >= 15.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, HIGH Wind Speed, LOW Gust Speed
                elif (wind >= 15.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, MEDIUM Wind Speed, HIGH Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, MEDIUM Wind Speed, MEDIUM Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.word_colors[3] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, MEDIUM Wind Speed, LOW Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, LOW Wind Speed, MEDIUM Gust Speed
                elif (wind < 9.6) and (wind >= 15.6) and(gust < 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[3] = 'orange'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, HIGH Visibility, LOW Wind Speed, LOW Gust Speed
                elif (wind < 9.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.status = "Do Not Fly \u2193"

            ## LOW Visibility
            else:
                # don't fly if the conditions are LOW Ceiling, LOW Visibility, HIGH Wind Speed, HIGH Gust Speed
                if (wind >= 15.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'pink'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, LOW Visibility, HIGH Wind Speed, MEDIUM Gust Speed
                elif (wind >= 15.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.word_colors[3] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, LOW Visibility, HIGH Wind Speed, LOW Gust Speed
                elif (wind >= 15.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'pink'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, LOW Visibility, MEDIUM Wind Speed, HIGH Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust >= 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.word_colors[3] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, LOW Visibility, MEDIUM Wind Speed, MEDIUM Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 21.7) and (gust >= 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[2] = 'orange'
                    self.word_colors[3]= 'orange'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, LOW Visibility, MEDIUM Wind Speed, LOW Gust Speed
                elif (wind < 15.6) and (wind >= 9.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0]= 'pink'
                    self.word_colors[2] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, LOW Visibility, LOW Wind Speed, MEDIUM Gust Speed
                elif (wind < 9.6) and (gust >= 15.6) and(gust < 21.7):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[3] = 'orange'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"

                # don't fly if the conditions are LOW Ceiling, LOW Visibility, LOW Wind Speed, LOW Gust Speed
                elif (wind < 9.6) and (gust < 15.6):
                    self.background_color = 'red'
                    self.word_colors[0] = 'pink'
                    self.word_colors[1] = 'pink'
                    self.status = "Do Not Fly \u2193"


    '''
    Used by DisplayWX to get the text from this class
    '''
    def Give_To_Display(self):
        print("I do nothing right now2")

'''
Starts the program, handles timing
'''
if __name__ == "__main__":
    
    # inititalize the controller and view
    G = WX_Controller()
    D = DisplayWX()

    while (True):
        # pull the data
        G.Pull()

        # analyze the data
        G.Analyze()

        # send the data to the display 
        G.Give_To_Display()

        # display the weather and if it's ok to fly
        D.Display_Stuff()

        # wait for three minutes, then repeat
        time.sleep(180)
    