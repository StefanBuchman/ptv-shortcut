import json
from hashlib import sha1
import hmac
import binascii
import os
import haversine as hs
import requests
from datetime import datetime
from dateutil import tz
from dateutil import parser

# Load stops data from stops.json
with open('stops.json') as f:
    stops = json.load(f)

def getURL(request):
    devId = os.environ['id']
    key = os.environ['key']
    endpoint = os.environ['endpoint']
    
    request = request + ('&' if ('?' in request) else '?')
    raw = request+'devid={0}'.format(devId)
    
    # Encode the string
    key_bytes = bytes(key, 'latin-1')
    data_bytes = bytes(raw, 'latin-1')
    
    hashed = hmac.new(key_bytes, data_bytes, sha1)
    signature = hashed.hexdigest()
    
    return 'https://'+endpoint+raw+'&signature={1}'.format(devId, signature)

def callPTV(apiURL):
    
    response = requests.get(apiURL)
    
    if response.status_code == 200:
        ptvJSON = response.json()
        return ptvJSON
    else:
        return
    
def getClosestStop(lat, lon):

    myLat = float(lat)
    myLon = float(lon)

    closestStop = stops['McKinnon']
    closestStopDistance = hs.haversine((myLat, myLon), (closestStop['latitude'], closestStop['longitude']))

    log = os.environ['log']

    if log == "high":
        print('Initial distance from McKinnon is {0}'.format(round(closestStopDistance, 2)))

    for stop in stops:
        stopDict = stops[stop]
        stopDistance = hs.haversine((myLat, myLon), (stopDict['latitude'], stopDict['longitude']))
        if stopDistance < closestStopDistance:
            closestStop = stop
            closestStopDistance = stopDistance
            
        if log == "high":
            print('{0} is {1} kilometres away'.format(stop, round(stopDistance, 2)))

    if log == "high":
        print('The closest stop is {0}'.format(closestStop['name']))

    return closestStop

def lambda_handler(event, context):
    
    log = os.environ['log']
    
    if log == "high":
        print(event)
    
    myLat = event['headers']['location-lat']
    myLong = event['headers']['location-long']

    closestStop = getClosestStop(myLat, myLong)
    
    ptvRequest = '/v3/departures/route_type/{routeType}/stop/{stop}'\
        '/route/{route}?direction_id={direction}&max_results=1&'\
        'include_cancelled=false'.format(routeType = closestStop['type'], stop = closestStop['id'], 
        route = closestStop['route'], direction = closestStop['direction'])
    
    ptvURL = getURL(ptvRequest)
    ptvData = callPTV(ptvURL)

    if log == "high":
        print(ptvURL)
        print(ptvData)
    
    nextDepartureUTC = ptvData['departures'][0]['estimated_departure_utc']
    nextDeparture = parser.parse(nextDepartureUTC)
    
    to_zone = tz.gettz('Australia/Melbourne')
    nextDepartureMEL = nextDeparture.astimezone(to_zone)
    
    tz_info = nextDepartureMEL.tzinfo
    dtNow = datetime.now(tz_info)
    
    deltaTime = nextDepartureMEL - dtNow
    
    seconds = deltaTime.total_seconds()
    mins = round(seconds / 60)
    
    #message = 'The next train is departing at {0} {1} {2} in {3} minutes'.format(
    #    nextDepartureMEL.strftime("%-I"), nextDepartureMEL.strftime("%M"), nextDepartureMEL.strftime("%p"), mins)
        
    message = 'The next {0} train is departing at {1} in {2} minutes from platform {3}'\
        .format(closestStop['name'], nextDepartureMEL.strftime("%-I:%M %p"), mins, ptvData['departures'][0]['platform_number'])
    
    return {
        'statusCode': 200,
        'body': message
    }