# Deployed to Google CLoud local - run from repo root dir, first set env var for GCP credentials location:
# $env:GOOGLE_APPLICATION_CREDENTIALS="C:\code\SAL9000\sal9000-307923-dfcc8f474f83.json"
# gcloud functions deploy handleEvent --runtime python310 --trigger-http --allow-unauthenticated --project=sal9000-307923 --region=us-west2
# url: https://us-west2-sal9000-307923.cloudfunctions.net/handleEvent

# keywordExtraction API call: https://us-west2-sal9000-307923.cloudfunctions.net/keyphraseExtraction?message=helloSal9000
#  

from datetime import datetime
VERY_BEGINNING_TIME = datetime.utcnow()
START_TIME = VERY_BEGINNING_TIME

import json
from google.cloud import secretmanager
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import threading
import re
import gcloud_logging
from fastapi.encoders import jsonable_encoder

#openai
import os
import openai
from openai import OpenAI
#openai.error disappeared?
#from openai.error import InvalidRequestError

#urllib.request for getting openai generated png over http and upload into Slack
import urllib.request

#google trends https://towardsdatascience.com/google-trends-api-for-python-a84bc25db88f
from pytrends.request import TrendReq

#https://github.com/shroominic/codeinterpreter-api
#from codeinterpreterapi import CodeInterpreterSession
#import asyncio

def printTimeElapsed(starttime, label):
    endtime = datetime.utcnow()
    print(str(endtime-starttime)[:-4] + " " + label)
    return endtime

START_TIME = printTimeElapsed(START_TIME, 'import time')
GCP_PROJECT_ID = "sal9000-307923"

# Need to update Slack tokens as Slack expire them, either through console or gcloud:
# gcloud secrets versions add SLACK_BOT_TOKEN --data-file=secret.txt  --project=sal9000-307923 

client = secretmanager.SecretManagerServiceClient()
START_TIME = printTimeElapsed(START_TIME, 'secretmanager.SecretManagerServiceClient90')
def getGCPSecretKey(secretname):
    request = {"name": f"projects/{GCP_PROJECT_ID}/secrets/{secretname}/versions/latest"}
    response = client.access_secret_version(request)
    return response.payload.data.decode("UTF-8")
SLACK_BOT_TOKEN = getGCPSecretKey('SLACK_BOT_TOKEN')
SLACK_USER_TOKEN = getGCPSecretKey('SLACK_USER_TOKEN')

openai.api_key = getGCPSecretKey('OPENAI_API_KEY')
openAIClient = OpenAI(api_key=openai.api_key)
# 7/6/23 GPT-4 Engine upgrade https://openai.com/blog/gpt-4-api-general-availability?utm_source=tldrnewsletter
# https://platform.openai.com/docs/models
# https://openai.com/api/pricing/
#OPENAI_COMPLETION_ENGINE = "text-davinci-003"
#OPENAI_CHAT_ENGINE = "gpt-4-32k"
OPENAI_COMPLETION_ENGINE = "gpt-3.5-turbo"
OPENAI_CHAT_ENGINE = "gpt-3.5-turbo"

SLACK_WEB_CLIENT_BOT = WebClient(token=SLACK_BOT_TOKEN) 
SLACK_WEB_CLIENT_USER = WebClient(token=SLACK_USER_TOKEN) 

#Number of search buttons for SAL to render
NUM_BUTTONS_FIRST_POST = 5
NUM_BUTTONS_LATER = 5

#Number of search results SAL returns
NUM_SEARCH_RESULTS = 6

"""
COMMON_WORDS_3K = {''}

COMMON_WORDS_3K_FILE = open('3kcommonwords.txt')
with COMMON_WORDS_3K_FILE as reader:
    for this_word in reader:
        this_word = this_word.rstrip()
        COMMON_WORDS_3K.add(this_word)
print("3K set has : ", len(COMMON_WORDS_3K))
"""
ENDPOINT_URL = "https://us-west2-sal9000-307923.cloudfunctions.net/keyphraseExtraction?message="

SAL_USER = 'U01R035QE3Z'
SAL_IMAGE = 'https://bit.ly/39eK1bY'
SAL_THIN_IMAGE = 'https://files.slack.com/files-pri/T5FGEAL8M-F01SXUR4CJD/sal_thin.jpg?pub_secret=97e5e68214'

