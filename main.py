import ccxt
import json
from flask import Flask, request
from telegram import Update, Bot
import logging
import config

app = Flask(__name__)

logging.basicConfig(filename="log_file.log", level=logging.DEBUG, format='%(asctime)s %(message)s', filemode='w')
logger = logging.getLogger()


def get_balance(exchange, quote_currency):
    balance = exchange.fetch_balance()
    return balance["free"][quote_currency]


def get_taker_fee(exchange, symbol):
    markets = exchange.load_markets()
    return markets[symbol]["taker"]


def send_telegram_message(bot, telegram_chat_id, message):
    bot.send_message(chat_id=telegram_chat_id, text=message)


def get_minimum_trade_amount(symbol):
    exchange = ccxt.binance()
    markets = exchange.load_markets()
    market = markets[symbol]
    return market['limits']['amount']['min']


@app.route("/webhook", methods=["POST"])
def webhook():
    data = json.loads(request.data)
    logger.info(data)
    # Telegram API anahtarınızı buraya girin
    telegram_api_key = data["bottoken"]
    telegram_chat_id = data["chatid"]

    bot = Bot(token=telegram_api_key)

    if data['passphrase'] != config.PASSPHRASE:
        send_telegram_message(bot, telegram_chat_id, "Login attempt: Invalid passphrase")
        logger.warning("Login attempt: Invalid passphrase")
        return {
            "code": "failure",
            "message": "Incorrect passphrase"
        }
    action = data["action"]
    symbol = data["symbol"]

    # Binance API anahtarlarınızı buraya girin
    api_key = data["apikey"]
    api_secret = data["apisecret"]

    # Binance hesabınıza bağlanın
    exchange = ccxt.binance({
        "apiKey": api_key,
        "secret": api_secret,
    })
    exchange.set_sandbox_mode(True)

    # Telegram botunu başlatın

    base_currency, quote_currency = symbol.split("/")
    try:
        if action == "buy":
            balance = get_balance(exchange, quote_currency)
            taker_fee = get_taker_fee(exchange, symbol)
            amount = balance / exchange.fetch_ticker(symbol)["ask"] * (1 - taker_fee)
            minimum_amount = get_minimum_trade_amount(symbol)
            if amount > minimum_amount:
                order = exchange.create_market_buy_order(symbol, amount)
                logger.info(order)
                message = f"Alım işlemi gerçekleştirildi: {order['amount']} {symbol} fiyatı {order['price']}"
            else:
                message = f"Yeterli fiyat bulunamadığından Alım işlemi gerçekleştirilemedi {amount}"
        elif action == "sell":
            balance = get_balance(exchange, base_currency)
            taker_fee = get_taker_fee(exchange, symbol)
            amount = balance * (1 - taker_fee)
            minimum_amount = get_minimum_trade_amount(symbol)
            if amount > minimum_amount:
                order = exchange.create_market_sell_order(symbol, amount)
                logger.info(order)
                message = f"Satım işlemi gerçekleştirildi: {order['amount']} {symbol} fiyatı {order['price']}"
            else:
                message = f"Yeterli fiyat bulunamadığından Alım işlemi gerçekleştirilemedi {amount}"
        else:
            return "Invalid action", 400
    except Exception as e:
        logger.error(e)
        send_telegram_message(bot, telegram_chat_id, f"Error: {e}")
        return {
            'code': 'Failure',
            'message': 'Error occurred while evaluating position and initiating trade'
        }, 500

    send_telegram_message(bot, telegram_chat_id, message)
    return {
        'code': 'Success',
        'message': 'Trade executed successfully'
    }, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
