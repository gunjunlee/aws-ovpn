import subprocess
import time
import os
from pathlib import Path
import platform
import csv
import json
import sys
import signal
import configparser
import argparse
import boto3
import botocore
from botocore.config import Config
import pdb

SSH_CMD = "ssh -o StrictHostKeyChecking=no -i {path_aws_key} ubuntu@{aws_ip}"
SCP_CMD = "scp -o StrictHostKeyChecking=no -i {path_aws_key} ubuntu@{aws_ip}"
SSH_WAIT_CMD = SSH_CMD + " ls"
SET_WG_SERVER_CMD =  SSH_CMD + \
                     " \"wget https://git.io/wireguard -O wireguard-install.sh" + \
                     " && sudo bash wireguard-install.sh" + \
                     " && sudo cp /root/client.conf ~/\""
GET_WG_CONF_CMD = SCP_CMD + ":~/client.conf {conf_path}"
WG_UP = "sudo wg-quick up {conf_path}"
WG_DOWN = "sudo wg-quick down {conf_path}"
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
path_credential = cur_dir / "credentials.csv"
path_cache = cur_dir / "cache.json"
dir_conf = cur_dir / "configs"
dir_conf.mkdir(exist_ok=True)


def get_region(region):
    if region is not None:
        if region in AWS_REGIONS.keys():
            return AWS_REGIONS[region]
        elif region in AWS_REGIONS.values():
            return region
        print("There is no region {region}".format(region=region))

    default_region = "tokyo"
    while True:
        region = input(
            "Enter the VPN server region {regions} (default: {default_region}): "
            .format(regions=list(AWS_REGIONS.keys()),
                    default_region=default_region)).strip()
        if len(region) == 0:
            region = default_region
        if region in AWS_REGIONS.keys():
            return AWS_REGIONS[region]
        elif region in AWS_REGIONS.values():
            return region
        print("There is no region {region}.".format(region=region))


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
    proc = subprocess.Popen(cmd,
                            shell=True,
                            stdin=sys.stdin.fileno(),
                            stdout=sys.stdout.fileno(),
                            stderr=sys.stderr.fileno())
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError("Error occured during setup wireguard server")


def get_wg_conf(path_aws_key, aws_ip, conf_path):
    proc = subprocess.run(GET_WG_CONF_CMD.format(path_aws_key=path_aws_key,
                                                 aws_ip=aws_ip,
                                                 conf_path=conf_path),
                          shell=True)
    if proc.returncode != 0:
        raise RuntimeError(
            "Error occured during downloading wireguard config from server")


def aws_run_instance(ec2, sg_id):
    print("Creating instance...")
    ret = ec2.run_instances(
        MaxCount=1,
        MinCount=1,
        ImageId="ami-0df99b3a8349462c6",  # ubuntu 20.04 base
        KeyName="aws-tokyo",
        InstanceType="t2.micro",
        SecurityGroupIds=sg_id,
        TagSpecifications=[{
            "ResourceType": "instance",
            "Tags": [{
                "Key": "Name",
                "Value": "wg-server",
            }]
        }],
    )

    return ret["Instances"][0]["InstanceId"]


def aws_wait_running(ec2, instance_id):
    while True:
        ret = ec2.describe_instances(InstanceIds=[instance_id])
        state = ret["Reservations"][0]["Instances"][0]["State"]["Name"].lower()
        if state == "running":
            break
        print(
            "Instance (id={instance_id}) is not running (now: {state}). wait for 5 seconds.."
            .format(instance_id=instance_id, state=state))
        time.sleep(5)  # wait for 5 secs


def aws_get_ip(ec2, instance_id):
    ret = ec2.describe_instances(InstanceIds=[instance_id])
    ip = ret["Reservations"][0]["Instances"][0]["PublicIpAddress"]
    return ip


def aws_is_instance_usable(ec2, instance_id):
    try:
        ret = ec2.describe_instances(InstanceIds=[instance_id])
        state = ret["Reservations"][0]["Instances"][0]["State"]["Name"].lower()
        if state == "shutting-down" or state == "terminated":
            print("instance (id={instance_id}) is not usable (state={state})".
                  format(instance_id=instance_id, state=state))
            return False
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidInstanceID.NotFound":
            print("Cannot find instance (id = {instance_id})".format(
                instance_id=instance_id))
            return False
    return True


def aws_start_instance(ec2, instance_id):
    ret = ec2.start_instances(InstanceIds=[instance_id])


def aws_stop_instance(ec2, instance_id):
    ret = ec2.stop_instances(InstanceIds=[instance_id])


def aws_get_security_group_id(ec2):
    try:
        ret = ec2.describe_security_groups(GroupNames=["AWS-WIREGUARD-VPN"])
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidGroup.NotFound":
            return None
    return ret["SecurityGroups"][0]["GroupId"]


