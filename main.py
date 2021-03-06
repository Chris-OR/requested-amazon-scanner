import requests
from proxy_requests import ProxyRequests
from bs4 import BeautifulSoup
import time
import telegram
import threading
import os
from flask import Flask
import json
from parsel import Selector

URL_LIST = ["https://www.amazon.com/Dyson-343783-01-Cyclone-Cord-Free-Cleaner/dp/B08QHLPXMS/ref=sr_1_32?m=A2L77EE7U53NWQ&qid=1645223842&refresh=1&rnid=10158976011&s=warehouse-deals&sr=1-32",
            "https://www.amazon.com/Dyson-Cyclone-Absolute-Lightweight-Cordless/dp/B0798FVV6V/ref=sr_1_2?keywords=Dyson&m=A2L77EE7U53NWQ&qid=1644714367&s=warehouse-deals&sr=8-2",
            "https://www.amazon.com/Dyson-Animal-Cordless-Vacuum-Cleaner/dp/B079K9B4XV/ref=sr_1_3?keywords=Dyson&m=A2L77EE7U53NWQ&qid=1644714367&s=warehouse-deals&sr=8-3",
            "https://www.amazon.com/Dyson-Cyclone-Absolute-Lightweight-Cordless/dp/B0798FVV6V/ref=sr_1_20?m=A2L77EE7U53NWQ&qid=1644862049&rnid=10158976011&s=warehouse-deals&sr=1-20",
            "https://www.amazon.com/Dyson-Animal-Cordless-Vacuum-Cleaner/dp/B079K9B4XV/ref=sr_1_15?m=A2L77EE7U53NWQ&qid=1644862049&rnid=10158976011&s=warehouse-deals&sr=1-15"
            ]

in_stock = []

proxy_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
    "Accept-Encoding": "gzip,deflate,br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "close",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://www.google.com/",
}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")


def get_webpage_with_proxy(url):
    print(f"Trying to load Amazon page...")
    searching = True
    while searching:
        r = ProxyRequests("https://www.google.com/")
        r.set_headers(proxy_headers)
        r.get_with_headers()
        # print(r.get_status_code())
        proxy = r.get_proxy_used()
        # print(proxy)

        proxy = {
            "http": f"http://{proxy}",
            "https": f"https://{proxy}",
        }

        try:
            response = requests.get(url, headers=proxy_headers, proxies=proxy)
            response.raise_for_status()
            searching = False
            return response
        except Exception as e:
            print(e)
            print("something went wrong")

    # webpage = response.text
    # webpage_soup = BeautifulSoup(webpage, "html.parser")
    # handle_webpage(webpage_soup)
#     # print(webpage_soup)
#
#
# def checker_thread():
#     print("Starting...")
#     while True:
#         for URL in URL_LIST:
#             get_webpage(URL)
#             time.sleep(75)
#
#


def handle_webpage(soup, url):
    captcha_catcher = soup.find(name="p", class_="a-last")
    captcha = False

    if captcha_catcher is not None:
        print("caught a captcha - we will move on")
        captcha = True

    if not captcha:
        print("Successfully retrieved webpage")
        title = soup.find(id="productTitle").getText().rstrip().lstrip()
        # price = soup.find(id="buyNew_noncbb").getText()
        # print(price)
        # if title:
        #     print(title)
        try:
            price = soup.find(id="buyNew_noncbb").getText().rstrip().lstrip()
            print(f"{title} is {price}")
            if title not in in_stock:
                send_telegram_message(title, price, url)
                in_stock.append(title)
        except:
            print(f"{title} is unavailable")
            if title in in_stock:
                in_stock.remove(title)
    print("\n")




AMAZON_US_URL = "https://www.amazon.com/"
AMAZON_ADDRESS_CHANGE_URL = (
    "https://www.amazon.com/gp/delivery/ajax/address-change.html"
)
AMAZON_CSRF_TOKEN_URL = (
    "https://www.amazon.com/gp/glow/get-address-selections.html?deviceType=desktop"
    "&pageType=Gateway&storeContext=NoStoreName&actionSource=desktop-modal"
)
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 ..."
)
DEFAULT_REQUEST_HEADERS = {"Accept-Language": "en", "User-Agent": DEFAULT_USER_AGENT}


