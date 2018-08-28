# -*- coding: utf-8 -*-
import pdb  # noqa
import re
import csv
import os
from datetime import datetime
from urllib.parse import urlencode
from scraper.settings import settings

import pandas as pd
import scrapy


def clean_text(text):
    return re.sub('\s{2,}', ' ', text).strip()


def make_file_name(attrs):
    filename = '{query}_{treasury}_{year}.csv'.format(**attrs)
    filename = re.sub(r',+', '', filename).replace(' ', '_').replace('/', '_')
    return filename


def get_datasets_path():
    dataset_relative_path = os.path.join(settings.PROJECT_PATH, '../datasets')
    dataset_path = os.path.normpath(dataset_relative_path)
    return dataset_path


class DatasetCollector(scrapy.Spider):
    allowed_domains = ['himkosh.hp.nic.in']

    ddo_code = '500'
    datasets_path = get_datasets_path()

    def parse(self, response):
        '''
        Collect queryable params and make dataset queries.
        '''

        current_date = datetime.today().strftime('%Y%m%d')
        # create date ranges for 10 years from now.
        start_dates = pd.date_range('20080101', current_date, freq='AS-JAN').strftime('%Y%m%d')
        end_dates = pd.date_range('20080101', current_date, freq='Y').strftime('%Y%m%d')

        if current_date not in end_dates:
            end_dates = end_dates.append(pd.Index([current_date]))

        # collect all treasury names from dropdown.
        treasuries = response.css('#cmbHOD option')

        # collect all query names from dropdown.
        queries = response.css('#ddlQuery option')

        # for each year for each query for each treasury, make requests for datasets.
        for treasury in treasuries[1:]:
            treasury_id = treasury.css('::attr(value)').extract_first() + '-' + self.ddo_code
            treasury_name = treasury.css('::text').extract_first()
            treasury_name = clean_text(treasury_name)

            for query in queries[1:]:
                query_id = query.css('::attr(value)').extract_first()
                query_name = query.css('::text').extract_first()
                query_name = clean_text(query_name)

                for start, end in zip(start_dates, end_dates):
                    query_params = {
                        'from_date': start,
                        'To_date': end,
                        'ddlquery': query_id,
                        'HODCode': treasury_id,
                        'Str': query_name
                    }

                    filename = make_file_name(
                        {'query': query_name, 'treasury': treasury_name, 'year': start[:4]}
                    )
                    filepath = os.path.join(self.datasets_path, filename)

                    # don't request the same dataset again if it's already collected previously
                    if not os.path.exists(filepath):
                        yield scrapy.Request(
                            self.query_url.format(urlencode(query_params)), self.parse_dataset,
                            meta={'filepath': filepath}
                        )

    def parse_dataset(self, response):
        '''
        Parse each dataset page to collect the data in a csv file.

        output: a csv file named with query_treasury_year(all lowercase) format.
        '''
        # header row for the file.
        heads = response.css('table tr.popupheadingeKosh td::text').extract()

        # all other rows
        data_rows = response.css('table tr[class*=pope]')

        # prepare file name and its path to write the file.
        filepath = response.meta.get('filepath')

        with open(filepath, 'w') as output_file:
            writer = csv.writer(output_file, delimiter=',')

            # write the header
            writer.writerow(heads)

            # write all other rows
            for row in data_rows:
                cols = row.css('td')
                observation = []
                for col in cols:
                    # since we need consistency in the row length,
                    # we need to extract each cell and set empty string when no data found.
                    # by default scrapy omits the cell if it's empty and it can cause inconsistent row lengths.  # noqa
                    observation.append(col.css('::text').extract_first(' '))
                writer.writerow(observation)


class ExpendituresSpider(DatasetCollector):
    name = 'expenditures'

    # this page contains all the populating info.
    start_urls = ['https://himkosh.hp.nic.in/treasuryportal/eKosh/ekoshddoquery.asp']

    # dataset is collected from here.
    query_url = 'https://himkosh.hp.nic.in/treasuryportal/eKosh/eKoshDDOPopUp.asp?{}'


class ReceiptsSpider(DatasetCollector):
    name = 'receipts'

    # this page contains all the populating info.
    start_urls = ['https://himkosh.hp.nic.in/treasuryportal/eKosh/eKoshDDOReceiptQuery.asp']

    # dataset is collected from here.
    query_url = 'https://himkosh.hp.nic.in/treasuryportal/eKosh/eKoshDDOReceiptPopUp.asp?{}'
