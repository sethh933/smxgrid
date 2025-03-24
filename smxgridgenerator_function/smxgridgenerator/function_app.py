import logging
import requests
import azure.functions as func
import azure.functions.decorators as decorators

app = decorators.FunctionApp()

@app.function_name(name="smxgridgenerator")
@app.schedule(schedule="0 0 0 * * *", arg_name="myTimer", run_on_startup=False, use_monitor=False)
def main(myTimer: func.TimerRequest) -> None:
    try:
        url = "https://smxmusegrid.azurewebsites.net/generate-and-archive-switch"
        response = requests.post(url)
        response.raise_for_status()
        logging.info(f"✅ Daily grid generated: {response.json()}")
    except Exception as e:
        logging.error(f"❌ Grid generation failed: {str(e)}")
