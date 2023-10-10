import logging

import googleads.errors
import yaml
import json
import tempfile
from retry import retry
from typing import List
from datetime import date
from googleads import ad_manager
from googleads import errors
from googleads.common import ZeepServiceProxy


class GoogleAdManagerClientException(Exception):
    pass


class GoogleAdManagerClient:

    def __init__(self, client_email, private_key, token_uri, network_code, api_version):
        logging.info(f"Using version of Google Ad Manager API: {api_version}")

        private_key_file = self.get_private_key_file(private_key, client_email, token_uri)

        self.api_version = api_version
        self.client = self.get_client(network_code, private_key_file)
        self.report_downloader = self.client.GetDataDownloader(version=self.api_version)

    @staticmethod
    def get_client(network_code: str, private_key_file: str) -> ad_manager.AdManagerClient:
        try:
            client = ad_manager.AdManagerClient.LoadFromString(yaml.dump({
                "ad_manager": {
                    "application_name": "kds-team.ex-google-ad-manager",
                    "network_code": network_code,
                    "path_to_private_key_file": private_key_file
                }
            }))
        except ValueError as e:
            raise GoogleAdManagerClientException(f"{e} Please, check format of your private key. "
                                                 f"New lines must be delimited by \\n character.") from e

        client.cache = ZeepServiceProxy.NO_CACHE
        return client

    @staticmethod
    def get_private_key_file(private_key: str, client_email: str, token_uri: str) -> str:
        file_path = "/tmp/private_key.json"
        with open(file_path, 'w') as outfile:
            json.dump({
                "private_key": private_key,
                "client_email": client_email,
                "token_uri": token_uri
            }, outfile)
        return file_path

    def get_report_query(self, dimensions: List, metrics: List, dimension_attributes: List = None,
                         ad_unit_view: str = "", currency: str = "", date_from: date = "", date_to: date = "",
                         dynamic_date: str = "", include_zero_impressions: bool = False) -> dict:

        report_query = {
            'dimensions': dimensions,
            'columns': metrics
        }

        if currency:
            report_query['reportCurrency'] = currency

        if dynamic_date:
            report_query["dateRangeType"] = dynamic_date
        elif date_from and date_to:
            report_query['dateRangeType'] = "CUSTOM_DATE"
            report_query['startDate'] = date_from
            report_query['endDate'] = date_to

        if dimension_attributes:
            report_query['dimensionAttributes'] = dimension_attributes

        if ad_unit_view:
            report_query['adUnitView'] = ad_unit_view

        if include_zero_impressions:
            report_query['include_zero_impressions'] = True

        logging.info(f"Running query : {report_query}")
        return report_query

    @retry(errors.GoogleAdsServerFault, tries=5, delay=30)
    def fetch_report_result(self, report_query: dict) -> tempfile.NamedTemporaryFile:
        report_file = tempfile.NamedTemporaryFile(suffix='.csv', delete=False)
        report_job = {'reportQuery': report_query}
        report_job_id = self.create_report(report_job)

        try:
            self.report_downloader.DownloadReportToFile(
                report_job_id=report_job_id,
                export_format='CSV_DUMP',
                outfile=report_file,
                use_gzip_compression=False)
        except errors.GoogleAdsServerFault as e:
            raise errors.GoogleAdsServerFault(f"Google Server Error occured : {e}") from e

        report_file.close()

        return report_file

    def create_report(self, report_job: dict):
        """Create report via API"""
        try:
            return self.report_downloader.WaitForReport(report_job)
        except errors.AdManagerReportError as e:
            raise GoogleAdManagerClientException(f'Failed to generate report. Error: {e}') from e
        except KeyError as e:
            raise GoogleAdManagerClientException(f"Failed to generate report. Please check used dimensions, "
                                                 f"metrics and used api version, Error: {e}") from e
        except googleads.errors.GoogleAdsServerFault as e:
            raise GoogleAdManagerClientException(f"Failed to generate report. Please check used dimensions, "
                                                 f"metrics and used api version, Error: {e}") from e
        except googleads.errors.GoogleAdsValueError() as e:
            raise GoogleAdManagerClientException(f"Failed to generate report. Selected API version is probably "
                                                 f"deprecated. Error: {e} from e")
