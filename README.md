# YogiTrainer

Please visit our official website <a href="http://ec2-18-134-229-185.eu-west-2.compute.amazonaws.com/"> here </a>.

Introducing YogiTrainer, a personal IoT Yoga instructor made to help you learn Yoga with the latest technology. Its real-time signal processing and live voice instructor allows for a powerful and disruptive solution to learning and practising Yoga during the time of the pandemic.

YogiTrainer is built using the Raspberry Pi Zero, and utilizes the Adafruit LIS3DH Accelerometer to perform motion tracking. The script device_main_merged.py can be run through the Pi via PuTTY, whilst the app_main_merged.py can be executed through your local machine. The main medium of communication between the Pi and your machine is through the MQTT publish and subscribe mechanism. Observe below the dependencies and instructions for this project.

### Installing Dependencies
```
pip install paho-mqtt
pip install numpy
pip install RPi.GPIO
pip install smbus2
pip install ssl
pip install matplotlib
pip install gTTS
pip install playsound
pip install DateTime
```

### Program Execution
```
python app_main_merged.py
python device_main_merged.py
```

## Project Description
Below shows the basic Raspberry Pi circuitry and setup to run the project.
<p align="center">
  <img src='/setup.jpeg' width="35%">
</p>

After running both script files on your local machine and the Pi, a connection will be established via MQTT. Once the devices are connected, you will be prompted to choose the workouts of your choice, or to view your past (historical) performance of any workouts you have attempted. 

<p align="center">
  <img src='/poseOne.png' width="20.25%">
  <img src='/poseTwo.png' width="28.25%">
  <img src='/poseThree.png' width="33%">
</p>

After successfully calibrating your device, you will attempt the workout with the assistance of a live voice instructor, guiding you to the correct pose and giving you a final feedback of your performance after the completion of the exercise. Your performance will be monitored and stored to track your overall progress.


### Advanced Features

In addition to the secure MQTT protocol for communication between your local machine and the Pi, a few advanced features are added to ensure accurate and efficient transfer of data from the sensors. The first involves the use of a Low Pass Filter (LPF) to filter high-frequency noise from the sensors through an <b>exponential moving average (EMA) filter</b>. As we sample from our accelerometers at a frequency of 10Hz, noisy data is first removed before compressed and sent via MQTT. The mathematical equation for the filter is shown below:

<i><strong>EMA<sub>t</sub> = (1-a) * EMA<sub>t-1</sub> + a * newData</strong></i>

After passing our sensor data through the LPF, it is compressed by rounding each result to the nearest tenth value. This will then be used to compress our final MQTT message to reduce the size of the sensor data array we are sending. To do this, we convert each consecutive data that are identical to a 2-tuple containing the data and the number of its consecutive occurences. For example, [1, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3] will be compressed as [(1, 5), (2, 3), (3, 8)]. This will then be decompressed by your local machine during the reception of this data.


### Live Audio Feedback
Using the gTTS and playSound package in Python, you will receive a live audio feedback of your overall performance throughout the practice session, as well as a final overall feedback. This live feedback will allow you to adjust your pose accordingly to meet the target pose.


### Tracking Past Performances
In addition to giving a final overall balance score for your yoga session, the device will track all past exercises locally. This will allow you to track your historical performance and observe the progress you have made on each exercise. In addition, this can be used as a feedback to see your areas of weakness and how to improve them. Below are charts which displays an example of your balance score and your historical performance.

<p align="center">
  <img src='/chrysHistory.png' width="49%">
  <img src='/graph.png' width="49%">
</p>

Find out more about our work in our <a href="http://ec2-18-134-229-185.eu-west-2.compute.amazonaws.com/"> official website </a>.
