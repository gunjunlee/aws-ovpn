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
import boto3
from botocore.config import Config
import pdb

SecurityGroupIds = [""]  #T
path_aws_key = ""  #T
SSH_CMD = "ssh -o StrictHostKeyChecking=no -i {path_aws_key} ubuntu@{aws_ip}"
SCP_CMD = "scp -o StrictHostKeyChecking=no -i {path_aws_key} ubuntu@{aws_ip}"
SSH_WAIT_CMD = SSH_CMD + " ls"
SET_WG_SERVER_CMD =  SSH_CMD + \
                     " \"wget https://git.io/wireguard -O wireguard-install.sh" + \
                     " && sudo bash wireguard-install.sh" + \
                     " && sudo cp /root/client.conf ~/\""
GET_WG_CONF_CMD = SCP_CMD + ":~/client.conf {conf_path}"
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


def connect_mac():
    pass


def connect_linux():
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


def check_ssh_key(path_aws_key):
    if oct(os.stat(path_aws_key).st_mode)[-3:] != "400":
        raise RuntimeError(
            "Permission of the ssh identity file is not owner read only.\n" \
            "Try: chmod 400 {path_aws_key}".format(path_aws_key=path_aws_key))

def aws_wait_ssh(path_aws_key, aws_ip):
    cmd = SSH_WAIT_CMD.format(path_aws_key=path_aws_key, aws_ip=aws_ip)
    while True:
        ret = subprocess.run(cmd, shell=True, capture_output=True)
        if ret.returncode == 0:
            break
        print(
            "Cannot connect Instance(id: {instance_id}, ip: {aws_ip}) yet. wait for 5 seconds.."
            .format(instance_id=instance_id, aws_ip=aws_ip))
        time.sleep(5)

def set_wg_server(path_aws_key, aws_ip):
    cmd = SET_WG_SERVER_CMD.format(path_aws_key=path_aws_key, aws_ip=aws_ip)
    print(cmd)
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdin=sys.stdin.fileno(),
                            stdout=sys.stdout.fileno(),
                            stderr=sys.stderr.fileno())
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Error occured during setup wireguard server")


def get_wg_conf(path_aws_key, aws_ip, conf_path):
    proc = subprocess.run(GET_WG_CONF_CMD.format(path_aws_key=path_aws_key, aws_ip=aws_ip, conf_path=conf_path), shell=True)
    if proc.returncode != 0:
        raise RuntimeError("Error occured during downloading wireguard config from server")


def aws_run_instance(ec2):
    ret = ec2.run_instances(
        MaxCount=1,
        MinCount=1,
        ImageId="ami-0df99b3a8349462c6",  # ubuntu 20.04 base
        KeyName="aws-tokyo",
        InstanceType="t2.micro",
        SecurityGroupIds=SecurityGroupIds,
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [
                    {
                        "Key": "Name",
                        "Value": "wg-server",
                    }
                ]
            }
        ],
    )

    return ret["Instances"][0]["InstanceId"]


def aws_wait_running(ec2, instance_id):
    while True:
        ret = ec2.describe_instances(InstanceIds=[instance_id])
        state = ret["Reservations"][0]["Instances"][0]["State"]["Name"].lower()
        if state == "running":
            break
        print(
            "Instance{instance_id} is not running (now: {state}). wait for 5 seconds.."
            .format(instance_id=instance_id, state=state))
        time.sleep(5)  # wait for 5 secs

def aws_get_ip(ec2, instance_id):
    ret = ec2.describe_instances(InstanceIds=[instance_id])
    ip = ret["Reservations"][0]["Instances"][0]["PublicIpAddress"]
    return ip

def aws_start_instance():
    pass


def aws_terminate_instance():
    pass


def aws_check_instance():
    pass
    stats["Reservations"][0]["Instances"][0]["Tags"]
    import pdb; pdb.set_trace()


def aws_check_security_group():
    pass


def aws_make_security_group():
    pass

def get_cred_key():
    try:
        with path_credential.open("r") as csv_file:
            csv_reader = csv.DictReader(csv_file)

            if "User name" in csv_reader.fieldnames:
                for row in csv_reader:
                    if row["User name"] == "AWS-WIREGUARD":
                        access_key = user_cred["Access key ID"]
                        secret_key = user_cred["Secret access key"]
                        return access_key, secret_key
            print("There is no user \"AWS-WIREGUARD\" in credentials.csv")
            print("Use first user instead")
            user_cred = next(csv_reader)
            access_key = user_cred["Access key ID"]
            secret_key = user_cred["Secret access key"]
            return access_key, secret_key
    except FileNotFoundError:
        print("Error: {path_credential} not exists".format(
            path_credential=path_credential.absolute()))
        exit(1)

if __name__ == "__main__":

    access_key, secret_key = get_cred_key()

    cache = {}
    try:
        with path_cache.open("r") as cache_file:
            cache = json.load(cache_file)
            print(cache)
    except FileNotFoundError:
        pass

    aws_region = get_region(cache.get("aws_region", "tokyo"))
    conf_path = (dir_conf / aws_region).absolute() + ".conf"

    config = Config(
        region_name = aws_region,
    )

    ec2 = boto3.client("ec2",
                       config=config,
                       aws_access_key_id=access_key,
                       aws_secret_access_key=secret_key)

    instance_id = aws_run_instance(ec2)
    aws_wait_running(ec2, instance_id)
    ip = aws_get_ip(ec2, instance_id)

    check_ssh_key(path_aws_key)
    aws_wait_ssh(path_aws_key=path_aws_key, aws_ip=ip)
    set_wg_server(path_aws_key=path_aws_key, aws_ip=ip)
    get_wg_conf(path_aws_key=path_aws_key, aws_ip=ip, conf_path=conf_path)
