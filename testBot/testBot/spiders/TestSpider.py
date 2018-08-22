import scrapy
import json
from urllib.parse import urlparse
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.internet.error import DNSLookupError, TCPTimedOutError
from testBot.constants import SCRAPY_FAILURE_PROXY, SCRAPY_FAILURE_OTHERS
from testBot.exceptions import ProxyFailureException, HTMLParsingException


class TestSpider(scrapy.Spider):
    name = "test_spider"
    config = None
    error_type = None
    error_description = None
    not_scraped_items = []
    not_scraped_items_optional = []
    hotel = {}

    def __init__(self, *args, **kwargs):
        super(TestSpider, self).__init__(*args, **kwargs)
        self.config = kwargs.get("config")
        self.config = json.loads(self.config)
        self.url = self.config["BotInfo"]["BaseUrl"]
        self.domain = urlparse(self.url).netloc
        self.start_urls = [self.url]
        self.allowed_domains = [self.domain]

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
        yield {"error_type": self.error_type, "error_description": self.error_description, "data": {},
               "not_scraped_items": self.not_scraped_items, "not_scraped_items_optional":
                   self.not_scraped_items_optional}

    def parse_hotel(self, response):
        with open("response.html", "wb") as Response:
            Response.write(response.body)
