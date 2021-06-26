import paho.mqtt.client as mqtt
import tkinter 
import time
import numpy as np
from PIL import Image, ImageTk
import json
from matplotlib import pyplot as plt
import matplotlib
matplotlib.use("Agg")
import threading 
import tkinter.font as font
from gtts import gTTS
from playsound import playsound
import os
import shelve # provides persistent storage
from datetime import datetime
# generate random floating point values
from random import seed
from random import random
seed(1)
from threading import Lock
lock = Lock()

# Idle function
def spin():
    return 1

# Decompress the incoming MQTT list message
def decompress_list(inp_list):
    decompressed_list = []
    for compressed_data in inp_list:
        cur_reading = compressed_data[0]
        cur_count = compressed_data[1]
        for i in range(cur_count):
            decompressed_list.append(cur_reading)
    return decompressed_list

# Handle incoming MQTT Publish Messages
def clear_gui():
    widget_list = all_children(window)
    for item in widget_list:
        item.grid_forget()
        item.place_forget()
        item.pack_forget()

# Obtains all window children, used to clear_gui()
def all_children (window) :
    _list = window.winfo_children()
    for item in _list :
        if item.winfo_children() :
            _list.extend(item.winfo_children())
    return _list

def notWorkoutDone():
    global workoutDone
    time.sleep(0.1)
    lock.acquire()
    workoutDoneLocal = workoutDone
    lock.release()
    return not workoutDoneLocal

def getContinuation():
    global continuation
    lock.acquire()
    continuationLocal = continuation
    lock.release()
    return continuationLocal

def getWorkoutType():
    global workoutType
    lock.acquire()
    workoutTypeLocal = workoutType
    lock.release()
    return workoutTypeLocal