START_TIME = printTimeElapsed(START_TIME, 'all initialization time')
"""
def fetchChannelsMap():
    if len(STATIC_CHANNEL_ID_NAME_MAP) == 0:
        result = SLACK_WEB_CLIENT_USER.conversations_list(types="public_channel, private_channel")
        print("fetched channels: ", result)
        channels = result['channels']
        for channel in channels:
            print("this channel: ", channel['name'])
            STATIC_CHANNEL_ID_NAME_MAP.update({channel["id"]: channel["name"]})
    return STATIC_CHANNEL_ID_NAME_MAP
"""
# Handle SAL9001 slash commands
# Slack handleEvent webhook: https://us-west2-sal9000-307923.cloudfunctions.net/handleSlashCommand
# This webhook is set here: https://api.slack.com/apps/A01R8CEGVMF/slash-commands?
#
#
# /log [seconds] [error]
def handleSlashCommand(request):
    postForm = request.form
# For a /log command event:  
# handleSlashCommand POST form: ImmutableMultiDict([('token', '41px5FTEvkFHVLe5rCf7KQyU'), ('team_id', 'T5FGEAL8M'), ('team_domain', 'lacto'), ('channel_id', 'GUEPXFVDE'), ('channel_name', 'privategroup'), ('user_id', 'U5FGEALER'), ('user_name', 'genechuang'), ('command', '/log'), ('text', '10'), ('api_app_id', 'A01R8CEGVMF'), ('is_enterprise_install', 'false'), ('response_url', 'https://hooks.slack.com/commands/T5FGEAL8M/1921837490098/CmXXR07PZv2SfmwuM0q0xLb7'), ('trigger_id', '1934451302657.185558360293.bfc0b5306af56adf4ef03da0b07774ab')])
    if 'command' in postForm and postForm.get('command') == '/log':
        channel_id = postForm.get('channel_id')
        text = postForm.get('text')
        print('handleEvent /log ' + text)
        seconds = 60 # default 60 seconds
        onlyError = 0
        text = postForm.get('text')
        if len(text) > 0:
            tokens = text.split(' ')
            seconds = int(tokens[0])
            if seconds > 300:
                seconds = 300 #max 5 minutes

            if len(tokens) > 1 and "error" == tokens[1]:
                onlyError = 1


        log_entries = gcloud_logging.list_entries(seconds, onlyError)
        rtnText = ""
        for entry in log_entries:
            timestamp = entry.timestamp.isoformat()[:-10]
            rtnText += "`* {}: {}`\n".format(timestamp, entry.payload)
#        print('/log rtnText', rtnText)

#swapped these two around to pix a langchain pydantic issubclass() arg 1 must be a class error
#        return jsonify(response_type='in_channel',text=rtnText)
        return jsonable_encoder(rtnText)


# Return reverse order List of 2nd element
def sortList(list):
    # key is set to sort using second elemnet of
    # sublist lambda has been used
    list.sort(key = lambda x: x[1])
    list.reverse()
    return list


# Return the extracted key phrases using Open AI
def extractKeyPhrasesOpenAI(extractMe, keywordsCap):
    if len(extractMe) == 0:
        return []
    #Gonna strip all URLs from text for now
#    extractMe  = removeURLsFromText(extractMe)
#    print("stripped URLs", extractMe)

#strip all \n,- first
    print("extractKeyPhrasesOpenAI about to strip:" + extractMe)
    extractMe = extractMe.replace("-", " ")
    extractMe = extractMe.replace("\n", " ")
    extractMe = extractMe.replace(",", " ")
    extractMe = extractMe.replace("|", " ")
    extractMe = extractMe.replace("<", "")
    extractMe = extractMe.replace(">", "")
    extractMe = extractMe.replace("(", "")
    extractMe = extractMe.replace(")", "")
    print("extractKeyPhrasesOpenAI stripped:" + extractMe)
    response = openAIClient.chat.completions.create(
        model=OPENAI_COMPLETION_ENGINE, 
        messages=[{"role": "user", "content": "Extract keywords from this text order by topic:\n\n" + extractMe}])
    print('chatExtract raw response:', response)
    response = response.choices[0].message.content
    print("chatExtract responseTxt.choices[0].message.content: ", response)
    delim =''
    if response.find('\n') != -1:
        delim = '\n'
        extractedRawList =  response.split(delim)
    elif response.find(',') != -1:
        delim = ','
        extractedRawList =  response.split(delim)
    else: #single token
        extractedRawList =  [response]
#        extractedRawList[0] =  response

    returnList = []
    for i in extractedRawList:
        if len(i) > 0:
            returnList.append(i.strip("-").strip(" ").strip("\n")[:40])
    returnList = returnList[:keywordsCap]
    return returnList

# Return TL;DR summarization with OpenAI

