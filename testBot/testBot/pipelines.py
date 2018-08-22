# -*- coding: utf-8 -*-

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html


class TestbotPipeline(object):
    items = []
    not_scraped_items = []
    not_scraped_items_optional = []
    error_type = None
    error_description = None

    def process_item(self, item, spider):
        self.items.append(item["data"])
        self.error_type = item["error_type"]
        self.error_description = item["error_description"]
        self.not_scraped_items += item["not_scraped_items"]
        self.not_scraped_items_optional += item["not_scraped_items_optional"]
        return item
