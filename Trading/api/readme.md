# How to run the REST API

Currently, the API supports one user, as it was intended for personal use.

The main use cases of this API are:
* data visualization via a third-party plugin that polls the API. I use Grafana as I didn't have the time or the need to code my own dashboard.
* data manipulation via POST methods, to quickly add data to your JSON files. You can implement custom buttons, or simply use the `http://127.0.0.1:8000/docs/` interface.

To learn the prerequisites of each component (as some require you to create and fill up JSON files with personal data), inspect these readmes:
* [loan](../loan)
* [investment](../investment)
* [stock](../stock)

Assuming that you have properly installed this framework, following the instructions [here](../../README.md):

Run the following command from this folder: `uvicorn api.main:app --reload`

Go to the following address to ensure the REST api is up and running: `http://127.0.0.1:8000/docs`

You should see something like this:
![Selection_1513](https://github.com/doruirimescu/python-trading/assets/7363000/8cfa9bb8-6197-4307-9cf9-0cc93ceb0d55)