def tldrOpenAI(summarizeMe):
    response = openAIClient.completions.create(
        engine=OPENAI_COMPLETION_ENGINE,
        prompt=summarizeMe +"\n\nTl;dr",
        temperature=0.7,
        max_tokens=60,
        top_p=1.0,
        frequency_penalty=0.0,
        presence_penalty=0.0
        )
    response =  response.choices[0].text
    return response

def keyphraseExtraction(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <https://flask.palletsprojects.com/en/1.1.x/api/#flask.Flask.make_response>`.
    """
    extractMe=''
    returnjson = 0
    request_json = request.get_json()
    if request_json and 'challenge' in request_json:
        #Slack url_verification challenge https://api.slack.com/events/url_verification
        return request_json['challenge']
    elif request.args and 'message' in request.args:
        returnjson = 'returnjson' in request.args
        extractMe = request.args.get('message')
    elif request_json and 'message' in request_json:
        returnjson = request_json['returnjson']
        extractMe =  request_json['message']
    else:
        extractMe = ''
    
    extractedKeyPhrases = extractKeyPhrasesOpenAI(extractMe, NUM_BUTTONS_FIRST_POST)

    return str(extractedKeyPhrases)

"""
ChatGPT 
"""
def ChatGPT(text):
    print('ChatGPT request:', text)
    print('ChatGPT request length:', len(text))
    if len(text) < 1:
        return "I have no answer to that."
    responseTxt = openAIClient.chat.completions.create(
        model=OPENAI_CHAT_ENGINE, 
        messages=[{"role": "user", "content": text}])
    print('ChatGPT raw response:', responseTxt)
    responseTxt = responseTxt.choices[0].message.content
    print("ChatGPT responseTxt.choices[0].message.content: ", responseTxt)
    return responseTxt


# DALL-E image complete with OpenAI
# https://beta.openai.com/docs/guides/images/introduction
def dalleOpenAI(drawMe):
    response = openAIClient.images.generate(
        model="dall-e-2",
        prompt=drawMe,
        n=1,
        size="1024x1024",
        quality="standard"
        )
    image_url = response.data[0].url
    return image_url
    
"""
sarcasticSAL takes eventAttributes with channel_id and text and calls OpenAI Marv to get a sarcastic response and posts in channel
"""
def sarcasticSALResponse(text):
    response = openAIClient.completions.create(
        engine=OPENAI_COMPLETION_ENGINE,
        prompt="Marv is a chatbot that reluctantly answers questions with sarcastic responses:\n\nYou: " + text + "\n",
        temperature=0.5,
        max_tokens=60,
        top_p=0.3,
        frequency_penalty=0.5,
        presence_penalty=0.0
    )
    responseTxt = response.choices[0].text[6:] #skip the first 6 chars which is "Marv: "
    print('sarcastic sal response:', responseTxt)
    return responseTxt

SALLE_CHANNEL = 'C049KEY2BCK'


"""
Args:
    request (flask.Request): The request object
Returns:
    The response text, or any set of values that can be turned into a
    Response object using `make_response`

Slack handleEvent webhook: https://us-west2-sal9000-307923.cloudfunctions.net/handleEvent
Event handler for 3 types of events:
1) New message to public channel (message.channels) or private channel (message.groups), events registered here: https://api.slack.com/apps/A01R8CEGVMF/event-subscriptions?
EventSubscription detected a top post in channel, SAL9000 to extract KeyPhrase, Search and Respond
2) User adds :sal9001: emoji to post, SAL to reply to that post
3) Interactive user push search button. Registered here: https://api.slack.com/apps/A01R8CEGVMF/interactive-messages
Use selected a keyphrase from SAL9001 first response, perform Search and Respond with search results

Deployed to Google CLoud local - run from repo root dir:
gcloud functions deploy handleEvent --runtime python310 --trigger-http --allow-unauthenticated --project=sal9000-307923 --region=us-west2