def on_message(client, userdata, message):
    messageString = message.payload.decode('utf-8')
    global workoutType
    global connected
    global dataReceived
    global calibrated
    global lbl
    global window
    global imageGraph 
    global imgGraph
    global imgGraphlbl
    global continuation
    global workoutDuration
    global workoutDone
    if messageString == "AWAITING_INPUT":
        lock.acquire()
        connected = True
        lock.release()
    elif messageString == "CALIBRATED":
        lock.acquire()
        calibrated = True
        lock.release()
    else:
        inp_list = json.loads(messageString)
        
        # Live voice assistant feedback
        lock.acquire()
        workoutDurationlocal=workoutDuration
        lock.release()
        if len(inp_list) != 0 and inp_list[0] == "NEW_POSITION_INFO":
            
            # variable to determine whether workout is paused
            lock.acquire()
            continuation = inp_list[1][3]
            lock.release()
            va_speech = "This will never be heard"
            if continuation == 1:
                # obtain current position
                cur_pos = inp_list[1]
                
                # obtain ideal position
                ideal_pos = inp_list[2]
                
                # obtain difference and provide feedback
                cur_x = cur_pos[0]
                cur_y = cur_pos[1]
                cur_z = cur_pos[2]
                
                ideal_x = ideal_pos[0]
                ideal_y = ideal_pos[1]
                ideal_z = ideal_pos[2]
                
                # handle feedback depending on corresponding workout
                workoutTypeLocal = getWorkoutType()
                if workoutTypeLocal == 1:
                    if cur_y - ideal_y <= -6: 
                        va_speech = "please lean slightly forwards"
                    elif cur_y - ideal_y >=  6:
                        va_speech = "please lean slightly backwards"
                    elif abs(cur_x - ideal_x) >= 360:
                        va_speech = "please straighten your back"
                    else:
                        va_speech = "you're doing great, hold this position"
            
                elif workoutTypeLocal == 2:
                    if cur_y - ideal_y >= 5:
                        va_speech = "please bend your body slightly less"
                    elif cur_y - ideal_y <= -5:
                        va_speech = "please bend your body slightly more"
                    elif abs(cur_x - ideal_x) >= 5:
                        va_speech = "please straighten your back"
                    else:
                        va_speech = "you're doing great, hold this position"
            
                elif workoutTypeLocal == 3:
                    if abs(cur_x - ideal_x) >= 5 or abs(cur_y - ideal_y) >= 5:
                        va_speech = "please straighten your back"
                    else:
                        va_speech = "you're doing great, hold this position"
                
            else:
                va_speech = "workout paused"
                #print("workout_paused")
        
            # live voice assistant
            if  notWorkoutDone():
                try:
                    va_obj = gTTS(text=va_speech, slow=False)
                    va_obj.save("guide.mp3")
                    playsound("guide.mp3")
                    os.remove("guide.mp3")
                except:
                    lock.acquire()
                    lbl.configure(text="Voice assistant unavailable, please connect your device to the internet")
                    lock.release()
                    time.sleep(4)
                    #on_closing()
            
            
        else:
            lock.acquire()
            dataReceived = True
            lock.release()
            
            # Plot Performance Feedback Graph
            deviations_list = decompress_list(inp_list[0])
            #print("deviations_list: ", deviations_list)
            scores = [((90 - i)/90.0)*100 for i in deviations_list]#offloading some processing to the device, compression necessary on pi to reduce mqtt traffic
            for j in range(len(scores)):
                if scores[j] < 0:
                    scores[j] = 0
                    #print("Zeroing")
            #print("scores ", scores)
            labels = np.arange(0,len(scores)/10.0, step=1).tolist()
            idx = np.asarray([i for i in range(7)])
            fig, ax = plt.subplots(figsize = (8,4))
            ax.plot(scores)

            plt.xticks(np.arange(0, len(scores), step=10), labels)
            plt.xlabel("Time (seconds)")
            plt.ylabel("Balance Score (/100)")
            plt.savefig('graph.png')
            plt.ylim([0, 100])
            balanceScore = sum(scores) / len(scores)

            lock.acquire()
            clear_gui()
            lock.release()
            lock.acquire()
            lbl.place(x=20, y = 20)
            lbl.configure(text="Overall Balance: " + str(round(balanceScore, 0)))
            imageGraph = Image.open('graph.png')
            imgGraph= ImageTk.PhotoImage(imageGraph)
            imgGraphlbl = tkinter.Label(image=imgGraph)
            imgGraphlbl.place(x = 15, y = 80)
            bHome.grid(row = 60, column = 5)
            lock.release()
            
            
            # Feedback Voice Assistant
            coords_pos = inp_list[1]
            ideal_pos = inp_list[2]
            
            avg_x = coords_pos[0]
            avg_y = coords_pos[1]
            avg_z = coords_pos[2]
            
            ideal_x = ideal_pos[0]
            ideal_y = ideal_pos[1]
            ideal_z = ideal_pos[2]
            now = datetime.now()
            stringDate = now.strftime("%d/%m/%Y")
            
            # Handles feedback depending on workout type
            lock.acquire()
            workoutTypeLocal = workoutType
            lock.release()
            if workoutTypeLocal == 1:
                if avg_x - ideal_x <= -5:
                    va_speech = "As overall feedback, in this exercise, you should try to lean forwards more"
                elif avg_x - ideal_x >= 5:
                    va_speech = "For feedback, in this exercise, you should try to lean slightly more backwards"
                elif abs(avg_y - ideal_y) >= 5:
                    va_speech = "As feedback, you should try to straighten your back more in this exercise"
                else:
                    va_speech = "You did really well! keep it up"
                if("Lotus" in logs):
                    lock.acquire()
                    logs["Lotus"].append((stringDate + "," +str(time.time()), round(balanceScore, 2)))
                    lock.release()
                else:
                    lock.acquire()
                    logs["Lotus"] = [(stringDate + "," +str(time.time()), round(balanceScore, 2))]
                    lock.release()
            
            elif workoutTypeLocal == 2:
                if avg_x - ideal_x >= 5:
                    va_speech = "As overall feedback, in this exercise, you should try to bend your body less"
                elif avg_x - ideal_x <= -5:
                    va_speech = "For feedback, in this exercise, you should try to bend your body more"
                elif abs(avg_y - ideal_y) >= 5:
                    va_speech = "As feedback, you should try to straighten your back more in this exercise"
                else:
                    va_speech = "You performed really well! Keep it up"
                if("Rose" in logs):
                    lock.acquire()
                    logs["Rose"].append((stringDate + "," +str(time.time()), round(balanceScore, 2)))
                    lock.release()
                else:
                    lock.acquire()
                    logs["Rose"] = [(stringDate + "," +str(time.time()), round(balanceScore, 2))]
                    lock.release()
            elif workoutTypeLocal == 3:
                if abs(avg_x - ideal_x) >= 5 or abs(avg_y - ideal_y) >= 5 or abs(avg_z-ideal_z) >= 5:
                    va_speech = "As an overall feedback, you should try to straighten your back more in this exercise"
                else:
                    va_speech = "You performed really well! Keep it up"
                if("Chrysanthemum" in logs):
                    lock.acquire()
                    logs["Chrysanthemum"].append((stringDate + "," +str(time.time()), round(balanceScore, 2)))
                    lock.release()
                else:
                    lock.acquire()
                    logs["Chrysanthemum"] = [(stringDate + "," +str(time.time()), round(balanceScore, 2))]
                    lock.release()
            time.sleep(2)
            
            # voice assistant feedback
            try:
                va_obj = gTTS(text="Great work." + va_speech, slow=False)
                va_obj.save("feedback.mp3")
                playsound("feedback.mp3")
                os.remove("feedback.mp3")
            except:
                lock.acquire()
                lbl.configure(text="Voice assistant unavailable, please connect your device to the internet")
                lock.release()
                time.sleep(4)
                #on_closing()
            
            

