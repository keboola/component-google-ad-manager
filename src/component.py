import logging
import dateparser
import os
import re
from datetime import date
from datetime import timedelta
from typing import List

from google_ad_manager import GoogleAdManagerClient, GoogleAdManagerClientException
from keboola.utils.header_normalizer import get_normalizer, NormalizerStrategy
from keboola.component.base import ComponentBase, UserException
from googleads import errors as google_errors
from google.auth import exceptions

KEY_API_VERSION = "api_version"
KEY_CLIENT_EMAIL = "client_email"
KEY_PRIVATE_KEY = "#private_key"
KEY_TOKEN_URI = "token_uri"
KEY_NETWORK_CODE = "network_code"
KEY_REPORT_SETTINGS = "report_settings"
KEY_REPORT_NAME = "report_name"
KEY_METRICS = "metrics"
KEY_DIMENSIONS = "dimensions"
KEY_DIMENSION_ATTRIBUTES = "dimension_attributes"
KEY_DATE_RANGE_SETTINGS = "date_settings"
KEY_DATE_FROM = "date_from"
KEY_DATE_TO = "date_to"
KEY_DATE_RANGE = "date_range"
KEY_REPORT_CURRENCY = "report_currency"
KEY_AD_UNIT_VIEW = "ad_unit_view"

REQUIRED_PARAMETERS = [KEY_CLIENT_EMAIL, KEY_PRIVATE_KEY, KEY_TOKEN_URI, KEY_NETWORK_CODE, KEY_REPORT_SETTINGS,
                       KEY_REPORT_NAME, KEY_DATE_RANGE_SETTINGS]
REQUIRED_IMAGE_PARS = []

SUPPORTED_VERSIONS = ["v202308", "v202305", "v202302", "v202211"]


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
        report_name = params.get(KEY_REPORT_NAME)
        report_name = "".join([self._normalize_report_name(report_name), ".csv"])
        report_settings = params.get(KEY_REPORT_SETTINGS)
        metrics = self._parse_input_string_to_list(report_settings.get(KEY_METRICS))
        dimensions = self._parse_input_string_to_list(report_settings.get(KEY_DIMENSIONS))
        dimension_attributes = self._parse_input_string_to_list(report_settings.get(KEY_DIMENSION_ATTRIBUTES))
        report_currency = report_settings.get(KEY_REPORT_CURRENCY, None)
        ad_unit_view = report_settings.get(KEY_AD_UNIT_VIEW)
        date_settings = params.get(KEY_DATE_RANGE_SETTINGS, {})
        date_from = date_settings.get(KEY_DATE_FROM)
        date_to = date_settings.get(KEY_DATE_TO)
        date_range = date_settings.get(KEY_DATE_RANGE)

        if (api_version := params.get(KEY_API_VERSION)) is not None:
            if api_version not in SUPPORTED_VERSIONS:
                raise UserException(f"Unsupported API version: {api_version}")

        date_from, date_to, dynamic_date = self._get_date_range(date_from, date_to, date_range)

        try:
            client = GoogleAdManagerClient(client_email, private_key, token_uri, network_code, api_version)
        except ValueError as client_error:
            raise UserException(client_error) from client_error
        except exceptions.RefreshError as login_error:
            raise UserException(login_error) from login_error
        except GoogleAdManagerClientException as client_error:
            raise UserException(client_error) from client_error

        report_query = client.get_report_query(dimensions, metrics,
                                               dimension_attributes=dimension_attributes, date_from=date_from,
                                               date_to=date_to, dynamic_date=dynamic_date, currency=report_currency,
                                               ad_unit_view=ad_unit_view)
        try:
            result_file = client.fetch_report_result(report_query)
        except google_errors.GoogleAdsServerFault as google_error:
            raise UserException(google_error) from google_error
        except GoogleAdManagerClientException as client_error:
            raise UserException(client_error) from client_error

        filesize = os.path.getsize(result_file.name)
        if filesize == 0:
            raise UserException("No data found")

        table = self.create_out_table_definition(report_name, incremental=False)
        columns = self._write_results_get_columns(result_file.name, table.full_path)
        columns = self._normalize_column_names(columns)
        table.columns = columns

        self.write_tabledef_manifest(table)

    @staticmethod
    def _normalize_column_names(output_columns: List) -> List:
        header_normalizer = get_normalizer(strategy=NormalizerStrategy.DEFAULT, forbidden_sub="_")
        return header_normalizer.normalize_header(output_columns)

    @staticmethod
    def _write_results_get_columns(in_table_path: str, out_table_path: str) -> List:
        """Processes binary file to utf-8 and returns columns"""
        columns = []
        with open(out_table_path, mode='wt', encoding='utf-8') as new_file:
            with open(in_table_path, mode='rb') as original_file:
                for i, line in enumerate(original_file):
                    if i == 0:
                        columns = line.decode().strip().split(",")
                        # Do not write header to CSV file
                        continue
                    new_file.write(line.decode())
        return columns

    @staticmethod
    def _parse_input_string_to_list(input_string: str) -> List:
        input_string = re.sub(r"[^a-zA-Z0-9_,]", '', input_string)
        input_list = input_string.split(",")
        return [word.strip() for word in input_list]

    @staticmethod
    def _get_last_week_dates() -> (date, date):
        today = date.today()
        offset = (today.weekday() - 5) % 7
        last_week_saturday = today - timedelta(days=offset)
        last_week_sunday = last_week_saturday - timedelta(days=6)
        return last_week_sunday, last_week_saturday

    @staticmethod
    def _get_last_month_dates() -> (date, date):
        last_day_of_prev_month = date.today().replace(day=1) - timedelta(days=1)
        start_day_of_prev_month = date.today().replace(day=1) - timedelta(days=last_day_of_prev_month.day)
        return start_day_of_prev_month, last_day_of_prev_month

    def _get_date_range(self, date_from: str, date_to: str, date_range: str) -> (date, date, str):
        dynamic_date = ""
        if date_range == "Last week (sun-sat)":
            date_from, date_to = self._get_last_week_dates()
        elif date_range == "Last month":
            date_from, date_to = self._get_last_month_dates()
        elif date_range == "Custom":
            try:
                date_from = dateparser.parse(date_from).date()
                date_to = dateparser.parse(date_to).date()
            except (AttributeError, TypeError) as err:
                raise UserException("Failed to parse custom date") from err
        elif date_range == "Next week":
            dynamic_date = "NEXT_WEEK"
        elif date_range == "Next month":
            dynamic_date = "NEXT_MONTH"
        elif date_range == "Reach lifetime":
            dynamic_date = "REACH_LIFETIME"
        elif date_range == "Next day":
            dynamic_date = "NEXT_DAY"
        elif date_range == "Yesterday":
            dynamic_date = "YESTERDAY"
        else:
            logging.info("No date range specified")
        return date_from, date_to, dynamic_date

    @staticmethod
    def _normalize_report_name(report_name: str) -> str:
        header_normalizer = get_normalizer(strategy=NormalizerStrategy.DEFAULT, forbidden_sub="_")
        return header_normalizer.normalize_header([report_name])[0]


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