"""

def handleEvent(request):
    print("handleEvent request: ", request)

    # Google Scheduler 5 minute warmer
    # https://us-west2-sal9000-307923.cloudfunctions.net/handleEvent?warmer=true
    if request.args.get('warmer'): 
        print('handleEvent Google Scheduler 5 min warmer')
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 

    # Don't handle any retry requests - Slack sends retries if it doesn't get response in 3 seconds
    retryNum = request.headers.get('X-Slack-Retry-Num')
    print('handleEvent retryNum: ', retryNum)
    if retryNum and int(retryNum) >= 1:
        return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 
    
    eventAttributes = {}

#    if request.method == 'GET': # GET - must be new post event message.channels or message.groups
    if request.is_json: # GET - must be new post event message.channels or message.groups
        request_json = request.get_json()
        print("handleEvent request.get_json(): ", request_json)
        if 'challenge' in request_json:
        #Slack url_verification challenge https://api.slack.com/events/url_verification
            return request_json['challenge']
        event = request_json['event']
        if event:
            if 'bot_id' in event:
                print('This is a bot message so not responding to it')
# 5/25/2022 removing Subtype fall through because it excludes posts with attachments which is a subtype='file_share' - I don't remember why I'm excluding subtype in the first place so keep it commented out
#            elif event.get("subtype"):
#                print('This is subtype so not responding to it: ', event.get("subtype"))
            elif 'text' in event and not event.get('text').startswith("/"): #User top post, SAL to respond for first time OR DM directly with SAL9001, activate Sarcastic SAL Chatbot
                print("main.handleEvent GET text: ", event['text'])
                channel_type = event['channel_type']
                # if DM with @SAL9001 or user evoked SAL in thread or text starts with 'draw me' - activate ChatGPT/Dall-E SAL Chatbot
                if 'im' == channel_type or ('thread_ts' in event and SAL_USER in event.get('text')) or SALLE_CHANNEL == event['channel'] or "draw me" in event['text'].lower(): 
                    eventAttributes = {
                        'user': event['user'],
                        'channel_id': event['channel'],
                        'thread_ts': event['ts'],
                        'channel_type': channel_type,
                        'text': event['text']
                    }
                    SALResponse(eventAttributes)
                    return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 

                elif 'thread_ts' not in event : #User top post in channel, SAL to respond in thread for first time
                    eventAttributes = {
                        'user': event['user'],
                        'channel_id': event['channel'],
                        'thread_ts': event['ts'],
                        'text': event['text'],
                        'searchme': '',
                        'keyphrasesCap': NUM_BUTTONS_FIRST_POST 
                    }
            elif 'reaction_added' == event.get('type') and "sal9001" == event.get('reaction') and 'message' == event.get('item').get('type'): #User add sal9001 emoji::
                print('main.handleEven GET :sal9001: emoji payload:', event)
                channel_id = event.get('item').get('channel')
                ts = event.get('item').get('ts')
                user = event.get('user')
                #Get message from Slack API to get text
                response = SLACK_WEB_CLIENT_USER.conversations_history(channel=channel_id,latest=ts,limit=1,inclusive='true') 
                if response:
                    print('retrived whole response: ', response)
                    thisMessage =  response.get('messages')[0]
                    print('retrieved requested ts: ' + ts + " got response ts: " + thisMessage.get('ts') + " I hope: " + str(thisMessage))
                    if thisMessage.get('ts') == ts: #only respond to top message emoji
                        text = thisMessage.get('text')
                        eventAttributes = {
                            'user': user,
                            'channel_id': channel_id,
                            'thread_ts': ts,
                            'text': text,
                            'searchme': '',
                            'keyphrasesCap': NUM_BUTTONS_LATER 
                        }

            else:
                print("This GET request fell through all filters, event: ", event)
        else:
            print("This message has no event element?? Doing nothing...")
    elif request.form is not None: # POST - either /log command or user push search button event
        postForm = request.form
        print("handleEvent POST form:", postForm)
        if 'command' in postForm and postForm.get('command') == '/log':
            return handleSlashCommand(request)

        if postForm.get('payload') is None:
            print("handleEvent POST form payload is null, returning!")
            return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 

        payload = json.loads(str(postForm.get('payload')))
        print('main.handleEven POST Interactive Event with payload: ', payload)
        payload_type = payload["type"]
        if "block_actions" == payload_type: #User pushed a search button
            text = payload['message']['text']
            print("main.handleEvent POST bock_action text: ", text)
            order = 'desc'
            parseSearchAndOrder = payload["actions"][0]['value'].split('|')
            print("main.handleEvent POST bock_action button action: ", parseSearchAndOrder)
            searchme = parseSearchAndOrder[0]
            if len(parseSearchAndOrder) > 1: # to remain backwards compatible with older questions without order token
                order = parseSearchAndOrder[1]

            eventAttributes = {
                'user': payload['user']['id'],
                'channel_id': payload['channel']['id'],
                'thread_ts': payload['message']['thread_ts'], 
                'this_ts': payload['message']['ts'], 
                'searchme': searchme,
                'order': order,
                'text': text,
                'keyphrasesCap': NUM_BUTTONS_LATER 
            }
            print("main.handleEvent POST bock_action eventAttributes: ", eventAttributes)


    if len(eventAttributes) > 0:
        constructAndPostBlock(eventAttributes)
    return json.dumps({'success':True}), 200, {'ContentType':'application/json'} 


# Asynchronously Construct a Slack block and post/update it
# Don't use this for now as weird stuff happens
def constructAndPostBlockAsync(eventAttributes):
    thread = threading.Thread(target=constructAndPostBlock, args=[eventAttributes])
    thread.start()


# Construct a Slack block and post/update it
def constructAndPostBlock(eventAttributes):
    startime = datetime.utcnow() 
    block = constructBlock(eventAttributes)
    printTimeElapsed(startime, 'constructBlock')
    startime2 = datetime.utcnow() 
    print("constructAndPostBlock: constructed block: ", block)
    response = postBlockToSlackChannel(eventAttributes, block)
    printTimeElapsed(startime2, 'postBlockToSlackChannel')
#    printTimeElapsed(startime, 'constructAndPostBlock')

#Posts a Block to parent post thread_ts.  
# If this_ts > 0, this is a user button push, update the existing block with with new search results
def postBlockToSlackChannel(eventAttributes, block):
    channel_id = eventAttributes['channel_id']
    text = eventAttributes['text']
    response = ''
    try:
        if 'this_ts' not in eventAttributes: 
###            print('posting new block to thread:', block)
            thread_ts = eventAttributes['thread_ts']
            response = SLACK_WEB_CLIENT_BOT.chat_postMessage(
                channel = channel_id,
                thread_ts=thread_ts,
                text = text,
                blocks = block
            )
        else: # user button push of existing block, update
            this_ts = eventAttributes['this_ts']
            print('update existing block to thread because this_ts:', this_ts)
            response = SLACK_WEB_CLIENT_BOT.chat_update(
                channel = channel_id,
                ts=this_ts,
                blocks = block,
                text = text,
                attachments=[] #zero out attachments just in case
            )

    except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
        print('error postBlockToSlackChannel:', e)
        assert e.response["error"]    # str like 'invalid_auth', 'channel_not_found'
    return response    


# Return Q&A with OpenAI

def qAndAOpenAI(answerMe):
    response = openai.ChatCompletion.create(
        model=OPENAI_CHAT_ENGINE, 
        messages=[{"role": "user", "content": answerMe}])

    return response

"""
ChatGPT 
"""
def ChatGPT(text):
    print('ChatGPT request:', text)
    print('ChatGPT request length:', len(text))
    if len(text) < 1:
        return "I have no answer to that."
    responseTxt = openAIClient.chat.completions.create(
        model=OPENAI_CHAT_ENGINE, 
        messages=[{"role": "user", "content": text}])
    print('ChatGPT raw response:', responseTxt)
    responseTxt = responseTxt.choices[0].message.content
    print("ChatGPT responseTxt.choices[0].message.content: ", responseTxt)
    return responseTxt


    
"""
sarcasticSAL takes eventAttributes with channel_id and text and calls OpenAI Marv to get a sarcastic response and posts in channel
"""
def sarcasticSALResponse(text):
    response = openAIClient.chat.completions.create(
        engine=OPENAI_COMPLETION_ENGINE,
        prompt="Marv is a chatbot that reluctantly answers questions with sarcastic responses:\n\nYou: " + text + "\n",
        temperature=0.5,
        max_tokens=60,
        top_p=0.3,
        frequency_penalty=0.5,
        presence_penalty=0.0
    )
    responseTxt = response.choices[0].text[6:] #skip the first 6 chars which is "Marv: "
    print('sarcastic sal response:', responseTxt)
    return responseTxt

SALLE_CHANNEL = 'C049KEY2BCK'

def SALResponse(eventAttributes):
    channel_id = eventAttributes['channel_id']
    thread_ts = eventAttributes['thread_ts']
    text = eventAttributes['text']
    channel_type = eventAttributes['channel_type']

    # if text contains 'draw me', activate Dall-e, otherwise ChatGPT                    
#    print('text.lower():', text.lower())
    if "draw me" in text.lower():
        startIndex = text.lower().index("draw me") + len("draw me")
        text = text[startIndex:] 
        print('bout to draw text: ', text)
#        try:
        dalleurl = dalleOpenAI(text)
        webUrl = urllib.request.urlopen(dalleurl)

        new_file = SLACK_WEB_CLIENT_BOT.files_upload(
            title="MyImage",
            content=webUrl.read(),
            filetype='png',
            channels=channel_id
        )
        file_url = new_file.get("file").get("permalink")
        print("uploaded image into slack permalink: ", file_url)
        response = "I drew" + text + " <" + file_url +"|here>"

#        except InvalidRequestError as e:
#            dalleurl = ''
#            response = "OpenAI cannot draw " + text + " because " + e.user_message
        try:
            #If in SALLE_CHANNEL or DM @SAL post in channel, otherwise post in thread
            if SALLE_CHANNEL == channel_id or 'im' == channel_type:
                response = SLACK_WEB_CLIENT_BOT.chat_postMessage(
                    channel = channel_id,
                    text = response
                )
            else:
                response = SLACK_WEB_CLIENT_BOT.chat_postMessage(
                        channel = channel_id,
                        thread_ts=thread_ts,
                        text = response
                    )


        except SlackApiError as e:
        # You will get a SlackApiError if "ok" is False
            print('error postBlockToSlackChannel:', e)
            assert e.response["error"]    # str like 'invalid_auth', 'channel_not_found'

    else:
        response = ChatGPT(text)
        if 'im' == channel_type:  # If IM/DM don't thread response
            print('respond in the channel!')    
            response = SLACK_WEB_CLIENT_BOT.chat_postMessage(
                channel = channel_id,
                text = response
            )
        else:
            print('respond in the thread!')    
            response = SLACK_WEB_CLIENT_BOT.chat_postMessage(
                    channel = channel_id,
                    thread_ts=thread_ts,
                    text = response
                )

    return response    

# This method will construct the Slack Block 
def constructBlock(eventAttributes):
    starttime = datetime.utcnow()
    text = eventAttributes['text']
    user = eventAttributes['user']
    channel_id = eventAttributes['channel_id']
    keyphrasesCap = eventAttributes['keyphrasesCap']
    searchme = ''
    order = 'desc'
    if 'searchme' in eventAttributes:
        searchme = eventAttributes['searchme']
    if 'order' in eventAttributes:
        order = eventAttributes['order']

    extractedKeyPhrases = extractKeyPhrasesOpenAI(text, keyphrasesCap)

    ChatGPTResponse = ChatGPT(text)
    greetings = "OpenAI Chat Model " + OPENAI_CHAT_ENGINE + ": " + ChatGPTResponse + "\nOther CTO Slackers have this to say:\n"
    slack_block_kit = [
        {
			"type": "image",
			"block_id": "sal_THIN_image",
			"image_url": SAL_THIN_IMAGE,
			"alt_text": "SAL 9001"
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": greetings
			}
        }
    ]

#    print('Slack Blockkit: ', slack_block_kit)
    count = 0
    searchButtons = []
    for keyPhrase in extractedKeyPhrases:
        thisButtonStyle = "primary"
        if len(searchme) > 0:
            if searchme == keyPhrase:
                thisButtonStyle = "danger"
                #flip order
                if order == 'asc':
                    order = 'desc'
                else:
                    order = 'asc'
        elif count == 0:
            thisButtonStyle = "danger"
            searchme = keyPhrase
        count += 1    

        searchButtons.append(
            {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": keyPhrase
                },
    			"style": thisButtonStyle,
                "value": keyPhrase + "|" + order,
            }
        )

    if len(searchButtons) > 0:
        slack_block_kit.append(
            {
                "type": "actions",
                "elements": searchButtons
            }
        )

    searchResultsString = ''
    if len(searchme) > 1: #don't bother searching if searchme length <= 1
        searchResults = searchSlackMessages(searchme, channel_id, NUM_SEARCH_RESULTS, 1, order)
        count = 1
        thread_ts = ''
        if 'thread_ts' in eventAttributes:
            thread_ts = eventAttributes['thread_ts']
        for thisSearchResult in searchResults['messages']['matches']:
            thisUser = thisSearchResult['user']
            thisUserName = thisSearchResult['username']
            this_ts = thisSearchResult['ts']
            thisDate = datetime.fromtimestamp(int(this_ts.split(".")[0])).strftime('%m-%d-%y')
            thisText = thisSearchResult['text']
#            thisTLDR = tldrOpenAI(thisText)

            if SAL_USER == thisUser: #skip posts by SAL
                continue
            if thread_ts == this_ts: #skip this parent post
                continue
#            Doing @user will cause SAL to push notify the user
#            thisUserName = "<@" + thisUserName + ">"

            searchResultsString += "<" + thisSearchResult['permalink'] + "|" + thisDate + "> " + " from " + thisUserName+ "\n"
            count += 1

    if len(searchResultsString) == 0:
        searchResultsString = "I'm sorry <@" + user + ">. I'm afraid I can't do that."    

    endtime = datetime.utcnow()
    elapsestr = str(endtime-starttime)[:-4]
    searchResultsString += "\nsearch time: " + elapsestr
    slack_block_kit.append(
       {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": searchResultsString
            }
        }
    )
 
    return slack_block_kit

"""
Removes all URLs from text.  First strip <https:> tags then https: urls
"""
def removeURLsFromText(text):
    text = re.sub(r'<?http\S+', '', text)
    return re.sub(r'http\S+', '', text)

# defining a params dict for the parameters to be sent to the API 
# https://api.slack.com/methods/search.messages
#  
# arguments
# query=text, count=20, highlight=true, page=1, sort=score/timestamp, sort_dir=desc/asc, team_id=T1234567890
#
# Returns json of results as described: https://api.slack.com/methods/search.messages  
def searchSlackMessages(text, channel_id, resultCount, page, order):
#    print ('searchSlackMessages in channel_id: ', channel_id)
#    channel_name = fetchChannelsMap().get(channel_id)
#    print ('searchSlackMessages in channel_name: ', channel_name)

    response = SLACK_WEB_CLIENT_USER.search_messages(query='"' + str(text) + '"', sort='score', sort_dir=order, count=resultCount, page=page)
#    response = SLACK_WEB_CLIENT_USER.search_messages(query='in:#' + str(channel_name) + ' "' + text + '"', sort='score', sort_dir=order, count=resultCount, page=page)

#    print ('search response: ', response)
    return response


# Google Trend return list of most popular daily search terms
# google trends https://towardsdatascience.com/google-trends-api-for-python-a84bc25db88f
def getGoogleTrendList():

    pytrend = TrendReq()
    df = pytrend.trending_searches (pn='united_states')
    df = df.reset_index()
    print("df[0].size ", df[0].size)
    print("df[0] ", df[0])
    rtn = []
    for row in df[0]:
        rtn.append(row)
    print("rtn:", rtn)
    return rtn

# codeinterpreter https://github.com/shroominic/codeinterpreter-api
"""
async def codeinterpreter():
    # create a session
    session = CodeInterpreterSession(openai_api_key=openai.api_key)
    await session.astart()

    # generate a response based on user input
    response = await session.generate_response(
        "Plot the bitcoin chart of 2023 YTD"
    )

    # output the response (text + image)
    print("AI: ", response.content)
    for file in response.files:
        file.show_image()

    # terminate the session
    await session.astop()