# Start specific workout
def startWorkout():
    global client
    global lbl
    global window
    global bigFont
    global calibrated
    global dataReceived
    global workoutType
    global workoutDuration
    global workoutDone

    lock.acquire()
    clear_gui()
    lbl.place(x=20, y = 20)
    workoutTypeLocal = workoutType
    lock.release()

    posePath = 'Error'
    poseText = 'Error'
    if workoutTypeLocal == 1:
        posePath = 'poseOne.png'
        poseText = 'Lotus'
    elif workoutTypeLocal == 2:
        posePath = 'poseTwo.png'
        poseText = 'Rose'
    elif workoutTypeLocal == 3:
        posePath = 'poseThree.png'
        poseText = 'Chrysanthemum'
        
    # Sends workout type to device via MQTT publish
    
    try:
        va_obj = gTTS(text="Connection test", slow=False)
        va_obj.save("testConn.mp3")
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/deviceOmar",payload=workoutTypeLocal)
    except:
        lock.acquire()
        lbl.configure(text="Connection error, please ensure that your PC is connected to the internet.")
        lock.release()
        time.sleep(4)
        on_closing()
    
    
    imagePose = Image.open(posePath)
    imgPose = ImageTk.PhotoImage(imagePose)
    imgPoselbl = tkinter.Label(image=imgPose, background = "#FFF9F3")

    lock.acquire()
    imgPoselbl.place(x = 50, y = 120)
    lbl.configure(text= poseText + " Pose")
    lock.release()
    
    # Calibration Voice Assistant
    try:
        va_obj = gTTS(text="Warmup: please follow and hold the pose shown for five consecutive seconds", slow=False)
        va_obj.save("calibrating.mp3")
        playsound("calibrating.mp3")
        os.remove("calibrating.mp3")
    except:
        lock.acquire()
        lbl.configure(text="Voice assistant unavailable, please connect your device to the internet")
        lock.release()
        time.sleep(4)
        #on_closing()
    
    
    for i in range(0, 5):
        lbl.configure(text= "Warmup starts in: " + str(5-i))
        time.sleep(1)

    imageLoading = Image.open('loading.png')
    pixeldata = list(imageLoading.getdata())
    imgLoading = ImageTk.PhotoImage(imageLoading)

 
    imglblLoading = tkinter.Label(image=imgLoading, background= "#FFF9F3")
    imglblLoading.grid(row = 40, column = 11)
    try:
        va_obj = gTTS(text="Connection test", slow=False)
        va_obj.save("testConn.mp3")
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/deviceOmar",payload="ACK")
    except:
        lock.acquire()
        lbl.configure(text="Connection error, please ensure that your PC is connected to the internet.")
        lock.release()
        time.sleep(4)
        on_closing()
    
    
    lock.acquire()
    lbl.configure(text="Warmup")
    lock.release()
    
    alpha = 30
    increase = True
    
    # Wait until calibration finished
    while notCalibrated():
        for i,pixel in enumerate(pixeldata):
            r = pixel[0]
            g = pixel[1]
            b = pixel[2]
            if (r < 5) and (g > 170 and g < 182) and (b > 234 and b < 246 ):
                pixeldata[i] = (0,176,240,alpha)
        imageLoading.putdata(pixeldata)
        if alpha == 200:
            increase = False
        elif alpha == 30:
            increase = True
        if increase == True:
            alpha = alpha + 10
        else:
            alpha = alpha - 10
        imgLoading = ImageTk.PhotoImage(imageLoading)
        imglblLoading.configure(image=imgLoading)
        
        time.sleep(0.0233)

    lock.acquire()
    calibrated = False
    lock.release()
    #print("Warmup successful/n workout starts in 3")
    
    # Workout Starting Voice Assistant
    try:
        va_obj = gTTS(text="warmup is completed. The workout is now about to begin, please follow the pose shown in the image", slow=False)
        va_obj.save("workout.mp3")
    except:
        lock.acquire()
        lbl.configure(text="Voice assistant unavailable, please connect your device to the internet")
        lock.release()
        time.sleep(4)
        #on_closing()

    playsound("workout.mp3")
    os.remove("workout.mp3")
    
    for i in range(0, 3):
        lock.acquire()
        lbl.config(text= "Workout starts in: " + str(3-i))
        lock.release()
        time.sleep(1)
    #rint("Show me that balance dahling ( ͡° ͜ʖ ͡°)")
    
    try:
        va_obj = gTTS(text="Connection test", slow=False)
        va_obj.save("testConn.mp3")
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/deviceOmar",payload="ACK")
    except:
        lock.acquire()
        lbl.configure(text="Connection error, please ensure that your PC is connected to the internet.")
        lock.release()
        time.sleep(4)
        on_closing()

    
    # Define workout duration (seconds)
    lock.acquire()
    workoutDurationLocal = workoutDuration
    lock.release()

    while workoutDurationLocal > 0:
       if continuation == 1:
           lock.acquire()
           lbl.configure(text = "Time left: " + str(workoutDurationLocal))
           lock.release()
           workoutDurationLocal = workoutDurationLocal-1
           if(workoutDurationLocal == 0):
               lock.acquire()
               workoutDone = True
               lock.release()
           time.sleep(1)
       else:
          lock.acquire()
          lbl.configure(text = "Time left: workout paused ")
          lock.release()
          workoutDurationLocal = workoutDurationLocal
          time.sleep(1) 
    
    
    lbl.configure(text= "Workout Complete, getting results: ") 
    try:
        va_obj = gTTS(text="Connection test", slow=False)
        va_obj.save("testConn.mp3")
        
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/deviceOmar",payload="WORKOUT_COMPLETE")
    except:
        lock.acquire()
        lbl.configure(text="Connection error, please ensure that your PC is connected to the internet.")
        lock.release()
        time.sleep(4)
        on_closing()
    

    # Wait until workout data is received for feedback
    while (notDataReceived()):
        spin()

    lock.acquire()
    workoutDone = False
    dataReceived = False
    lock.release()