def get_amazon_content(start_url: str, cookies: dict = None) -> tuple:
    response = requests.get(
        url=start_url, headers=DEFAULT_REQUEST_HEADERS, cookies=cookies
    )
    response.raise_for_status()
    return Selector(text=response.text), response.cookies


def get_ajax_token(content: Selector):
    data = content.xpath(
        "//span[@id='nav-global-location-data-modal-action']/@data-a-modal"
    ).get()
    if not data:
        raise ValueError("Invalid page content")
    json_data = json.loads(data)
    return json_data["ajaxHeaders"]["anti-csrftoken-a2z"]


def get_session_id(content: Selector):
    session_id = content.re_first(r'session: \{id: "(.+?)"')
    if not session_id:
        raise ValueError("Session id not found")
    return session_id


def get_token(content: Selector):
    csrf_token = content.re_first(r'CSRF_TOKEN : "(.+?)"')
    if not csrf_token:
        raise ValueError("CSRF token not found")
    return csrf_token


def send_change_location_request(zip_code: str, headers: dict, cookies: dict):
    response = requests.post(
        url=AMAZON_ADDRESS_CHANGE_URL,
        data={
            "locationType": "LOCATION_INPUT",
            "zipCode": zip_code,
            "storeContext": "generic",
            "deviceType": "web",
            "pageType": "Gateway",
            "actionSource": "glow",
            "almBrandId": "undefined",
        },
        headers=headers,
        cookies=cookies,
    )
    assert response.json()["isValidAddress"], "Invalid change response"
    return response.cookies


def get_session_cookies(zip_code: str):
    while True:
        for URL in URL_LIST:
            try:
                # response = requests.get(url=AMAZON_US_URL, headers=DEFAULT_REQUEST_HEADERS)
                response = get_webpage_with_proxy(url=AMAZON_US_URL)
                content = Selector(text=response.text)
                webpage1 = response.text
                webpage_soup = BeautifulSoup(webpage1, "html.parser")
                if webpage_soup.find(name="p", class_="a-last"):
                    print("caught a captcha when changing location")
                headers = {
                    "anti-csrftoken-a2z": get_ajax_token(content=content),
                    "user-agent": DEFAULT_USER_AGENT,
                }
                response = requests.get(
                    url=AMAZON_CSRF_TOKEN_URL, headers=headers, cookies=response.cookies
                )
                content = Selector(text=response.text)

                headers = {
                    "anti-csrftoken-a2z": get_token(content=content),
                    "user-agent": DEFAULT_USER_AGENT,
                }
                send_change_location_request(
                    zip_code=zip_code, headers=headers, cookies=dict(response.cookies)
                )
                # Verify that location changed correctly.
                response = requests.get(
                    url=URL, headers=DEFAULT_REQUEST_HEADERS, cookies=response.cookies
                )
                content = Selector(text=response.text)
                webpage = response.text

                webpage_soup = BeautifulSoup(webpage, "html.parser")
                handle_webpage(webpage_soup, URL)

                location_label = content.css("span#glow-ingress-line2::text").get().strip()
                assert zip_code in location_label

                time.sleep(75)
            except ValueError as e:
                print("ran into error when changing server location... trying again")
                print(e)
                time.sleep(75)


def send_telegram_message(title, price, URL):
    bot_token = os.environ.get("BOT_TOKEN")
    bot = telegram.Bot(bot_token)
    chat_id = os.environ.get("VACUUM_CHAT_ID")
    chat_id2 = os.environ.get("VACUUM_CHAT_ID2")
    message = f"{title} is {price}.  Check it out: {URL}"
    bot.sendMessage(chat_id, message, parse_mode=telegram.ParseMode.HTML)
    bot.sendMessage(chat_id2, message, parse_mode=telegram.ParseMode.HTML)


def start_app():
    print("Starting Scan...")
    get_session_cookies(zip_code=os.environ.get("ZIP_CODE"))


print("App Loaded...")
threading.Thread(target=start_app, daemon=True).start()

@app.route('/')
def home():
    return("hello")

if __name__ == "__main__":
    app.run(debug=False)