"""
# Main for commandline run and quick tests
# $env:GOOGLE_APPLICATION_CREDENTIALS="C:\code\SAL9000\sal9000-307923-dfcc8f474f83.json"
if __name__ == "__main__":
    print("openapi.key: ", openai.api_key)
    START_TIME = printTimeElapsed(START_TIME, 'main start')

# $env:OPENAI_API_KEY="thekey"
    os.environ["OPENAI_API_KEY"] = openai.api_key
#    print("Why doesn't this work?? OS Env OPENAI_API_KEY: ", os.environ["OPENAI_API_KEY"])
# run the async function
    
#    asyncio.run(codeinterpreter())

    TEST_STRINGS = [
        "What's the best cloud data warehouse?"
#         "Has anyone tried https://test.ai/ for AI based QA?  I may try this out soon."
#         "draw me mandalorian riding a bicycle photograph style"gcl
#        "Chewy rocks! I like this quote: When you’re nice, people smile. When you’re really nice, people talk. And when you’re exceptionally and consistently nice, you go viral. https://jasonfeifer.bulletin.com/this-company-s-customer-service-is-so-insanely-good-it-went-viral"
#        "Webinar: How to reason about indexing your Postgres database by <https://www.linkedin.com/in/lfittl/|Lukas Fittl> founder of <http://pganalyze.com|pganalyze.com> (he was founding engineer of Citus which I've used in previous project for managed sharded Postgres)  <https://us02web.zoom.us/webinar/register/9816552361071/WN_cjrUDKVuSqO8GckfiCWkbA>"
#        "Bill Gates says crypto and NFTs are a sham.\n\nWell Windows and Office are a sham.  So it takes one to know one! https://www.cnn.com/2022/06/15/tech/bill-gates-crypto-nfts-comments/index.html"
#        "Hi all - thank you @Lee Ditiangkin for the invite! I'm co-founder / GP of a new B2B-centric pre-seed and seed-stage fund called Garuda Ventures (garuda.vc). Previously was an early employee at Okta, where I was an early/founding member of all of our inorganic growth functions (M&A, BD, Ventures) -- and before that did a few other things back East in NYC/DC (law/finance/etc). Am based in the Bay Area, but we invest everywhere.\nExcited to meet and learn from technical leaders, operators, and entrepreneurs (and hopefully re-connect with some familiar faces :slightly_smiling_face:). Our portfolio companies are also always hiring. Feel free to reach out! Always up for a chat.",
#        "Any recommendations for an easy to use no code platform to do mobile app POCs?  A non-technical friend wants to do some prototyping.  I'm looking at bubble.io, flutterflow.io, appgyver.com and appypie.com.  Ideally, I'd like her to start with something that can later be easily ported to a more permanent architecture if her ideas become viable.",
#        "Morning Slackers - Anyone here using the enterprise version of https://readme.com/pricing . If so, how much are you paying? Any alternatives?",
#        "Anyone used https://www.thoughtspot.com/ before or currently using it?"
#        "Okta not having a good morning:\nhttps://twitter.com/_MG_/status/1506109152665382920"
#        "Not sure where to post this: I'm looking for the recommendation of the dev shops that can absorb the product dev and support soup to nuts, preferably in LatAm, I've already reached out to EPAM, looking for more leads"
#        "This has been asked a few times on here already, but curious if anyone has developed any strong opinions since the last time it was asked. What has worked the best for your front end teams in E2E testing React Native apps? Appium? Detox?",
#        "I am looking for a good vendor who has integrations to all of the adtech systems out there to gather and normalize campaign performance data. Ideally, it would be a connector or api we can implement to aggregate campaign performance data.  Also, we have a data lake in S3 and Snowflake, if that helps. Please let me know if anyone knows of any good providers in this space.  Thx!!",    
#        "Can someone point me to feature flagging best practices? How do you name your feature flags? How do you ensure a configuration of flags is compatible?"
        ]

# Test Dall-e draw
    dalleURL = dalleOpenAI("Homer Simpson chasing a turkey on a farm, by Matt Groening, matte painting trending on artstation hq")
    print('Dall-E: ', dalleURL)


    for extractme in TEST_STRINGS:
        print("OpenAI extracted phrases:", extractKeyPhrasesOpenAI(extractme, NUM_BUTTONS_FIRST_POST))
#        print('\nmain test Original text:', extractme)
#        ChatGPT(extractme)

#        print("OpenAI answer:", qAndAOpenAI(extractme))
#        print("OpenAI tldr:", tldrOpenAI(extractme))
#        print("OpenAI sarcastic:", SALResponse(extractme))
#    postMessageToSlackChannel('test', '', 'Best crm?')        

    # Test Constructing and posting new block to Slack

#    response = SLACK_WEB_CLIENT_USER.conversations_history(channel=TEST_CHANNEL_ID,latest=TEST_TS,limit=1,inclusive='true') 
    thisMessage = TEST_STRINGS[0]

#    if response:
#        print('retrived whole response: ', response)
#        thisMessage =  response.get('messages')[0].get('text')
#    print('Extracting real Slack message:', thisMessage)
#    print("OpenAI extracted phrases:", extractKeyPhrasesOpenAI(thisMessage, NUM_BUTTONS_FIRST_POST))
#    print("OpenAI extracted phrases null:", extractKeyPhrasesOpenAI("", NUM_BUTTONS_FIRST_POST))

# Test ChatGPT + Slack Post
    TEST_USER = 'U5FGEALER' # Gene
    TEST_TS = '1667580780.319159'
    TEST_CHANNEL_ID = 'GUEPXFVDE' #test
    TEST_CHANNEL_NAME = 'test' #test
"""
    eventAttributes = {
            'text': "best CRM?", 
            'channel_id': TEST_CHANNEL_ID, 
            'channel_type': "post", 
            "thread_ts": "1683745710.504239",
            'user': TEST_USER,
            'keyphrasesCap': NUM_BUTTONS_FIRST_POST 
        }
    constructAndPostBlock(eventAttributes)
"""
"""
# Google trend draw test
    trendsList = getGoogleTrendList()
    eventAttributes = {
            'text': "Drawing trends: " + " ".join(trendsList), 
            'channel_id': TEST_CHANNEL_ID, 
            'channel_type': "post", 
            "thread_ts":    TEST_TS,
            'user': TEST_USER,
        }
    SALResponse(eventAttributes)
    for thisTrend in trendsList:
        thisMessage = "draw me " + thisTrend + ", matte painting trending on deviantart"
        eventAttributes = {
            'text': thisMessage, 
            'channel_id': TEST_CHANNEL_ID, 
            'channel_type': "post", 
            "thread_ts":    TEST_TS,
            'user': TEST_USER,
            }
        SALResponse(eventAttributes)

#    SALResponse(eventAttributes)

    constructAndPostBlock(eventAttributes)

#    channelsMap = fetchChannelsMap()
#    print('channelsMap: ', channelsMap)

    START_TIME = printTimeElapsed(VERY_BEGINNING_TIME, 'total')

    # test Gcloud logging get entries
#
#     log_entries = gcloud_logging.list_entries(10, 0)
"""