def notCalibrated():
    global calibrated
    lock.acquire()
    calibratedLocal = calibrated
    lock.release()
    return (not calibratedLocal)

def notConnected():
    global connected
    lock.acquire()
    connectedLocal = connected
    lock.release()
    return (not connectedLocal)

def notDataReceived():
    global dataReceived
    lock.acquire()
    dataReceivedLocal = dataReceived
    lock.release()
    return (not dataReceivedLocal)


# Obtain duration of workout
def confirmDuration():
    global workoutDuration
    global threadsList
    lock.acquire()
    clear_gui()
    workoutDuration = int(entry_widget.get())

    t=threading.Thread(target=startWorkout) 
    threadsList.append(t)
    lock.release()
    t.daemon = True
    t.start()
    
# Handles display for workout1
def onWorkoutOneSelected ():
    global workoutType
    global lbl
    global entry_widget
    global bConf
    lock.acquire()#no other tasks to do here so although crit section is long, user will have to wait util things update
    clear_gui()
    lbl.configure(text="Set workout duration: ")
    lbl.place(x=20, y = 20)
    workoutType = 1
    entry_widget = tkinter.Entry(window)
    entry_widget.insert(0, "30")
    entry_widget.place(x = 50, y = 150)
    bConf = tkinter.Button(window, text="Confirm")
    bConf.configure(command=confirmDuration)
    bConf.place(x = 50, y = 250)
    bConf['font'] = bigFont
    entry_widget['font'] = bigFont
    lock.release()

# Handles display for workout2 
def onWorkoutTwoSelected ():
    global workoutType
    global lbl
    global entry_widget
    global bConf
    lock.acquire()
    clear_gui()
    lbl.configure(text="Set workout duration: ")
    lbl.place(x=20, y = 20)
    workoutType = 2
    entry_widget = tkinter.Entry(window)
    entry_widget.insert(0, "30")
    entry_widget.place(x = 50, y = 150)
    bConf = tkinter.Button(window, text="Confirm")
    bConf.configure(command=confirmDuration)
    bConf.place(x = 50, y = 250)
    bConf['font'] = bigFont
    entry_widget['font'] = bigFont
    lock.release()
