import scrapy
import json
import re
from urllib.parse import urlparse
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.selector import Selector
from twisted.internet.error import DNSLookupError, TCPTimedOutError
from testBot.constants import SCRAPY_FAILURE_PROXY, SCRAPY_FAILURE_OTHERS, SCRAPY_FAILURE_HTML
from testBot.exceptions import ProxyFailureException, HTMLParsingException
from testBot.utils import Utils


class TestSpider(scrapy.Spider):
    name = "test_spider"
    config = None
    error_type = 0
    error_description = ""
    not_scraped_items = []
    not_scraped_items_optional = []
    hotel = {}
    utils = None

    def __init__(self, *args, **kwargs):
        super(TestSpider, self).__init__(*args, **kwargs)
        self.config = kwargs.get("config")
        self.config = json.loads(self.config)
        self.url = self.config["BotInfo"]["BaseUrl"]
        self.domain = urlparse(self.url).netloc
        self.start_urls = [self.url]
        self.allowed_domains = [self.domain]
        self.utils = Utils(self.config, {}, [], [])

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, errback=self.error_handler, dont_filter=True)

    def parse(self, response):
        try:
            cid = self.config["CrawlParams"]["checkInDate"].replace('/', '-')
            cod = self.config["CrawlParams"]["checkOutDate"].replace('/', '-')
            if True:
                search_url = self.config["BotInfo"]["BaseUrl"] + "/hotel/" + \
                             self.config["CrawlParams"]["propertyChainCode"] + ".en-gb.html?" + \
                             "checkin=" + cid + \
                             ";checkout=" + cod + \
                             ";dest_id=" + self.config["CrawlParams"]["cityCode"] + \
                             ";dest_type=city;dist=0" + ";selected_currency=" + self.config["CrawlParams"]["currency"]
                yield scrapy.Request(search_url, callback=self.parse_hotel, errback=self.error_handler)
        except ProxyFailureException as e:
            self.error_type = SCRAPY_FAILURE_PROXY
            self.error_description = str(e)
            yield {"error_type": self.error_type, "error_description": self.error_description, "data": self.hotel,
                   "not_scraped_items": self.not_scraped_items, "not_scraped_items_optional":
                       self.not_scraped_items_optional}
        except Exception as e:
            self.error_type = SCRAPY_FAILURE_OTHERS
            self.error_description = str(e)
            yield {"error_type": self.error_type, "error_description": self.error_description, "data": self.hotel,
                   "not_scraped_items": self.not_scraped_items, "not_scraped_items_optional":
                       self.not_scraped_items_optional}

    def parse_hotel(self, response):
        with open("response.html", "wb") as Response:
            Response.write(response.body)
        try:
            self.utils.get_hotel_details()
            selector = Selector(response)
            for tag in self.config["BotInfo"]["HtmlTags"]:
                if self.config["BotInfo"]["HtmlTags"][tag]["parent"] is None:
                    if tag == "hotelRoomsTableDivSelector":
                        self.utils.get_room_details(selector)
                    elif tag != "hotelDepthPriceDivSelector" and tag != "hotelDepthChargeDivSelector":
                        self.not_scraped_items = self.utils.not_scraped_items
                        self.not_scraped_items_optional = self.utils.not_scraped_items_optional
                        self.utils.hotel = self.utils.evaluate_tag(tag, selector, self.utils.hotel)
            self.hotel = self.utils.hotel
            if self.config["CrawlParams"]["depth"] == "1":
                for room in self.hotel["Rooms"]:
                    url = "https://secure.booking.com/book.html?"
                    cid = self.config["CrawlParams"]["checkInDate"].replace('/', '-')
                    url += "hotel_id=" + self.config["CrawlParams"]["propertyID"] + "&stage=1&checkin=" + cid + \
                           "&interval=" + self.config["CrawlParams"]["minimumLengthofStay"] + \
                           "&rt_num_rooms=1&nr_rooms_" + room["RoomId"] + "=1;selected_currency=" + \
                           self.config["CrawlParams"]["currency"]
                    yield scrapy.Request(url, callback=self.parse_details, meta={"Room": room},
                                         errback=self.error_handler, dont_filter=True)
            yield {"error_type": self.error_type, "error_description": self.error_description,
                   "data": self.hotel, "not_scraped_items": self.not_scraped_items,
                   "not_scraped_items_optional": self.not_scraped_items_optional}

        except HTMLParsingException as e:
            self.error_type = SCRAPY_FAILURE_HTML
            self.error_description = str(e)
            yield {"error_type": self.error_type, "error_description": self.error_description,
                   "data": self.hotel, "not_scraped_items": self.not_scraped_items,
                   "not_scraped_items_optional": self.not_scraped_items_optional}
        except Exception as e:
            self.error_type = SCRAPY_FAILURE_OTHERS
            self.error_description = str(e)
            yield {"error_type": self.error_type, "error_description": self.error_description,
                   "data": self.hotel, "not_scraped_items": self.not_scraped_items,
                   "not_scraped_items_optional": self.not_scraped_items_optional}

    def parse_details(self, response):
        try:
            with open("details.html", "wb") as Response:
                Response.write(response.body)
            selector = Selector(response)
            price = self.utils.get_element_value("hotelDepthPriceDivSelector", selector)
            charge_list = self.utils.get_element_value("hotelDepthChargeDivSelector", selector)
            room = response.meta.get("Room")
            daily_rate = room["DailyRate"]
            stay_amount = room["StayAmount"]
            price = re.findall('\d+', price)[0]
            daily_rate["Price"] = round(float(price)/float(self.config["CrawlParams"]["minimumLengthofStay"]), 2)
            stay_amount["Price"] = price
            for charge in charge_list:
                charge_details = self.utils.get_element_value("hotelDepthChargeDetailsSelector", charge)
                charge_price = self.utils.get_element_value("hotelDepthChargePriceSelector", charge)
                daily_rate["TaxInfo"] = {}
                stay_amount["TaxInfo"] = {}
                if charge_price is not None and charge_details is not None:
                    charge_price = charge_price.strip("\n")
                    charge_details = charge_details.strip("\n")
                    charge_details = charge_details.split('%')
                    daily_rate["TaxInfo"][charge_details[1]] = {"Percent": charge_details[0],
                                                                "Value": charge_price}
                    stay_amount["TaxInfo"][charge_details[1]] = {"Percent": charge_details[0],
                                                                 "Value": charge_price}
            room["DailyRate"] = daily_rate
            room["StayAmount"] = stay_amount
            for i in range(len(self.hotel["Rooms"])):
                if self.hotel["Rooms"][i]["RoomId"] == room["RoomId"]:
                    self.hotel["Rooms"][i] = room
            self.utils = None
            yield {"Rooms": True}
        except Exception as e:
            raise e

    def error_handler(self, failure):
        # log all failures
        self.logger.error(repr(failure))
        self.error_type = SCRAPY_FAILURE_PROXY
        self.error_description = failure.getErrorMessage()
        # in case you want to do something special for some errors,
        # you may need the failure's type:
        if failure.check(HttpError):
            # these exceptions come from HttpError spider middleware
            # you can get the non-200 response
            response = failure.value.response
            self.logger.error('HttpError on %s', response.url)
        elif failure.check(DNSLookupError):
            # this is the original request
            request = failure.request
            self.logger.error('DNSLookupError on %s', request.url)
        elif failure.check(TimeoutError, TCPTimedOutError):
            request = failure.request
            self.logger.error('TimeoutError on %s', request.url)
        yield {"error_type": self.error_type, "error_description": self.error_description, "data": self.hotel,
               "not_scraped_items": self.not_scraped_items, "not_scraped_items_optional":
                   self.not_scraped_items_optional}
