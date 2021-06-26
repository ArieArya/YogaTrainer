import ssl
import paho.mqtt.client as mqtt
import numpy as np
import time
import smbus2
import json
import math
import RPi.GPIO as GPIO
from math import copysign
from threading import Lock
lock = Lock()

received = False
workoutComplete = False
workoutType = 0
restart = False
bus = None 
ACCEL_ADRESS = 0x18 #accelerometer's I2C adress
ideal_pos_dict = {
                1: [0, -60, 60], # position one around -60 degrees yaxis (pi facing away from me) # (x axis the wooble horizontally)
                2: [0, -25,25], # position two around -25 degrees maybe add challenge difficulty (xaxis is the horizontal wobble)
                3: [1,1,1] # anything between -5 plus 5 on the y axis and x axis is zero
            }

# Handle incoming MQTT Publish Messages
def on_message(client, userdata, message):
    messageString = message.payload.decode('utf-8')
    global received
    global workoutComplete
    global workoutType
    global restart
    if(messageString == "ACK"):
        lock.acquire()
        received = True
        lock.release()
    elif(messageString == "WORKOUT_COMPLETE"):
        lock.acquire()
        workoutComplete = True
        lock.release()
    elif(messageString == "RESTART"):
        print("Got a restart")
        lock.acquire()
        restart = True
        lock.release()
    else:
        print("Assigning workout type")
        lock.acquire()
        workoutType = int(messageString)
        lock.release()
        
# Set up I2C sensor registers
def setup_sensor():
    global bus
    global ACCEL_ADRESS
    bus = smbus2.SMBus(1)
    bus.write_byte_data(ACCEL_ADRESS,0x1E,0x90)
    bus.write_byte_data(ACCEL_ADRESS,0x20,0x77) # 0x77 sets the system to normal mode at 400 hz
    bus.write_byte_data(ACCEL_ADRESS,0x23,0x88) # set config bits //make this parametizeable!!
    bus.write_byte_data(ACCEL_ADRESS,0x21,0x3)
    bus.write_byte_data(ACCEL_ADRESS,0x38,0x10)
    bus.write_byte_data(ACCEL_ADRESS,0x22,0x80)


# Calculate rotation angles (i.e. Polar Co-ordinates) from Cartesian Co-ordinate 
def angle_calculator(x,y,z):
    sign = lambda a: copysign(1,a)  
    u = 0.01
    pitch = np.arctan2(y,sign(z)*np.sqrt(np.power(z,2)+(u*np.power(x,2)))) 
    roll = np.arctan2((-x),(np.sqrt(np.power(y,2) + np.power(z,2)))) 
    yaw = np.arctan2(np.sqrt(np.power(x,2)+np.power(y,2)),z) 
    return np.rad2deg(pitch),np.rad2deg(roll),np.rad2deg(yaw)


# Perform Low-Pass-Filter Averaging of Angles
prev_data = [0,0,0]
prev_result = [0,0,0]
def LPF_averaging(xangle,yangle,zangle):
    global prev_data
    global prev_result
    a=0.45 # set cutoff and weight
    pitch = (1-a)*prev_result[0] + a*((xangle+prev_data[0])/2)
    roll = (1-a)*prev_result[1] + a*((yangle+prev_data[1])/2)
    yaw = (1-a)*prev_result[2] + a*((zangle+prev_data[2])/2)
    prev_result[0] = pitch
    prev_result[1] = roll
    prev_result[2] = yaw
    prev_data[0] = xangle
    prev_data[1] = yangle
    prev_data[2] = zangle
    return pitch, roll, yaw


# Read data from Accelerometer
def accel_read():
    global ACCEL_ADRESS#not accessed by other threads
    STATUS_REG =  bus.read_byte_data(0x18, 0x27)
    if(((STATUS_REG>>(3)) & 0x1) != 0):
        OUT_X_L = bus.read_byte_data(ACCEL_ADRESS, 0x28)
        OUT_X_H = bus.read_byte_data(ACCEL_ADRESS, 0x29)
        OUT_Y_L = bus.read_byte_data(ACCEL_ADRESS, 0x2a)
        OUT_Y_H = bus.read_byte_data(ACCEL_ADRESS, 0x2b)
        OUT_Z_L = bus.read_byte_data(ACCEL_ADRESS, 0x2c)
        OUT_Z_H = bus.read_byte_data(ACCEL_ADRESS, 0x2d)
        
        # constructing the three force components from the low (L) and high (H) registers
        x = (OUT_X_H<<8) | OUT_X_L
        y = (OUT_Y_H<<8) | OUT_Y_L
        z = (OUT_Z_H<<8) | OUT_Z_L 
        total_size = 2**15
        maxacc =  2      
        x = maxacc * (np.int16(x)/total_size)
        y = maxacc * (np.int16(y)/total_size)
        z = maxacc * (np.int16(z)/total_size)
        return np.float16(x), np.float16(y), np.float16(z)
    else:
        return 0,0,0

