# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html
import json
import requests
from testBot.constants import SCRAPY_FAILURE_PROXY, FAILURE_STATUS_TRUE, FAILURE_STATUS_FALSE


class TestbotPipeline(object):
    items = []
    not_scraped_items = []
    not_scraped_items_optional = []
    error_type = None
    error_description = None
    request_id = None
    url = None

    def open_spider(self, spider):
        self.request_id = spider.config["MetaData"]["RowKey"]
        self.url = spider.config["ApiEndpoints"]["ClosureServiceUrl"]

    def close_spider(self, spider):
        item = {
                "requestId": self.request_id, "data": self.items,
                "error": {"errorType": self.error_type, "errorDescription": self.error_description},
                "websiteId": spider.config["MetaData"]["SiteId"],
                "failedElements": {"not_scraped_items": self.not_scraped_items,
                                   "not_scraped_items_optional": self.not_scraped_items_optional},
                }
        if len(self.not_scraped_items) > 0 or self.error_type == SCRAPY_FAILURE_PROXY or len(self.items) == 0:
            item["status"] = FAILURE_STATUS_TRUE
        else:
            item["status"] = FAILURE_STATUS_FALSE
        data_json = json.dumps(item)
        print(item)
        headers = {'Content-Type': 'application/json'}
        try:
            requests.post(url=self.url, data=data_json, headers=headers)
        except Exception as e:
            print(str(e))

    def process_item(self, item, spider):
        if "Rooms" not in item:
            self.items.append(item["data"])
            self.error_type = item["error_type"]
            self.error_description = item["error_description"]
            self.not_scraped_items += item["not_scraped_items"]
            self.not_scraped_items_optional += item["not_scraped_items_optional"]
        return item
