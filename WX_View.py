import json
import time
import datetime
import asyncio
import re
import os
import sys
import WX_Model
from pyscript import document   

def main():

    document.querySelector("#ceiling").innerText = "Look! A ceiling!"
    document.querySelector("#visibility").innerText = "It worked! I can see!"
    document.querySelector("#last_update").innerText = "I have never updated anything"
    document.querySelector("#metar").innerText = "metar"
    document.querySelector("#status").innerText = "Good To Fly \u2191"
    # sideways arrow: \u2194
    # up arrow: \u2191
    # down arrow: \u2193

    # inititalize the model
    G = WX_Model()
    
    #while (True):
        # pull the data
    #    paragraph_p.text = G.Pull()

        # analyze the data
        #G.Analyze()

        # wait for three minutes, then repeat
    #    time.sleep(180)

# IDK what this is but the program doesn't work without it
if __name__ == "__main__":
    main()