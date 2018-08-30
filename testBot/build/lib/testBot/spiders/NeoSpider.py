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
    step = 1

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
        print("here")
        if "step" + str(self.step) in self.nav_config:
            step_data = self.nav_config["step" + str(self.step)]
            self.step += 1
            if step_data["action"] == "redirect":
                redirect_url = self.parse_url(step_data["urlGenerator"])
                print(redirect_url)
                yield scrapy.Request(redirect_url, callback=self.parse_hotel, errback=self.error_handler)
            elif step_data["action"] == "click":
                pass

    def parse_hotel(self, response):
        with open("response.html", "wb") as Response:
            Response.write(response.body)

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
                print(sub)
            url_generator = url_generator.replace("{"+item[0]+"#"+item[1]+"}", sub)
        return url_generator