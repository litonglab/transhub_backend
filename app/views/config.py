import yaml

from app.extensions import redis_client
import json
from app.config import ALL_SUMMARY_DIR_PATH, JSON_KEY, YAML_KEY

def set_config_json(json_content):
    p = redis_client.pipeline()
    p.set(JSON_KEY, json.dumps(json_content))
    p.execute()
    for temp_dir in ALL_SUMMARY_DIR_PATH:
        with open(f"{temp_dir}/src/experiments/data/pantheon_metadata.json", "w") as f:
            print(f"write json to {temp_dir}/src/experiments/data/pantheon_metadata.json")
            json.dump(json_content, f, indent=4)
        with open(f"{temp_dir}/src/experiments/data_p/pantheon_metadata.json", "w") as f:
            print(f"write json to {temp_dir}/src/experiments/data_p/pantheon_metadata.json")
            json.dump(json_content, f, indent=4)






def get_config_json():
    data = redis_client.get(JSON_KEY)
    if data:
        return json.loads(data)
    for temp_dir in ALL_SUMMARY_DIR_PATH:
        with open(f"{temp_dir}/src/experiments/data/pantheon_metadata.json", "r") as f:
            jsoncontent = json.load(f)
            set_config_json(jsoncontent)
            return jsoncontent


# app/views/config.py
def set_config_yaml(config_content):
    p = redis_client.pipeline()
    p.set(YAML_KEY, str(config_content))
    p.execute()
    for temp_dir in ALL_SUMMARY_DIR_PATH:
        with open(f"{temp_dir}/src/config.yml", "w") as f:
            yaml.dump(config_content, f, default_flow_style=False)

# app/views/config.py
def get_config_yaml():
    data = redis_client.get(YAML_KEY)
    if data:
        return yaml.safe_load(data)
    for temp_dir in ALL_SUMMARY_DIR_PATH:
        with open(f"{temp_dir}/src/config.yml", "r+") as f:
            c_content = yaml.safe_load(f)
            set_config_yaml(c_content)
            return c_content