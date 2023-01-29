from Trading.utils.time import get_date_now_cet
import os
import json


def write_json_to_file_named_with_today_date(json_dict):
    data_path = os.getenv("DATA_STORAGE_PATH", "data/")
    date_today = get_date_now_cet()
    json_path = data_path + str(date_today) + ".json"
    f = open(json_path, 'w')
    json_object = json.dumps(json_dict, indent=4)
    f.write(json_object)
    f.close()


def read_json_from_file_named_with_today_date():
    data_path = os.getenv("DATA_STORAGE_PATH", "data/")
    date_today = get_date_now_cet()
    json_path = data_path + str(date_today) + ".json"
    try:
        f = open(json_path, 'r+')
    except Exception as e:
        return None
    json_data = json.load(f)
    f.close()
    return json_data