# Calibrate user position
def calibrate_user():
    calibration_completed = False
    global moveforward
    global prev_data
    global prev_result
    cal_start_time = time.time()
    va_start_time = time.time()
    
    # obtain ideal position from workout
    ideal_pos = ideal_pos_dict[workoutType]
    print(workoutType)
    ideal_x = ideal_pos[0]
    ideal_y = ideal_pos[1]
    ideal_z = ideal_pos[2]

    while not calibration_completed:
        cur_time = time.time()
        
        # obtain current user position
        x, y, z = accel_read()
        x_angle, y_angle, z_angle  = angle_calculator(x,y,z)
        pitch , roll, yaw = LPF_averaging(x_angle,y_angle,z_angle)
        position_info = ["NEW_POSITION_INFO", [float(pitch), float(roll), float(yaw),moveforward], ideal_pos,]
        LED_feedback(pitch,roll,yaw)   
        
        # restart calibration timer if ideal position not met
        if abs(roll - ideal_y) >= 5 or abs(yaw - ideal_z) >= 5:
            cal_start_time = time.time()
        
        # complete calibration if timer passed
        if cur_time - cal_start_time > 5:
            prev_data = [0,0,0]
            prev_result = [0,0,0]
            calibration_completed = True
            break
            
        # send new message every 5 seconds to obtain live feedback during calibration
        if cur_time - va_start_time > 5:
            MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=json.dumps(position_info))
            cur_time = time.time()
            va_start_time = time.time()

        time.sleep(0.1)
    return 
    
# Idle function
def spin():
    return 1


# Obtain average position from an array of positions
def average_pos(inp_coord):
    n = len(inp_coord)
    avg_x = 0
    avg_y = 0
    avg_z = 0
    for i in range(len(inp_coord)):
        avg_x += inp_coord[i][0]
        avg_y += inp_coord[i][1]
        avg_z += inp_coord[i][2]

    return [avg_x/n, avg_y/n, avg_z/n]


# GPIO setup for interrupts
button_1 = 17
LED_RED = 23
LED_GREEN = 27
LED_BLUE = 22
def setup_gpio():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(button_1,GPIO.IN,pull_up_down=GPIO.PUD_UP)
    GPIO.setup(LED_RED,GPIO.OUT)
    GPIO.setup(LED_GREEN,GPIO.OUT)
    GPIO.setup(LED_BLUE,GPIO.OUT)


# Device LED Feedback
def LED_feedback(pitch,roll,yaw):
    ideal_x = ideal_pos_dict[workoutType][0]
    ideal_y = ideal_pos_dict[workoutType][1]
    ideal_z = ideal_pos_dict[workoutType][2]
    if workoutType == 1 and moveforward == 1:
        if abs(roll-ideal_y) >= 5 or abs(pitch-ideal_x) >= 5 or abs(yaw-ideal_z) >= 5:
            GPIO.output(LED_RED,GPIO.LOW)
            GPIO.output(LED_GREEN,GPIO.HIGH)
            GPIO.output(LED_BLUE,GPIO.HIGH)
        else:
            GPIO.output(LED_RED,GPIO.HIGH)
            GPIO.output(LED_GREEN,GPIO.LOW)
            GPIO.output(LED_BLUE,GPIO.HIGH)
    elif workoutType == 2 and moveforward == 1:
        if abs(roll-ideal_y) >= 5 or abs(pitch-ideal_x) >= 5 or abs(yaw-ideal_z) >= 5:
            GPIO.output(LED_RED,GPIO.LOW)
            GPIO.output(LED_GREEN,GPIO.HIGH)
            GPIO.output(LED_BLUE,GPIO.HIGH)
        else:
            GPIO.output(LED_RED,GPIO.HIGH)
            GPIO.output(LED_GREEN,GPIO.LOW)
            GPIO.output(LED_BLUE,GPIO.HIGH)
    elif workoutType == 3 and moveforward == 1:
        if abs(roll-ideal_y) >= 5 or abs(pitch-ideal_x) >= 5 or abs((yaw-ideal_z)) >= 5:
            GPIO.output(LED_RED,GPIO.LOW)
            GPIO.output(LED_GREEN,GPIO.HIGH)
            GPIO.output(LED_BLUE,GPIO.HIGH)
        else:
            GPIO.output(LED_RED,GPIO.HIGH)
            GPIO.output(LED_GREEN,GPIO.LOW)
            GPIO.output(LED_BLUE,GPIO.HIGH)
    else:
        GPIO.output(LED_RED,GPIO.HIGH)
        GPIO.output(LED_GREEN,GPIO.LOW)
        GPIO.output(LED_BLUE,GPIO.HIGH)

def LED_turnoff():
    GPIO.output(LED_RED,GPIO.HIGH)
    GPIO.output(LED_GREEN,GPIO.HIGH)
    GPIO.output(LED_BLUE,GPIO.HIGH)