# Handles display for workout3
def onWorkoutThreeSelected ():
    global workoutType
    global lbl
    global entry_widget
    global bConf
    lock.acquire()
    clear_gui()
    lbl.configure(text="Set workout duration: ")
    lbl.place(x=20, y = 20)
    workoutType = 3
    entry_widget = tkinter.Entry(window)
    entry_widget.insert(0, "30")
    entry_widget.place(x = 50, y = 150)
    bConf = tkinter.Button(window, text="Confirm")
    bConf.configure(command=confirmDuration)
    bConf.place(x = 50, y = 250)
    bConf['font'] = bigFont
    entry_widget['font'] = bigFont
    lock.release()

# Obtain history of all workouts 
def onWorkoutHistorySelected ():
    lock.acquire()
    clear_gui()
    b1.grid_forget()
    b2.grid_forget()
    b3.grid_forget()
    b4.pack_forget()
    b4.grid_forget()
    lbl.place(x=20, y = 20)
    lbl.configure(text="Select history")
    b5['font'] = bigFont
    b6['font'] = bigFont
    b7['font'] = bigFont
    bHome.grid(row = 60, column = 5)
    b5.grid(row = 10, column = 5)
    b6.grid(row = 10, column = 15)
    b7.grid(row = 10, column = 25)
    b5.configure(command=onHistoryOneSelected, bg='#C26E20')
    b6.configure(command=onHistoryTwoSelected,  bg='#C26E20')
    b7.configure(command=onHistoryThreeSelected,  bg='#C26E20')
    lock.release()

# Obtains history of all workout1
def onHistoryOneSelected():
    global workoutType
    lock.acquire()
    lbl.place(x=20, y = 20)
    workoutType = 1
    lock.release()
    if("Lotus" in logs):
         showHistory()
    else:
        lock.acquire()
        lbl.configure(text="No past workouts, why not go for a Lotus pose now?")
        lock.release()
    

# Obtains history of all workout2
def onHistoryTwoSelected():
    global workoutType
    lock.acquire()
    lbl.place(x=20, y = 20)
    workoutType = 2
    lock.release()
    if("Rose" in logs):
         showHistory()
    else:
        lock.acquire()
        lbl.configure(text="No past workouts, why not go for a Rose pose now?")
        lock.release()
    

# Obtains history of all workout3
def onHistoryThreeSelected():
    global workoutType
    lock.acquire()
    lbl.place(x=20, y = 20)
    workoutType = 3
    lock.release()
    if("Chrysanthemum" in logs):
         showHistory()
    else:
        lock.acquire()
        lbl.configure(text="No past workouts, why not go for a Chrysanthemum pose now?")
        lock.release()
    
        
# Display all workout type to see historical performance
def showHistory():
    global imgHis
    global imageGraphHis
    global imgGraphHis
    global imgGraphlblHis
    
    lock.acquire()
    workoutTypeLocal = workoutType
    lock.release()

    if(workoutTypeLocal == 1):
        workoutName = "Lotus"
        histImagePath = "lotusHistory.png"
    elif(workoutTypeLocal == 2):
        workoutName = "Rose"
        histImagePath = "roseHistory.png"
    elif(workoutTypeLocal == 3):
        workoutName = "Chrysanthemum"
        histImagePath = "chrysHistory.png"
    
    lock.acquire()
    b5.grid_forget()
    b6.grid_forget()
    b7.grid_forget()

    lbl.configure(text=workoutName + " Pose History")
    

    
    listTmp = logs[workoutName][:]
    lock.release()

    dates = []
    scores = []
    datesLabels = []
    for x in range(len(listTmp)): 
        if x > 7:
            break
        dates.append(listTmp[len(listTmp)-x-1][0])
        datesLabels.append(listTmp[len(listTmp)-x-1][0].split(",")[0])
        scores.append(listTmp[len(listTmp)-x-1][1])
    i = 1
    while(len(dates) < 7):
        dates.append("No data " + str(i))
        datesLabels.append("")
        scores.append(0)
        i = i + 1
    dates.reverse()
    scores.reverse()
    datesLabels.reverse()
    idx = np.asarray([i for i in range(7)])
    fig, ax = plt.subplots(figsize = (8,4))
    ax.bar(x=dates, height=scores, tick_label = tuple(datesLabels))
    plt.ylim([0, 100])
    plt.bar(x=dates, height = scores)
    plt.ylabel("Balance Score (/100)")
    fig.tight_layout()
    plt.savefig(histImagePath)
    
    lock.acquire()
    imgHis = ImageTk.PhotoImage(Image.open(histImagePath))
    imageGraphHis = Image.open(histImagePath)
    imgGraphHis= ImageTk.PhotoImage(imageGraphHis)
    imgGraphlblHis = tkinter.Label(image=imgGraphHis)
    imgGraphlblHis.place(x = 15, y = 80)
    lock.release()

