import datetime

import pandas as pd


def pd_date_to_datetime(date, hour=None, minute=None):
    date = pd.to_datetime(date)
    hour = date.hour if hour is None else hour
    minute = date.minute if minute is None else minute
    # TODO: add option to keep the TZ - now we have to localize again if it is needed
    return datetime.datetime(date.year, date.month, date.day, hour, minute, 0, 0)


def paginated_html_table(df_html: str):
    # Credit goes to: https://stackoverflow.com/a/49134917
    base_html = """
                <!doctype html>
                <html><head>
                <meta http-equiv="Content-type" content="text/html; charset=utf-8">
                <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/2.2.2/jquery.min.js"></script>
                <link rel="stylesheet" type="text/css" href="https://cdn.datatables.net/1.10.16/css/jquery.dataTables.css">
                <script type="text/javascript" src="https://cdn.datatables.net/1.10.16/js/jquery.dataTables.js"></script>
                </head><body>%s<script type="text/javascript">$(document).ready(function(){$('table').DataTable({
                    "lengthMenu": [[5, 10, 25, 50, -1], [5, 10, 25, 50, "All"]],
                    "pageLength": 5,
                    "scrollX": true,
                    "order": []
                });});</script>
                </body></html>
                """

    if isinstance(df_html, pd.DataFrame):
        df_html = df_html.to_html()

    return base_html % df_html
