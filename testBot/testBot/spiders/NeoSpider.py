import scrapy
import json
import re
from urllib.parse import urlparse
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.selector import Selector
from twisted.internet.error import DNSLookupError, TCPTimedOutError
from testBot.constants import SCRAPY_FAILURE_PROXY, SCRAPY_FAILURE_OTHERS, SCRAPY_FAILURE_HTML


class NeoSpider(scrapy.Spider):
    name = "neo_spider"
    config = None
    error_type = 0
    url = ""
    domain = ""
    allowed_domains = []
    start_urls = []
    error_description = ""
    not_scraped_items = []
    not_scraped_items_optional = []
    hotel = {}
    tags = {}
    step = 1
    room_id = 1

    def __init__(self, *args, **kwargs):
        super(NeoSpider, self).__init__(*args, **kwargs)
        self.config = kwargs.get("config")
        self.config = json.loads(self.config)
        self.nav_config = kwargs.get("nav_config")
        self.nav_config = json.loads(self.nav_config)
        self.process_config()

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, errback=self.error_handler, dont_filter=True)

    def process_config(self):
        if "step" + str(self.step) in self.nav_config:
            step_data = self.nav_config["step" + str(self.step)]
            self.url = step_data["url"]
            self.domain = urlparse(self.url).netloc
            self.start_urls = [self.url]
            self.allowed_domains = [self.domain]

    def parse(self, response):
        if "step" + str(self.step) in self.nav_config:
            step_data = self.nav_config["step" + str(self.step)]
            self.step += 1
            if len(step_data["htmlTags"]) != 0:
                selector = Selector(response)
                self.tags = step_data["htmlTags"]
                self.process_tags(selector)
            if step_data["action"] == "redirect":
                redirect_url = self.parse_url(step_data["urlGenerator"])
                print(redirect_url)
                yield scrapy.Request(redirect_url, callback=self.parse_hotel, errback=self.error_handler)
            elif step_data["action"] == "click":
                pass

    def parse_hotel(self, response):
        with open("response_neo.html", "wb") as Response:
            Response.write(response.body)
        if "step" + str(self.step) in self.nav_config:
            step_data = self.nav_config["step" + str(self.step)]
            self.step += 1
            self.get_hotel_details()
            if len(step_data["htmlTags"]) != 0:
                selector = Selector(response)
                self.tags = step_data["htmlTags"]
                self.process_tags(selector)
            if step_data["action"] == "redirect":
                redirect_url = self.parse_url(step_data["urlGenerator"])
                print(redirect_url)
                yield scrapy.Request(redirect_url, callback=self.parse_hotel, errback=self.error_handler)
            elif step_data["action"] == "click":
                pass

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

    def parse_url(self, url_generator):
        pattern = r"{(.*?)#(.*?)}"
        result = re.findall(pattern, url_generator)
        for item in result:
            sub = self.config[item[0]][item[1]]
            if item[1] == "checkInDate" or item[1] == "checkOutDate":
                sub = sub.replace('/', '-')
            url_generator = url_generator.replace("{"+item[0]+"#"+item[1]+"}", sub)
        return url_generator

    def process_tags(self, selector):
        for tag in self.tags:
            if tag == "hotelRoomsTableDivSelector":
                self.get_room_details(selector)
            elif self.tags[tag]["parent"] is None:
                self.evaluate_tag(tag, selector)

    def get_room_details(self, selector):
        try:
            rooms_table_div = self.get_element_value("hotelRoomsTableDivSelector", selector)
            rooms_div = self.get_element_value("hotelRoomsRowDivSelector", rooms_table_div)
            room_id = 0
            for room_div in rooms_div:
                room = self.get_room()
                self.hotel["Rooms"].append(room)
                availability_div = self.get_element_value("roomAvailabilityDivSelector", room_div)
                if availability_div is not None and len(availability_div) == 0:
                    check = self.get_element_value("roomCheckSelector", room_div)
                    if check is None or len(check) == 0:
                        room = self.hotel["Rooms"][room_id-1]
                        for tag in self.config["BotInfo"]["HtmlTags"]:
                            if tag == "hotelPriceDivSelector":
                                room = self.get_price_details(room, room_div)
                            elif tag == "hotelBedroomTypeDivSelector":
                                self.get_bedroom_details(room, room_div)
                            elif self.config["BotInfo"]["HtmlTags"][tag]["parent"] == "hotelRoomsRowSelector" and\
                                    tag != "roomCheckSelector" and tag != "roomAvailabilityDivSelector" and not\
                                    self.config["BotInfo"]["HtmlTags"][tag]["filter"]:
                                self.evaluate_tag(tag, room_div)
                    else:
                        room_id += 1
                        room["Availability"] = "O"
                        room["Error_Description"] = None
                        for tag in self.config["BotInfo"]["HtmlTags"]:
                            if tag == "hotelPriceDivSelector":
                                self.get_price_details(room, room_div)
                            elif tag == "hotelBedroomTypeDivSelector":
                                self.get_bedroom_details(room, room_div)
                            elif self.config["BotInfo"]["HtmlTags"][tag]["parent"] == "hotelRoomsRowSelector" and\
                                    tag != "roomCheckSelector" and tag != "roomAvailabilityDivSelector":
                                self.evaluate_tag(tag, room_div)
                else:
                    room = self.get_room()
                    room_id += 1
                    for tag in self.config["BotInfo"]["HtmlTags"]:
                        if self.config["BotInfo"]["HtmlTags"][tag]["parent"] == "hotelRoomsRowSelector" and \
                                tag != "roomCheckSelector" and tag != "hotelPriceDivSelector"\
                                and tag != "roomAvailabilityDivSelector":
                            self.evaluate_tag(tag, room_div)
                    room["Error_Description"] = self.get_element_value("hotelRoomStatusSelector", availability_div)
                    room["Availability"] = "AVL01"
                self.hotel["Rooms"].append(room)
        except Exception as e:
            raise e

    def get_room(self):
        room = {
            "Url": "",
            "PagePosition": "",
            "PageRank": "",
            "OverallRank": "",
            "OutBoundFlightDetails": "",
            "ReturnFlightDetails": "",
            "Discount": 0,
            "Transferincluded": "",
            "TransferType": "",
            "CheapestRateIndicator": "",
            "FilePath": "",
            "Extra2": "",
            "Extra3": "",
            "Extra5": "",
            "Extra4": "",
            "HitCount": "",
            "Facilities": [],
            "DailyRate": {"TaxInfo": {}},
            "StayAmount": {"TaxInfo": {}}
        }
        return room

    def get_hotel_details(self):
        # adding hotel details
        try:
            self.hotel["WebsiteName"] = self.config["BotInfo"]["WebsiteName"]
            self.hotel["SiteId"] = self.config["BotInfo"]["WebsiteID"]
            self.hotel["rateRequestId"] = ""
            self.hotel["LOS"] = self.config["CrawlParams"]["minimumLengthofStay"]
            self.hotel["HotelId"] = self.config["CrawlParams"]["propertyID"]
            self.hotel["ServerResponseTime"] = ""
            self.hotel["PageContentSize_MD"] = None
            self.hotel["RequestSegmentId"] = self.config["MetaData"]["RequestSegmentId"]
            self.hotel["ReportID"] = self.config["MetaData"]["ReportId"]
            self.hotel["CityId"] = self.config["CrawlParams"]["cityId"]
            self.hotel["isRequestFailed"] = None
            self.hotel["RequestType"] = self.config["CrawlParams"]["type"]
            self.hotel["CheckInDate"] = self.config["CrawlParams"]["checkInDate"]
            self.hotel["CheckOutDate"] = self.config["CrawlParams"]["checkOutDate"]
            self.hotel["City"] = self.config["CrawlParams"]["city"]
            self.hotel["RequestCurrency"] = self.config["CrawlParams"]["currency"]
            self.hotel["Rooms"] = []
        except Exception as e:
            raise e

    def get_price_details(self, room, selector):
        price_div = self.get_element_value("hotelPriceDivSelector", selector)
        price_check = self.get_element_value("hotelRoomDiscountPriceSelector", price_div)
        if price_check is not None and len(price_check) != 0:
            discount_price = self.get_element_value("hotelRoomDiscountPriceSelector", price_div)
            original_price = self.get_element_value("hotelRoomOriginalPriceSelector", price_div)
            original_price = re.findall('\d+', original_price)
            discount_price = re.findall('\d+', discount_price)
            if len(original_price) == 2:
                original_price = float(original_price[0]) + float(original_price[1]) / 100
            elif len(original_price) == 1:
                original_price = float(original_price[0])
            if len(discount_price) == 2:
                discount_price = float(discount_price[0]) + float(discount_price[1]) / 100
            elif len(discount_price) == 1:
                discount_price = float(discount_price[0])
            room["DailyRate"]["Price"] = discount_price / int(self.config["CrawlParams"]["minimumLengthofStay"])
            room["StayAmount"]["Price"] = discount_price
            room["Discount"] = (original_price - discount_price) * 100 / float(original_price)
            room["RateCategory"] = "O"
        else:
            standard_price = self.get_element_value("hotelRoomStandardPriceSelector", price_div)
            standard_price = re.findall('\d+', standard_price)
            if len(standard_price) == 2:
                standard_price = float(standard_price[0]) + float(standard_price[1]) / 100
            elif len(standard_price) == 1:
                standard_price = float(standard_price[0])
            room["DailyRate"]["Price"] = standard_price / int(self.config["CrawlParams"]["minimumLengthofStay"])
            room["StayAmount"]["Price"] = standard_price
            room["RateCategory"] = "O"
        return room

    def get_tax_details(self, target, tax_info):
        tax = "".join(tax_info)
        tax = tax.strip("\n")
        tax = tax.split("\n")
        tax = [i for i in tax if i != ""]
        tax_included = []
        tax_not_included = []
        inclusion = True
        for i in range(len(tax)):
            if "Not included" in tax[i]:
                inclusion = False
            elif "Included" in tax[i]:
                inclusion = True
            elif '%' in tax[i]:
                if inclusion:
                    tax_included.append(tax[i])
                else:
                    tax_not_included.append(tax[i])
        daily_rate = target["DailyRate"]
        stay_amount = target["StayAmount"]
        if len(tax_included) == 0:
            daily_rate["isTaxIncluded"] = False
            stay_amount["isTaxIncluded"] = False
            for i in tax_not_included:
                temp = i.strip(",").split("%")
                daily_rate["TaxInfo"][temp[1]] = temp[0]
                stay_amount["TaxInfo"][temp[1]] = temp[0]
        else:
            daily_rate["isTaxIncluded"] = True
            stay_amount["isTaxIncluded"] = True
            for i in tax_included:
                temp = i.strip(",").split("%")
                daily_rate["TaxInfo"][temp[1]] = temp[0]
                stay_amount["TaxInfo"][temp[1]] = temp[0]
        target["DailyRate"] = daily_rate
        target["StayAmount"] = stay_amount
        return target

    def get_bedroom_details(self, room, room_div):
        try:
            bedroom = self.get_element_value("hotelBedroomTypeDivSelector", room_div)
            check = self.get_element_value("hotelBedtypeFixedSelector", bedroom)
            if check is not None and len(check) != 0:
                self.evaluate_tag("hotelBedtypeFixedSelector", room_div)
            else:
                self.evaluate_tag("hotelBedtypeOptionsSelector", room_div)
            return room
        except Exception as e:
            raise e

    def evaluate_tag(self, parent_tag, selector):
        children = 0
        child_selector = selector.xpath(self.tags[parent_tag]["ByXpath"])
        for tag in self.tags:
            if self.tags[tag]["parent"] == parent_tag:
                children += 1
                if child_selector is None or len(child_selector) == 0:
                    if self.tags[parent_tag]["isOptional"]:
                        self.not_scraped_items_optional.append(parent_tag)
                    else:
                        self.not_scraped_items.append(parent_tag)
                else:
                    self.evaluate_tag(tag, child_selector)
        if children == 0:
            value = self.get_element_value(parent_tag, selector)
            if value is None or len(value) == 0:
                if self.tags[parent_tag]["isOptional"]:
                    self.not_scraped_items_optional.append(parent_tag)
                else:
                    self.not_scraped_items.append(parent_tag)
            else:
                if "Room" in parent_tag:
                    self.hotel["Rooms"][self.room_id-1] = self.save(self.hotel["Rooms"][self.room_id-1],
                                                                    self.tags[parent_tag]["SavePath"].split(";"), value)
                else:
                    self.hotel = self.save(self.hotel, self.tags[parent_tag]["SavePath"].split(";"), value)

    def get_element_value(self, parent_tag, selector):
        try:
            if self.tags[parent_tag]["isValue"]:
                output = selector.xpath(self.tags[parent_tag]["ByXpath"] + "/text()")
                if output is not None and len(output) != 0:
                    output = output.extract_first().strip("\n").strip()
            else:
                output = selector.xpath(self.tags[parent_tag]["ByXpath"])
                if "string(" in self.tags[parent_tag]["ByXpath"] and\
                        "Div" not in parent_tag:
                    if output is not None and len(output) != 0:
                        output = output.extract_first().strip("\n").strip()
            return output
        except Exception as e:
            self.error_type = SCRAPY_FAILURE_HTML
            self.error_description = str(e)
            raise e

    def save(self, target, save_path, value):
        try:
            if len(save_path) == 0:
                return value
            else:
                if save_path[0] == "add":
                    if isinstance(value, str):
                        target.append(value)
                    else:
                        target += value
                else:
                    if save_path[0] not in target:
                        target[save_path[0]] = self.save({}, save_path[1:], value)
                    else:
                        target[save_path[0]] = self.save(target[save_path[0]], save_path[1:], value)
                return target
        except Exception as e:
            raise e