# Display home page
def onHomeSelected():
    global threadsList
    lock.acquire()
    clear_gui()
    lbl.configure(text="Home")
    lbl.place(x=20, y = 20)
    b1.grid(row = 10, column = 5)
    b2.grid(row = 10, column = 15)
    b3.grid(row = 10, column = 25)
    b4.place(x = 300, y=300)
    bHome.grid(row = 60, column = 5)
    restartThread=threading.Thread(target=restartingThread)
    threadsList.append(restartThread)
    lock.release()
    restartingThread.daemon = True
    restartThread.start()
        
# Restart the device
def restartingThread():
    
    try:
        va_obj = gTTS(text="ConnectionTest", slow=False)
        va_obj.save("testConn.mp3")
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/deviceOmar",payload="RESTART")
    except:
        lock.acquire()
        lbl.configure(text="Connection error, please ensure that your PC is connected to the internet.")
        lock.release()
        time.sleep(4)
        on_closing()
    


# Display client connection and workout selection process
def interactiveThreadMain():
    global client
    global bigFont

    client = mqtt.Client()
    client.on_message = on_message
    try:
        RETURN_CODE = client.connect("test.mosquitto.org",port=1883)
        client.loop_start()
        client.subscribe("IC.embedded/AOOEmbed/appOmar", qos=2)
    except:
        lock.acquire()
        lbl.configure(text="Connection error, please ensure that your PC is connected to the internet.")
        lock.release()
        time.sleep(4)
        on_closing()
    while(notConnected()):
        spin()
    
    lock.acquire()
    #print("Connection Successful! choose workout")
    lbl.configure(text = "Connection Successful! Choose workout")
    b1['font'] = bigFont
    b2['font'] = bigFont
    b3['font'] = bigFont
    b4['font'] = bigFont

    bHome['font'] = bigFont
    b1.grid(row = 10, column = 5)
    b2.grid(row = 10, column = 15)
    b3.grid(row = 10, column = 25)
    b4.place(x = 300, y = 300)
    bHome.grid(row = 60, column = 5)
    b1.configure(command=onWorkoutOneSelected)
    b2.configure(command=onWorkoutTwoSelected)
    b3.configure(command=onWorkoutThreeSelected)
    b4.configure(command=onWorkoutHistorySelected)
    bHome.configure(command=onHomeSelected, bg='#3940AD', fg='white')
    lock.release()

# Main, nothing to lock and unlock here, one thread is spawned by this and that only happens at the end 

connected = False
dataReceived = False
calibrated = False
continuation = 1
workoutType = 0
workoutDuration = 10
workoutDone = False
window = tkinter.Tk()

rows = 0
while rows < 50:
    window.rowconfigure(rows, weight=1)
    window.columnconfigure(rows,weight=1)
    rows += 1
window.configure(background = "#FFF9F3")
bigFont = font.Font(size=30)
window.title("YogiTrainer")
window.geometry('900x900')
lbl = tkinter.Label(window, text="Connecting...")
lbl['font']=bigFont
lbl.place(x=20, y = 20)
lbl.configure(background = "#FFF9F3")
b1 = tkinter.Button(window, text="Lotus")
b2 = tkinter.Button(window, text="Rose")
b3 = tkinter.Button(window, text="Chrysanthemum")
b4 = tkinter.Button(window, text = "View Workout History")
b5 = tkinter.Button(window, text="Lotus")
b6 = tkinter.Button(window, text="Rose")
b7 = tkinter.Button(window, text="Chrysanthemum")
bHome = tkinter.Button(window, text = "Home")
logs = shelve.open("logs", writeback=True)

def on_closing():
    MSG_INFO = client.publish("IC.embedded/AOOEmbed/deviceOmar",payload="RESTART")
    client.loop_stop()
    logs.close()
    window.destroy()
    #threads are daemon threads so are abruptly halted on exit, however, all resources are release before that is done
    
    

window.protocol("WM_DELETE_WINDOW", on_closing)
threadsList = []
interactiveThread=threading.Thread(target=interactiveThreadMain)
threadsList.append(interactiveThread)
interactiveThread.daemon = True
interactiveThread.start()

window.mainloop()
