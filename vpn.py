
import subprocess
import tempfile
import json
import time
from pathlib import Path

instance_ids = ""
AWS_START_CMD = f"aws ec2 start-instances --instance-ids {instance_ids}"
AWS_STOP_CMD = f"aws ec2 stop-instances --instance-ids {instance_ids}"
AWS_DESCRIBE_CMD = f"aws ec2 describe-instances --instance-ids {instance_ids}"

cur_dir = Path(__file__).parent

ovpn = cur_dir/"aws-ovpn.ovpn"

def check_aws(ret):
    if ret.returncode != 0:
        raise RuntimeError(f"aws command failed")

def run_aws_command(command):
    print(f"executing {command}..")
    ret = subprocess.run(command, shell=True, capture_output=True)
    if ret.returncode != 0:
        print("----------stdout---------")
        print(ret.stdout)
        print("----------stderr---------")
        print(ret.stderr)
    return ret

try:
    check_aws(run_aws_command(AWS_START_CMD))

    while True:
        ret = run_aws_command(AWS_DESCRIBE_CMD)
        if ret.returncode != 0:
            time.sleep(5)
            continue
        query = json.loads(ret.stdout)
        if query["Reservations"][0]["Instances"][0]["State"]["Name"] != "running":
            time.sleep(5)
            continue
        break

    ip = query["Reservations"][0]["Instances"][0]["PublicIpAddress"]

    with open(ovpn, "r") as f:
        with tempfile.NamedTemporaryFile("w+t") as temp:
            for line in f:
                if line.startswith("remote"):
                    port = line.split()[-1]
                    line = f"remote {ip} {port}\n"
                temp.write(line)
            temp.flush()
            subprocess.run(f"cat {temp.name}", shell=True)
            subprocess.run(f"sudo openvpn --config {temp.name}", shell=True)

except:
    check_aws(run_aws_command(AWS_STOP_CMD))
