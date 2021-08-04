# Google Ad Manager Report extractor

This extractor allows you to download specified reports from your Google Ad Manager account. The component uses the 202105 version of the API.

**Table of contents:**  
  
[TOC]

## Authentication
To authenticate the component you must create a Google Service Account and link it to the Google Ad Manager account in the API settings.
From the Google Service Account JSON key you will be able to get the private key and the Token URI.
   
- Token URI (token_uri) - [REQ] uri specified in the service account json key
- Private key (#private_key) - [REQ] specified in the service account json key, copy and paste the entire key (Key must be written in one row, each new line must be delimited by \n character) 
- Service Account Email (client_email) - [REQ]
- Network code (network_code) [REQ] - You'll find this in the URL when you are logged into your network. For example, in the URL https://admanager.google.com/1234#home, 1234 is your network code.

## Report parameters
It is recommended to first create a report on the Google Ad Manager report page to first
test if all dimension and metric combinations are available for the given report type, as
well as the date ranges matching the dimensions (eg. WEEK dimension must have one or more week sun-sat, 
if a date range of mon-fri is given it will result in an error).

Once you create a valid report on the Google Ad Manager report page you can go to the 
[api docs](https://developers.google.com/ad-manager/api/reference/v202105/ReportService.ReportQuery#dimensions)
to find the proper names of the dimensions and metrics for the API.
Eg. CTR in the Ad exchange report type is AD_EXCHANGE_CTR in the API. 

- Output name (report_name) - [REQ] name of output eg. historical_report_ads_weekly will be saved as this in storage
- Report settings (report_settings) [REQ]
  - Dimensios (dimensions) - [REQ] should be written comma separated (no quotation marks) eg. DIMENSION1, DIMENSION2 ... etc.
  - Dimension attributes (dimension_attributes) - [OPT] should be written comma separated (no quotation marks) eg. DIMENSION_ATTR1, DIMENSION_ATTR2 ... etc.
  - Metrics (metrics) - [REQ] should be written comma separated (no quotation marks) eg. METRIC1, METRIC2 ... etc.
  - Report type (report_type) - [REQ] type of report to download
  - Ad Unit view (ad_unit_view) [OPT] - Ad unit view describes how data is fetched about ad units, Default TOP_LEVEL: 
    - TOP_LEVEL : Only the top level ad units. Metrics include events for their descendants that are not filtered out.
    - FLAT : All the ad units. Metrics do not include events for the descendants.
    - HIERARCHICAL : Use the ad unit hierarchy. There will be as many ad unit columns as levels of ad units in the generated report
- Date settings (date_settings) [REQ]
  - Timezone (timezone) - [REQ] Determines the time zone used for the report's date range. It allows AD_EXCHANGE, PUBLISHER and PROPOSAL_LOCAL
  - Date range (date_range) - [REQ] Type of date range
  - Last week (sun-sat) used for WEEK dimension
  - Last month (from first day of the previous month to last day of the previous month)
  - Custom - must then specify date from and to (3 days ago to 1 day ago) (1 march 2021 to 23 march 2021)
    - Date to (date_to) - [OPT] 4 days ago, yeserday, August 14, 2020 EST (it uses [dateparser](https://pypi.org/project/dateparser/))
  - Date from (date_from) - [OPT]