import datetime
import logging
import requests

import azure.functions as func

def main(mytimer: func.TimerRequest) -> None:
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()

    try:
        url = "https://smxmusegrid.azurewebsites.net/generate-and-archive-switch"
        response = requests.post(url)
        response.raise_for_status()
        logging.info(f"✅ Daily grid generated: {response.json()} at {utc_timestamp}")
    except Exception as e:
        logging.error(f"❌ Grid generation failed at {utc_timestamp}: {str(e)}")

