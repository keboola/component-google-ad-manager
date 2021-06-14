import sys
import logging
import yaml
import json
import tempfile
from googleads import ad_manager
from googleads import errors
from googleads.common import ZeepServiceProxy


class GoogleAdManagerClient:

    def __init__(self, client_email, private_key, token_uri, network_code, api_version):
        logging.info(f"Using version of Google Ad Manager API: {api_version}")

        private_key_file = self.get_private_key_file(private_key, client_email, token_uri)

        self.client = self.get_client(network_code, private_key_file)
        self.report_downloader = self.client.GetDataDownloader(version=api_version)

    @staticmethod
    def get_client(network_code, private_key_file):
        try:
            client = ad_manager.AdManagerClient.LoadFromString(yaml.dump({
                "ad_manager": {
                    "application_name": "kds-team.ex-google-ad-manager",
                    "network_code": network_code,
                    "path_to_private_key_file": private_key_file
                }
            }))
        except ValueError as e:
            raise ValueError(
                f"{e} Please, check format of your private key. New lines"
                f" must be delimited by \\n character."
            )
        client.cache = ZeepServiceProxy.NO_CACHE
        return client

    @staticmethod
    def get_private_key_file(private_key, client_email, token_uri) -> str:
        file_path = "/tmp/private_key.json"
        with open(file_path, 'w') as outfile:
            json.dump({
                "private_key": private_key,
                "client_email": client_email,
                "token_uri": token_uri
            }, outfile)
        return file_path

    @staticmethod
    def get_report_query(dimensions, metrics, timezone, dimension_attributes="", ad_unit_view="", currency="",
                         date_from="", date_to=""):
        report_query = {
            'dimensions': dimensions,
            'columns': metrics,
            'timeZoneType': timezone
        }

        if date_from and date_to:
            report_query['dateRangeType'] = "CUSTOM_DATE"
            report_query['startDate'] = date_from
            report_query['endDate'] = date_to

        if dimension_attributes:
            report_query['dimensionAttributes'] = dimension_attributes

        if ad_unit_view:
            report_query['adUnitView'] = ad_unit_view

        if currency:
            report_query['adxReportCurrency'] = currency

        return report_query

    def fetch_report_result(self, report_query):
        report_file = tempfile.NamedTemporaryFile(
            suffix='.csv', delete=False
        )
        report_job = {
            'reportQuery': report_query
        }
        report_job_id = self.create_report(report_job)

        self.report_downloader.DownloadReportToFile(
            report_job_id=report_job_id,
            export_format='CSV_DUMP',
            outfile=report_file,
            use_gzip_compression=False
        )
        return report_file

    def create_report(self, report_job: dict):
        """Create report via API"""
        try:
            # Run the report and wait for it to finish
            report_job_id = self.report_downloader.WaitForReport(report_job)
            return report_job_id
        except errors.AdManagerReportError as e:
            logging.info('Failed to generate report. Error: %s' % e)
            sys.exit()
