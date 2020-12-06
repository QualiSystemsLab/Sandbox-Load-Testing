from datetime import datetime


def get_utc_iso_8601_timestamp():
    """
    sample "2020-12-05T20:25:50.412Z"
    :return:
    """
    iso_8601_format = "%Y-%m-%dT%H:%M:%SZ"
    ts = datetime.utcnow().strftime(iso_8601_format)
    return ts


if __name__ == "__main__":
    x = get_utc_iso_8601_timestamp()
    print(x)