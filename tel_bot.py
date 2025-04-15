#
# Date : 20/12/2024
#
# Assignment : IoT Assignment (CSM3313)
# Group 18
# Name : 1.MUHAMMAD AFIQ FAHMIE BIN AMRI (S67158)
#        2.TUAN MOHAMAD FIRDAUS BIN TUAN ROSDI (S65650)
#        3.AMMAR SYARIFUDDIN BIN MOHD ZUKRI (S66115)
#
# Project Name : MySmart Feeder
# Description : A project where we can feed the cat by using the telegram bot in our phone.
#
# Telegram Bot Link : https://t.me/MySmartFeederBot
#
# This is the code for communication to the Favoriot MQTT broker and the telegram bot. The process were ,
# 1. The telegram bot will connect to the MQTT broker and listen for food level updates from the Favoriot device.
# 2. The telegram bot will respond to commands such as /start, /feed, and /foodlevel.
# 3. The telegram bot will publish commands to the MQTT broker to control the motor and check the food level.
# 4. The telegram bot will display messages and photos based on the food level status.
# 5. The telegram bot will send messages to the user via Telegram.
# 6. The telegram bot will send photos to the user via Telegram.
# The system act as a bridge between the MQTT broker and the telegram bot or can called as local server.



import time

#Import MQTT library
import paho.mqtt.client as mqtt

#Import telegram library to create a bot and handle commands
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Favoriot MQTT Configuration
MQTT_BROKER = "mqtt.favoriot.com"
MQTT_USER = "afQI0FOKCBEvmdgGfDb2JqC6UnNOc6GM"
MQTT_PASS = "afQI0FOKCBEvmdgGfDb2JqC6UnNOc6GM"
DEVICE_ID = "ESP32@afiqamri03"

# Will pass the data using this endpoint
TOPIC = f"{MQTT_USER}/v2/streams"

food_level = None  # To store the food level

# MQTT message callback to receive food level and display to the user via telegram bot.
def mqtt_callback(client, userdata, message):
    global food_level
    print(f"Received message on topic {message.topic}: {message.payload}")
    if b'"food_level"' in message.payload:
        try:
            # Extract food level from payload
            payload_str = message.payload.decode("utf-8")
            food_level = payload_str.split('"food_level":')[1].split("}")[0]
            print(f"Food level updated: {food_level} cm")
        except Exception as e:
            print(f"Error processing food level: {e}")

# Function to publish messages to MQTT Server or Favoriot Datastreams
def publish_mqtt(command):
    try:
        client = mqtt.Client()
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.connect(MQTT_BROKER, 1883, 60)
        payload = f'{{"device_developer_id": "{DEVICE_ID}", "data": {{"command": "{command}"}}}}'
        client.publish(TOPIC, payload)
        client.disconnect()
        return True
    except Exception as e:
        print(f"Error publishing to MQTT: {e}")
        return False

# Telegram bot command handlers
# Command to start the bot
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    # Send welcome message for User
    await update.message.reply_text("Welcome to MySmart Feeder! Use /feed to feed your cats. Use /foodlevel to check the food level.")
    await update.message.reply_photo(open("pictures/cat.png", "rb"))

# Command to feed the cat
async def feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    
    # Send message to Favoriot when user clicks /feed on the bot
    if publish_mqtt("activate_motor"):
        # Send message to user if the command is successfully sent
        await update.message.reply_text("Feeds your cat is successful!")
        await update.message.reply_photo(open("pictures/thankyouCat.png", "rb"))
    else:
        # Send message to user if the command is not successfully sent
        await update.message.reply_text("Failed to send command to Favoriot.")

# Command to check the food level
async def foodlevel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global food_level
    # Send message to Favoriot when user clicks /foodlevel on the bot
    if publish_mqtt("check_food_level"):
        # Send message to user if the command is successfully sent and begin to check the food level
        await update.message.reply_text("Checking food level... Please wait a moment.")
        # Allow some time for MQTT to process and update the food level
        time.sleep(3)
        # Check if the food level is available
        if food_level is not None:
            # Tell if the food level is low or else
            #1st condition : Food level is full or enough..
            if  float(food_level) < 8:
                # Send message to user if the food level is full and enough
                await update.message.reply_text("Food is enough for your cat for couple of days! Feed your cat now ! Use /feed . ")
                await update.message.reply_text(f"The current food level is {food_level} cm.")
                await update.message.reply_photo(open("pictures/cat_tq.png", "rb"))
                return

            #2nd condition : Give warning which food level is almost out..
            if  8 <= float(food_level) < 12:
                # Send message to user if the food level is almost out
                await update.message.reply_text("Food is almost out for your cat! You better feed now! Use /feed to feed your cats now!.")
                await update.message.reply_text(f"The current food level is {food_level} cm.")
                await update.message.reply_photo(open("pictures/cat_middle.png", "rb"))
                
            #3nd condition : Warning , food level is very loww
            if  float(food_level) >= 12:
                # Send message to user if the food level is very low
                await update.message.reply_text("Food is very low for your cat! You better feed now! Use /feed to feed your cats now!")
                await update.message.reply_text(f"The current food level is {food_level} cm.")
                await update.message.reply_photo(open("pictures/cat_angry.png", "rb"))
        # If the food level is not available
        else:
            await update.message.reply_text("Unable to retrieve the food level. Please try again later.")
    # Send message to user if the command is not successfully sent
    else:
        await update.message.reply_text("Failed to send command to Favoriot.")

# Main function to run the bot
def main():
    # Telegram bot token
    application = ApplicationBuilder().token("7754717211:AAH-gc_6JKQXsxxPGZPrpuxGPCq0siCnGmc").build()

    # Add command handlers to the bot
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("feed", feed))
    application.add_handler(CommandHandler("foodlevel", foodlevel))

    # Set up MQTT client for the bot to listen for messages
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.connect(MQTT_BROKER, 1883, 60)

    # Configure MQTT callback
    mqtt_client.on_message = mqtt_callback
    mqtt_client.subscribe(TOPIC)
    print("Subscribed to topic for food level updates.")

    # Start the bot and MQTT client loop
    mqtt_client.loop_start()
    application.run_polling()

# Run the bot
if __name__ == "__main__":
    main()


