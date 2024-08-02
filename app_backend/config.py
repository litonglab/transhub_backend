BASEDIR = "/mnt/f/linux/project/Transhub_data"

ALL_CLASS = {"计算机系统基础II": "pantheon-ics", "计算机网络": "pantheon-network",
             "校内赛计算机网络赛道": "pantheon-competition"}

# 构建规则：{cname: BASEDIR+ALL_CLASS[cname]}
ALL_CLASS_PATH = {cname: BASEDIR + "/" + ALL_CLASS[cname] for cname in ALL_CLASS.keys()}

USER_DIR_PATH = BASEDIR + "/user_data"
DDLTIME = '2099-06-19-23-01-00'

MYSQL_USERNAME='root'
MYSQL_PASSWORD='0'
MYSQL_ADDRESS='localhost:3307'
MYSQL_DBNAME = 'transhub_base'



class cctraining_config:
    cname = "计算机网络"
    loss_rate = [0.0, 0.1]
    # uplink_file = ALL_CLASS_PATH[cname] + "/test_data/Verizon-LTE-short.up"
    # downlink_file = ALL_CLASS_PATH[cname] + "/test_data/Verizon-LTE-short.down"
    zhinan_path = ALL_CLASS_PATH[cname] + "/help/zhinan.pdf"
    downlink_dir =ALL_CLASS_PATH[cname]+ "/test_data/downlink"
    uplink_dir = ALL_CLASS_PATH[cname]+"/test_data/uplink"
    trace_num = 1
    cca_guide_path = ALL_CLASS_PATH[cname] + "/help/cca_guide.docx"
    user_guide_path = ALL_CLASS_PATH[cname] + "/help/user_guide.docx"

