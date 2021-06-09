'''
Template Component main class.

'''
import csv
import logging
import dateparser
import os
from datetime import date
from datetime import timedelta

from google_ad_manager.ad_manager_client import GoogleAdManagerClient
from keboola.utils.header_normalizer import get_normalizer, NormalizerStrategy
from keboola.component.base import ComponentBase, UserException
from googleads import errors as google_errors

# Deprecation = February 2022
# Sunset = May 2022
API_VERSION = "v202105"

KEY_CLIENT_EMAIL = "client_email"
KEY_PRIVATE_KEY = "#private_key"
KEY_TOKEN_URI = "token_uri"
KEY_NETWORK_CODE = "network_code"
KEY_REPORT_TYPE = "report_type"
KEY_REPORT_NAME = "report_name"
KEY_METRICS = "metrics"
KEY_DIMENSIONS = "dimensions"
KEY_DIMENSION_ATTRIBUTES = "dimension_attributes"
KEY_TIMEZONE = "timezone"
KEY_DATE_FROM = "date_from"
KEY_DATE_TO = "date_to"
KEY_DATE_RANGE = "date_range"
KEY_REPORT_CURRENCY = "report_currency"

REQUIRED_PARAMETERS = []
REQUIRED_IMAGE_PARS = []


class Component(ComponentBase):
    def __init__(self):
        super().__init__(required_parameters=REQUIRED_PARAMETERS,
                         required_image_parameters=REQUIRED_IMAGE_PARS)

    def run(self):
        params = self.configuration.parameters

        client_email = params.get(KEY_CLIENT_EMAIL)
        private_key = params.get(KEY_PRIVATE_KEY).replace("\\n", '\n')
        token_uri = params.get(KEY_TOKEN_URI)
        network_code = params.get(KEY_NETWORK_CODE)
        report_name = "".join([params.get(KEY_REPORT_NAME), ".csv"])
        metrics = self.parse_input_string_to_list(params.get(KEY_METRICS))
        dimensions = self.parse_input_string_to_list(params.get(KEY_DIMENSIONS))
        dimension_attributes = self.parse_input_string_to_list(params.get(KEY_DIMENSION_ATTRIBUTES))
        timezone = params.get(KEY_TIMEZONE)
        date_from = params.get(KEY_DATE_FROM)
        date_to = params.get(KEY_DATE_TO)
        report_currency = params.get(KEY_REPORT_CURRENCY)
        date_range = params.get(KEY_DATE_RANGE)

        date_from, date_to = self.get_date_range(date_from, date_to, date_range)

        try:
            client = GoogleAdManagerClient(client_email, private_key, token_uri, network_code, API_VERSION)
        except ValueError as client_error:
            raise UserException(client_error) from client_error

        report_query = client.get_report_query(dimensions, metrics, timezone,
                                               dimension_attributes=dimension_attributes, date_from=date_from,
                                               date_to=date_to, currency=report_currency)

        try:
            result_file = client.fetch_report_result(report_query)
        except google_errors.GoogleAdsServerFault as google_error:
            raise UserException(google_error) from google_error

        filesize = os.path.getsize(result_file.name)
        if filesize == 0:
            raise UserException("No data found")

        table = self.create_out_table_definition(report_name,
                                                 incremental=False)
        columns = self.write_results_get_columns(result_file.name, table.full_path)
        columns = self.normalize_column_names(columns)
        table.columns = columns

        self.write_tabledef_manifest(table)

    @staticmethod
    def normalize_column_names(output_columns):
        header_normalizer = get_normalizer(strategy=NormalizerStrategy.DEFAULT, forbidden_sub="_")
        return header_normalizer.normalize_header(output_columns)

    @staticmethod
    def write_results_get_columns(in_table_path, out_table_path):
        with open(in_table_path, mode="r") as in_file:
            reader = csv.DictReader(in_file)
            with open(out_table_path, mode='wt', encoding='utf-8', newline='') as out_file:
                writer = csv.DictWriter(out_file, reader.fieldnames)
                for result in reader:
                    writer.writerow(result)
                return reader.fieldnames

    def parse_input_string_to_list(self, input_string):
        input_list = input_string.split(",")
        return [word.strip() for word in input_list]

    @staticmethod
    def get_last_week_dates():
        today = date.today()
        offset = (today.weekday() - 5) % 7
        last_week_saturday = today - timedelta(days=offset)
        last_week_sunday = last_week_saturday - timedelta(days=6)
        return last_week_sunday, last_week_saturday

    def get_last_month_dates(self):
        last_day_of_prev_month = date.today().replace(day=1) - timedelta(days=1)
        start_day_of_prev_month = date.today().replace(day=1) - timedelta(days=last_day_of_prev_month.day)
        return start_day_of_prev_month, last_day_of_prev_month

    def get_date_range(self, date_from, date_to, date_range):
        if date_range == "Last week (sun-sat)":
            date_from, date_to = self.get_last_week_dates()
        elif date_range == "Last month":
            date_from, date_to = self.get_last_month_dates()
        elif date_range == "Custom":
            date_from = dateparser.parse(date_from).date()
            date_to = dateparser.parse(date_to).date()
        return date_from, date_to


if __name__ == "__main__":
    try:
        comp = Component()
        comp.run()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
