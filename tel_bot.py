"""
MySmart Feeder Telegram/MQTT bridge.

Configuration is loaded from environment variables so credentials are never
stored in source control. Copy .env.example to .env and provide your own
values before running the application.
"""

import asyncio
import logging
import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

MQTT_BROKER = os.getenv("FAVORIOT_MQTT_BROKER", "mqtt.favoriot.com")
MQTT_PORT = int(os.getenv("FAVORIOT_MQTT_PORT", "1883"))
MQTT_USER = os.getenv("FAVORIOT_MQTT_USER")
MQTT_PASS = os.getenv("FAVORIOT_MQTT_PASS")
DEVICE_ID = os.getenv("FAVORIOT_DEVICE_ID")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

PICTURES_DIR = Path(__file__).resolve().parent / "pictures"
food_level = None


def validate_configuration() -> None:
    """Fail early when required runtime configuration is missing."""
    required = {
        "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
        "FAVORIOT_MQTT_USER": MQTT_USER,
        "FAVORIOT_MQTT_PASS": MQTT_PASS,
        "FAVORIOT_DEVICE_ID": DEVICE_ID,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): " + ", ".join(missing)
        )


def mqtt_topic() -> str:
    return f"{MQTT_USER}/v2/streams"


def mqtt_callback(client, userdata, message) -> None:
    """Receive food-level updates from Favoriot."""
    del client, userdata
    global food_level

    logger.info("Received MQTT message on topic %s", message.topic)

    if b'"food_level"' not in message.payload:
        return

    try:
        payload_str = message.payload.decode("utf-8")
        parsed = payload_str.split('"food_level":', 1)[1].split("}", 1)[0]
        food_level = parsed.strip().strip('", ')
        logger.info("Food level updated: %s cm", food_level)
    except (UnicodeDecodeError, IndexError, ValueError) as exc:
        logger.warning("Unable to parse food-level payload: %s", exc)


def publish_mqtt(command: str) -> bool:
    """Publish a feeder command to Favoriot."""
    try:
        client = mqtt.Client()
        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.connect(MQTT_BROKER, MQTT_PORT, 60)

        payload = (
            f'{{"device_developer_id": "{DEVICE_ID}", '
            f'"data": {{"command": "{command}"}}}}'
        )
        client.publish(mqtt_topic(), payload)
        client.disconnect()
        return True
    except Exception:
        logger.exception("Failed to publish MQTT command: %s", command)
        return False


async def send_photo(update: Update, filename: str) -> None:
    if update.message is None:
        return

    image_path = PICTURES_DIR / filename
    if not image_path.exists():
        logger.warning("Image not found: %s", image_path)
        return

    with image_path.open("rb") as photo:
        await update.message.reply_photo(photo)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is None:
        return

    await update.message.reply_text(
        "Welcome to MySmart Feeder! Use /feed to feed your cat or "
        "/foodlevel to check the current food level."
    )
    await send_photo(update, "cat.png")


async def feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is None:
        return

    if publish_mqtt("activate_motor"):
        await update.message.reply_text("Feeding command sent successfully.")
        await send_photo(update, "thankyouCat.png")
    else:
        await update.message.reply_text(
            "Unable to send the feeding command. Please try again later."
        )


async def foodlevel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    global food_level

    if update.message is None:
        return

    if not publish_mqtt("check_food_level"):
        await update.message.reply_text(
            "Unable to request the food level. Please try again later."
        )
        return

    await update.message.reply_text("Checking food level...")
    await asyncio.sleep(3)

    if food_level is None:
        await update.message.reply_text(
            "Unable to retrieve the food level. Please try again later."
        )
        return

    try:
        level = float(food_level)
    except ValueError:
        logger.warning("Invalid food-level value received: %s", food_level)
        await update.message.reply_text("Received an invalid food-level reading.")
        return

    await update.message.reply_text(f"The current food level is {level:g} cm.")

    if level < 8:
        await update.message.reply_text(
            "Food level is sufficient. You can use /feed when needed."
        )
        await send_photo(update, "cat_tq.png")
    elif level < 12:
        await update.message.reply_text(
            "Food is running low. Consider refilling the feeder soon."
        )
        await send_photo(update, "cat_middle.png")
    else:
        await update.message.reply_text(
            "Food level is very low. Please refill the feeder."
        )
        await send_photo(update, "cat_angry.png")


def main() -> None:
    validate_configuration()

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("feed", feed))
    application.add_handler(CommandHandler("foodlevel", foodlevel))

    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
    mqtt_client.on_message = mqtt_callback
    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.subscribe(mqtt_topic())
    mqtt_client.loop_start()

    logger.info("Subscribed to Favoriot stream topic.")
    application.run_polling()


if __name__ == "__main__":
    main()
