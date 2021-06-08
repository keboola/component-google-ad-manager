'''
Template Component main class.

'''
import csv
import logging
import dateparser
import os

from google_ad_manager.ad_manager_client import GoogleAdManagerClient
from keboola.utils.header_normalizer import get_normalizer, NormalizerStrategy
from keboola.component.base import ComponentBase, UserException

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
KEY_REPORT_CURRENCY = "report_currency"

REQUIRED_PARAMETERS = []
REQUIRED_IMAGE_PARS = []

types = ["Historical", "Future sell - through", "Reach", "Sales", "Ad Exchange", "Ad speed"]


class Component(ComponentBase):
    def __init__(self):
        super().__init__(required_parameters=REQUIRED_PARAMETERS,
                         required_image_parameters=REQUIRED_IMAGE_PARS)

    def run(self):
        params = self.configuration.parameters

        client_email = params.get(KEY_CLIENT_EMAIL)
        private_key = params.get(KEY_PRIVATE_KEY).replace("\\n", "\n")
        token_uri = params.get(KEY_TOKEN_URI)
        network_code = params.get(KEY_NETWORK_CODE)
        report_type = params.get(KEY_REPORT_TYPE)
        report_name = "".join([params.get(KEY_REPORT_NAME), ".csv"])
        metrics = self.parse_input_string_to_list(params.get(KEY_METRICS))
        dimensions = self.parse_input_string_to_list(params.get(KEY_DIMENSIONS))
        dimension_attributes = self.parse_input_string_to_list(params.get(KEY_DIMENSION_ATTRIBUTES))
        timezone = params.get(KEY_TIMEZONE)
        date_from = params.get(KEY_DATE_FROM)
        date_to = params.get(KEY_DATE_TO)

        date_from = dateparser.parse(date_from).date()
        date_to = dateparser.parse(date_to).date()

        try:
            client = GoogleAdManagerClient(client_email, private_key, token_uri, network_code, API_VERSION)
        except ValueError as client_error:
            raise UserException(client_error) from client_error

        if report_type == "Historical":
            report_query = client.get_report_query(dimensions, metrics, timezone,
                                                   dimension_attributes=dimension_attributes, date_from=date_from,
                                                   date_to=date_to)
        elif report_type == "Ad Exchange historical":
            report_query = client.get_report_query(dimensions, metrics, timezone, date_from=date_from,
                                                   date_to=date_to)
        elif report_type == "Future sell - through":
            report_query = client.get_report_query(dimensions, metrics, timezone, date_from=date_from,
                                                   date_to=date_to)
        elif report_type == "Reach":
            report_query = client.get_report_query(dimensions, metrics)
        elif report_type == "Ad speed":
            report_query = client.get_report_query(dimensions, metrics)

        result_file = client.fetch_report_result(report_query)
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