def aws_create_security_group(ec2):
    try:
        ret = ec2.create_security_group(Description="for AWS WIREGUARD VPN",
                                        GroupName="AWS-WIREGUARD-VPN")
        sg_id = ret["GroupId"]
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "InvalidGroup.Duplicate":
            print("Use preexisting security group")
            ret = ec2.describe_security_groups(
                GroupNames=["AWS-WIREGUARD-VPN"])
            sg_id = ret["SecurityGroups"][0]["GroupId"]

    ret = ec2.authorize_security_group_ingress(GroupId=sg_id,
                                               IpPermissions=[{
                                                   'FromPort':
                                                   51820,
                                                   'IpProtocol':
                                                   'udp',
                                                   'IpRanges': [{
                                                       'CidrIp':
                                                       '0.0.0.0/0'
                                                   }],
                                                   'Ipv6Ranges': [],
                                                   'PrefixListIds': [],
                                                   'ToPort':
                                                   51820,
                                                   'UserIdGroupPairs': []
                                               }, {
                                                   'FromPort':
                                                   22,
                                                   'IpProtocol':
                                                   'tcp',
                                                   'IpRanges': [{
                                                       'CidrIp':
                                                       '0.0.0.0/0',
                                                       'Description':
                                                       ''
                                                   }],
                                                   'Ipv6Ranges': [],
                                                   'PrefixListIds': [],
                                                   'ToPort':
                                                   22,
                                                   'UserIdGroupPairs': []
                                               }])
    return sg_id


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


def wg_up(conf_path):
    cmd = WG_UP.format(conf_path=conf_path)
    ret = subprocess.run(cmd, shell=True)


def wg_down(conf_path):
    cmd = WG_DOWN.format(conf_path=conf_path)
    ret = subprocess.run(cmd, shell=True)


def signal_handler(sig, frame):
    wg_down(conf_path=conf_path)
    aws_stop_instance(ec2, instance_id)

    cache[aws_region] = {
        "instance-id": instance_id,
        "conf-path": conf_path,
        "path-aws-key": path_aws_key,
    }
    with path_cache.open("w") as cache_file:
        json.dump(cache, cache_file)


def update_config(conf_path, ip):
    config = configparser.ConfigParser()
    config.read(conf_path)
    _, port = config["Peer"]["Endpoint"].split(":")
    config["Peer"]["Endpoint"] = "{ip}:{port}".format(ip=ip, port=port)
    with open(conf_path, "w") as f:
        config.write(f)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aws-key", type=str, help="path to aws key")
    parser.add_argument("--region", type=str, help="region")
    args = parser.parse_args()
    return args


if __name__ == "__main__":
    args = parse_args()

    access_key, secret_key = get_cred_key()

    cache = {}
    try:
        with path_cache.open("r") as cache_file:
            cache = json.load(cache_file)
            print(cache)
    except FileNotFoundError:
        pass

    aws_region = get_region(cache.get("aws_region", args.region))
    config = Config(region_name=aws_region, )
    ec2 = boto3.client("ec2",
                       config=config,
                       aws_access_key_id=access_key,
                       aws_secret_access_key=secret_key)

    sg_id = aws_get_security_group_id(ec2)
    if sg_id is None:
        print(
            "Cannot find security group for AWS WIREGUARD VPN (region: {region})"
            .format(region=aws_region))
        print("Creating security group...")
        sg_id = aws_create_security_group(ec2)

    is_ready = False
    if aws_region in cache.keys():
        c = cache[aws_region]
        instance_id = c["instance-id"]
        conf_path = c["conf-path"]
        path_aws_key = c["path-aws-key"]
        check_ssh_key(path_aws_key)

        if aws_is_instance_usable(ec2, instance_id):
            aws_start_instance(ec2, instance_id)
            aws_wait_running(ec2, instance_id)
            ip = aws_get_ip(ec2, instance_id)
            aws_wait_ssh(path_aws_key=path_aws_key, aws_ip=ip)
            update_config(conf_path, ip)
            is_ready = True
    if not is_ready:
        conf_path = str((dir_conf / aws_region).absolute()) + ".conf"
        instance_id = aws_run_instance(ec2, sg_id)
        aws_wait_running(ec2, instance_id)
        ip = aws_get_ip(ec2, instance_id)
        if args.aws_key is not None:
            path_aws_key = args.aws_key
        else:
            path_aws_key = input(
                "Enter the path to aws key (region: {region}): ".format(
                    region=aws_region))
        check_ssh_key(path_aws_key)

        aws_wait_ssh(path_aws_key=path_aws_key, aws_ip=ip)
        set_wg_server(path_aws_key=path_aws_key, aws_ip=ip)
        get_wg_conf(path_aws_key=path_aws_key, aws_ip=ip, conf_path=conf_path)

    wg_up(conf_path=conf_path)

    signal.signal(signal.SIGINT, signal_handler)
    signal.pause()
