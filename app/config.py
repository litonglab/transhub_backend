BASEDIR = "/mnt/f/linux/project/Transhub_data"

ALL_CLASS = {"计算机系统基础II": "pantheon-ics", "计算机网络": "pantheon-network",
             "校内赛计算机网络赛道": "pantheon-competition"}

# 构建规则：{cname: BASEDIR+ALL_CLASS[cname]}
ALL_CLASS_PATH = {cname: BASEDIR + "/" + ALL_CLASS[cname] for cname in ALL_CLASS.keys()}

# ALL_SUMMARY_DIR_PATH = [BASEDIR + "/pantheon-ics",
#                         BASEDIR + "/pantheon-network",
#                         BASEDIR + "/pantheon-competition",
#                         BASEDIR + "/pantheon"]  # default

YAML_KEY = "yaml_config"
JSON_KEY = "json_config"

USER_DIR_PATH = BASEDIR + "/user_data"
DDLTIME = '2099-06-19-23-01-00'

class cctraining_config:
    cname = "计算机网络"
    loss_rate = 0.1
    uplink_file = ALL_CLASS_PATH[cname]+"/test_data/Verizon-LTE-short.up"
    downlink_file = ALL_CLASS_PATH[cname]+"/test_data/Verizon-LTE-short.down"