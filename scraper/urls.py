from urllib.parse import quote

import config

FILTER_QUERY = quote(f"主推类目： {config.CATEGORY_FILTER};{config.CONTACT_FILTER}", safe="")

DAREN_SQUARE_FILTERED_URL = (
    f"{config.DAREN_SQUARE_URL}?filter={FILTER_QUERY}"
)
