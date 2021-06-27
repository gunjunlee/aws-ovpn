import subprocess
from sys import stderr, stdin, stdout
import tempfile
import json
import time
import os
from pathlib import Path
import platform
import csv
import json
import sys

SSH_CMD = "ssh -i {aws_key} ubuntu@{aws_ip}"
SCP_CMD = "scp -i {aws_key} ubuntu@{aws_ip}"
SET_WG_SERVER_CMD =  SSH_CMD + \
                     "\"wget https://git.io/wireguard -O wireguard-install.sh" + \
                     " && sudo bash wireguard-install.sh" + \
                     " && sudo cp /root/client.conf ~/\""
GET_WG_CONF_CMD = SCP_CMD + ":~/client.conf {conf_path}"
AWS_CMD = " aws --region {aws_region} ec2 "
AWS_RUN_CMD = AWS_CMD + " run-instances" + \
                           " --image-id ami-0df99b3a8349462c6" + \
                           " --key-name {aws_key_name}" + \
                           " --instance-type {aws_instance_type}" + \
                           " --security-group-ids {security_group_ids}" + \
                           " --tag-specifications 'ResourceType=instance,Tags=[{{Key=Name,Value=wg-server}}]'"
AWS_START_CMD = AWS_CMD + " start-instances --instance-ids {instance_ids}"
AWS_STOP_CMD = AWS_CMD + " stop-instances --instance-ids {instance_ids}"
AWS_DESCRIBE_CMD = AWS_CMD + " describe-instances --filters Name=tag-key,Values=Name"
AWS_REGIONS = {
    "tokyo": "ap-northeast-1",
    "seoul": "ap-northeast-2",
    "osaka": "ap-northeast-3",
    "hongkong": "ap-east-1",
    "mumbai": "ap-south-1",
    "singapore": "ap-southeast-1",
    "sydney": "ap-southeast-2",
    "virginia": "us-east-1",
    "ohio": "us-east-2",
    "california": "us-west-1",
    "oregon": "us-west-2",
}
cur_dir = Path(__file__).parent
path_config_template = cur_dir / "config_template.conf"
path_credential = cur_dir / "credentials.csv"
path_cache = cur_dir / "cache.json"
dir_conf = cur_dir / "configs"
dir_conf.mkdir(exist_ok=True)

def connect_windows():
    pass


def get_region(default_region):
    while True:
        region = input(
            "Enter the VPN server region {regions} (default: {default_region}): "
            .format(regions=list(AWS_REGIONS.keys()), default_region=default_region)).strip()
        if len(region) == 0:
            region = default_region
        if region in AWS_REGIONS.keys():
            return AWS_REGIONS[region]
        elif region in AWS_REGIONS.values():
            return region
        print("There is no region named {region}.".format(region=region))


def set_wg_server():
    proc = subprocess.Popen(SET_WG_SERVER_CMD.format(aws_key=aws_key, aws_ip=aws_ip),
                            shell=True,
                            stdin=sys.stdin.fileno(),
                            stdout=sys.stdout.fileno(),
                            stderr=sys.stderr.fileno())
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Error occured during setup wireguard server")


def get_wg_conf():
    conf_path = (dir_conf / aws_region).absolute()
    proc = subprocess.run(GET_WG_CONF_CMD.format(aws_key=aws_key, aws_ip=aws_ip, conf_path=conf_path), shell=True)
    if proc.returncode != 0:
        raise RuntimeError("Error occured during downloading wireguard config from server")


def aws_run_instance():
    cmd = AWS_RUN_CMD.format(
        aws_region=aws_region, aws_key_name="aws-tokyo",
        aws_instance_type="t2.micro", security_group_ids="")#T
    print(cmd)
    proc = subprocess.run(cmd, shell=True, env=os.environ.copy(), capture_output=True)
    print(proc.stdout)


def aws_start_instance():
    pass


def aws_terminate_instance():
    pass


def aws_check_instance():
    cmd = AWS_DESCRIBE_CMD.format(aws_region=aws_region)
    print(cmd)
    proc = subprocess.run(cmd, shell=True, env=os.environ.copy(), capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError("aws descrive failed")
    stats = json.loads(proc.stdout)
    stats["Reservations"][0]["Instances"][0]["Tags"]
    import pdb; pdb.set_trace()


def aws_check_security_group():
    pass


def aws_make_security_group():
    pass


try:
    with path_credential.open("r") as csv_file:
        csv_reader = csv.DictReader(csv_file)
        user_cred = None
        for row in csv_reader:
            if row["User name"] == "AWS-WIREGUARD":
                user_cred = row
                break
        else:
            print("There is no user \"AWS-WIREGUARD\" in credentials.csv")
            print("Use first user instead")
            user_cred = csv_reader[0]
        os.environ["AWS_ACCESS_KEY_ID"] = user_cred["Access key ID"]
        os.environ["AWS_SECRET_ACCESS_KEY"] = user_cred["Secret access key"]
except FileNotFoundError:
    print("Error: {path_credential} not exists".format(
        path_credential=path_credential.absolute()))
    exit(1)

cache = {}
try:
    with path_cache.open("r") as cache_file:
        cache = json.load(cache_file)
        print(cache)
except FileNotFoundError:
    pass

aws_region = get_region(cache.get("aws_region", "seoul"))
# aws_run_instance()
aws_check_instance()

# aws_ip = ""#T
# aws_key = ""#T

# try:
#     set_wg_server()
#     get_wg_conf()
# except:
#     pass

# def check_aws(ret):
#     if ret.returncode != 0:
#         raise RuntimeError(f"aws command failed")


# def run_aws_command(command):
#     print(f"executing {command}..")
#     ret = subprocess.run(command, shell=True, capture_output=True)
#     if ret.returncode != 0:
#         print("----------stdout---------")
#         print(ret.stdout)
#         print("----------stderr---------")
#         print(ret.stderr)
#         print("-------------------------")
#     return ret


# try:
#     check_aws(run_aws_command(AWS_START_CMD))

#     while True:
#         ret = run_aws_command(AWS_DESCRIBE_CMD)
#         if ret.returncode != 0:
#             time.sleep(5)
#             continue
#         query = json.loads(ret.stdout)
#         state = query["Reservations"][0]["Instances"][0]["State"]
#         if state["Name"] != "running":
#             time.sleep(5)
#             continue
#         break

#     ip = query["Reservations"][0]["Instances"][0]["PublicIpAddress"]

#     with open(ovpn, "r") as f:
#         with tempfile.NamedTemporaryFile("w+t") as temp:
#             for line in f:
#                 if line.startswith("remote"):
#                     port = line.split()[-1]
#                     line = f"remote {ip} {port}\n"
#                 temp.write(line)
#             temp.flush()
#             subprocess.run(f"cat {temp.name}", shell=True)
#             subprocess.run(f"sudo openvpn --config {temp.name}", shell=True)

# except:
#     check_aws(run_aws_command(AWS_STOP_CMD))