# Interrupt Callbacks
button1_count = 0
moveforward = 1
def button1_interrupt(channel):
    global button1_count#this variable is only accessed by 1 thread so no need to mutex
    global moveforward
    global ideal_pos_dict
    global workoutType
    lock.acquire()
    workoutTypelocal = workoutType
    lock.release()
    lock.acquire()
    ideal_pos = ideal_pos_dict[workoutTypelocal]
    lock.release()
    # stop condition
    if button1_count % 2 == 0:
        lock.acquire()
        moveforward = 0
        lock.release()
        position_info = ["NEW_POSITION_INFO", [0,0,0,0], ideal_pos]
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=json.dumps(position_info))
        button1_count += 1 
    # continue condition
    else:
        lock.acquire()
        moveforward = 1
        lock.release()
        position_info = ["NEW_POSITION_INFO", [0, 0, 0,1], ideal_pos]
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=json.dumps(position_info))
        button1_count += 1 
    # non stop condition
    

    

# Helper function for compress_list
def findNextIndex(inp_list, start_index):
    counter = 0
    cur_value = inp_list[start_index]
    for i in range(start_index, len(inp_list)):
        if inp_list[i] != cur_value:
            return i
    return len(inp_list) - 1
    
# Compresses list before MQTT publish
def compress_list(deviations):
    rounded_list = []
    compressed_list = []
    
    for deviation in deviations:
        rounded_list.append(int(math.floor(deviation/10.0)) * 10)
    
    idx = 0
    while idx < len(rounded_list):
        cur_value = rounded_list[idx]
        next_idx = findNextIndex(rounded_list, idx)
        compressed_list.append([cur_value, next_idx - idx])
        idx = next_idx + 1
    print(compressed_list)
    return compressed_list

def notWorkoutComplete():
    global workoutComplete
    lock.acquire()
    workoutCompleteLocal = workoutComplete
    lock.release()
    return (not workoutCompleteLocal)

def notRestart():
    global restart
    lock.acquire()
    restartLocal = restart
    lock.release()
    return (not restart)

def notReceived():
    global received
    lock.acquire()
    receivedLocal = received
    lock.release()
    return (not received)

def moveforwardSet():
    global moveforward
    lock.acquire()
    moveforwardLocal = moveforward
    lock.release()
    return (moveforwardLocal)

# Setup MQTT client 
client = mqtt.Client()
client.on_message = on_message
client.tls_set(ca_certs="mosquitto.org.crt",certfile="client.crt",keyfile="client.key",tls_version=ssl.PROTOCOL_TLSv1_2)
RETURN_CODE = client.connect("test.mosquitto.org",port=8884)
client.loop_start()
client.subscribe("IC.embedded/AOOEmbed/deviceOmar", qos=2)
setup_gpio()

# setup interrupts, for button released
GPIO.add_event_detect(button_1,GPIO.RISING,callback=button1_interrupt,bouncetime=100)
while(True):
    while(notReceived()):
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=("AWAITING_INPUT"))
        time.sleep(1)
    print("Connection successful")
    lock.acquire()
    received = False
    lock.release()
    # setup sensor
    setup_sensor()

    # Calibrate the user
    lock.acquire()
    restart = False
    lock.release()
    calibrate_user()
    prev_data = [0,0,0]
    prev_result = [0,0,0]
    print("calibration complete")
    MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=("CALIBRATED"))
    while(notReceived() and notRestart()):
        spin()
    lock.acquire()
    received = False
    lock.release()

    # Define ideal workout position
    ideal_pos = ideal_pos_dict[workoutType]
    start_time = time.time()
    coord_list = []
    deviations = []
    print("Got here with restart " + str(restart))
    # Loop during workout
    while(notWorkoutComplete() and notRestart()):
        
        if moveforwardSet() == 1:
            #print("resume")
            x, y, z = accel_read()
            x_angle, y_angle, z_angle = angle_calculator(x,y,z)
            pitch , roll, yaw = LPF_averaging(x_angle,y_angle,z_angle)
            LED_feedback(pitch,roll,yaw)
            coord_list.append([pitch, roll, yaw])
            position_info = ["NEW_POSITION_INFO", [float(pitch), float(roll), float(z),int(moveforward)], ideal_pos] # json does not accept numpy types

            # calculate deviation based on Euclidean difference
            deviations.append(math.sqrt((pitch-ideal_pos[0])**2 + (roll-ideal_pos[1])**2 + (yaw-ideal_pos[2])**2))
            time.sleep(0.1)

            # send new message every 5 seconds for feedback
            cur_time = time.time()
            if cur_time - start_time > 5:
                MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=json.dumps(position_info))
                cur_time = time.time()
                start_time = time.time()
        
        # Workout Paused
        else:
            #print("paused")
            position_info = ["NEW_POSITION_INFO",[0,0,0,moveforward],ideal_pos] 
            cur_time=time.time()
            if cur_time - start_time > 5:
                MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=json.dumps(position_info))
                cur_time = time.time()
                start_time = time.time()

    if (notRestart()):
        # Reset workout complete to False
        workoutComplete = False

        

        # Obtain compressed data before MQTT publish
        compressed_deviations = compress_list(deviations)
        average_coord = average_pos(coord_list)
        pld = json.dumps([compressed_deviations, average_coord, ideal_pos]) 
        MSG_INFO = client.publish("IC.embedded/AOOEmbed/appOmar",payload=pld)
    LED_turnoff()
    while(notRestart()):
        spin()
    restart = False
    lock.acquire()
    moveforward = 1
    lock.release()

client.loop_stop()