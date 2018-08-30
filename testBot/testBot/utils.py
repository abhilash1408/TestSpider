import re
from testBot.constants import SCRAPY_FAILURE_HTML
from testBot.exceptions import HTMLParsingException


class Utils(object):
    error_type = 0
    error_description = ""

    def __init__(self, config, hotel, not_scraped_items, not_scraped_items_optional):
        self.not_scraped_items_optional = not_scraped_items_optional
        self.hotel = hotel
        self.config = config
        self.not_scraped_items = not_scraped_items

    def evaluate_tag(self, parent_tag, parent_selector, target):
        try:
            children = 0
            for child_tag in self.config["BotInfo"]["HtmlTags"]:
                if self.config["BotInfo"]["HtmlTags"][child_tag]["parent"] == parent_tag:
                    children += 1
                    child_selector = parent_selector.xpath(self.config["BotInfo"]["HtmlTags"][parent_tag]["ByXpath"])
                    self.evaluate_tag(child_tag, child_selector, target)
            if children == 0:
                value = self.get_element_value(parent_tag, parent_selector)
                if value is None or len(value) == 0:
                    if not self.config["BotInfo"]["HtmlTags"][parent_tag]["isOptional"]:
                        if parent_tag not in self.not_scraped_items:
                            self.not_scraped_items.append(parent_tag)
                    else:
                        if parent_tag not in self.not_scraped_items_optional:
                            self.not_scraped_items_optional.append(parent_tag)
                else:
                    if parent_tag == "hotelTaxDetailsSelector":
                        target = self.get_tax_details(target, value)
                    else:
                        target = self.save(target, self.config["BotInfo"]
                                           ["HtmlTags"][parent_tag]["SavePath"].split(";"), value)
            return target
        except HTMLParsingException as e:
            if not self.config["BotInfo"]["HtmlTags"][parent_tag]["isOptional"]:
                if parent_tag not in self.not_scraped_items:
                    self.not_scraped_items.append(parent_tag)
            else:
                if parent_tag not in self.not_scraped_items_optional:
                    self.not_scraped_items_optional.append(parent_tag)
            self.error_type = SCRAPY_FAILURE_HTML
            self.error_description = str(e)
            raise e
        except Exception as e:
            self.error_type = SCRAPY_FAILURE_HTML
            self.error_description = str(e)

    def get_room_details(self, selector):
        try:
            rooms_table_div = self.get_element_value("hotelRoomsTableDivSelector", selector)
            rooms_div = self.get_element_value("hotelRoomsRowDivSelector", rooms_table_div)
            room_id = 0
            for room_div in rooms_div:
                room = self.get_room()
                availability_div = self.get_element_value("roomAvailabilityDivSelector", room_div)
                if availability_div is not None and len(availability_div) == 0:
                    check = self.get_element_value("roomCheckSelector", room_div)
                    if check is None or len(check) == 0:
                        room = self.hotel["Rooms"][room_id-1]
                        for tag in self.config["BotInfo"]["HtmlTags"]:
                            if tag == "hotelPriceDivSelector":
                                room = self.get_price_details(room, room_div)
                            elif tag == "hotelBedroomTypeDivSelector":
                                room = self.get_bedroom_details(room, room_div)
                            elif self.config["BotInfo"]["HtmlTags"][tag]["parent"] == "hotelRoomsRowSelector" and\
                                    tag != "roomCheckSelector" and tag != "roomAvailabilityDivSelector" and not\
                                    self.config["BotInfo"]["HtmlTags"][tag]["filter"]:
                                room = self.evaluate_tag(tag, room_div, room)
                    else:
                        room_id += 1
                        room["Availability"] = "O"
                        room["Error_Description"] = None
                        for tag in self.config["BotInfo"]["HtmlTags"]:
                            if tag == "hotelPriceDivSelector":
                                room = self.get_price_details(room, room_div)
                            elif tag == "hotelBedroomTypeDivSelector":
                                room = self.get_bedroom_details(room, room_div)
                            elif self.config["BotInfo"]["HtmlTags"][tag]["parent"] == "hotelRoomsRowSelector" and\
                                    tag != "roomCheckSelector" and tag != "roomAvailabilityDivSelector":
                                room = self.evaluate_tag(tag, room_div, room)
                else:
                    room = self.get_room()
                    room_id += 1
                    for tag in self.config["BotInfo"]["HtmlTags"]:
                        if self.config["BotInfo"]["HtmlTags"][tag]["parent"] == "hotelRoomsRowSelector" and \
                                tag != "roomCheckSelector" and tag != "hotelPriceDivSelector"\
                                and tag != "roomAvailabilityDivSelector":
                            room = self.evaluate_tag(tag, room_div, room)
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

    def save(self, d, save_path, value):
        try:
            if len(save_path) == 0:
                return value
            else:
                if save_path[0] == "add":
                    if isinstance(value, str):
                        d.append(value)
                    else:
                        d += value
                else:
                    if save_path[0] not in d:
                        d[save_path[0]] = self.save({}, save_path[1:], value)
                    else:
                        d[save_path[0]] = self.save(d[save_path[0]], save_path[1:], value)
                return d
        except Exception as e:
            raise e

    def get_element_value(self, tag, selector):
        try:
            if self.config["BotInfo"]["HtmlTags"][tag]["isValue"]:
                output = selector.xpath(self.config["BotInfo"]["HtmlTags"][tag]["ByXpath"]+"/text()")
                if output is not None and len(output) != 0:
                    if tag == "hotelOtherFacilitiesSelector":
                        output = [x.strip("\n") for x in output.extract()]
                    else:
                        output = output.extract_first().strip("\n").strip()
            else:
                output = selector.xpath(self.config["BotInfo"]["HtmlTags"][tag]["ByXpath"])
                if "string(" in self.config["BotInfo"]["HtmlTags"][tag]["ByXpath"] or\
                        "Div" not in tag:
                    if output is not None and len(output) != 0:
                        if tag == "hotelTaxDetailsSelector":
                            output = output.extract()
                        else:
                            output = output.extract_first().strip("\n").strip()
            return output
        except Exception as e:
            raise HTMLParsingException(str(e))

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
                room = self.evaluate_tag("hotelBedtypeFixedSelector", room_div, room)
            else:
                room = self.evaluate_tag("hotelBedtypeOptionsSelector", room_div, room)
            return room
        except Exception as e:
            raise e