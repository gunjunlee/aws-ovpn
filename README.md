# AWS-WIREGUARD

Make and Connect temporal [WireGuard](https://www.wireguard.com/) VPN server on AWS.

VPN server will be terminated automatically when you disconnect the VPN.

## How to Use

This `How to Use` page is written mainly for Windows users. I expect Linux Users can do it!

### 1. Common

1. Install `WireGuard`. Go to [WireGuard installation page](https://www.wireguard.com/install/) and download the Windows installer.
    - if you're a Mac user. try `brew install wireguard-tools` on terminal
2. Configure AWS. Go to [AWS IAM Users management page](https://console.aws.amazon.com/iam/home#/users) and click `add user` button
    1. 1st page
        1. name: `AWS-WIREGUARD`
        2. access type: `programming type`
        3. click `Next: Permissions` button
    2. 2nd page
        1. click `Attach existing policies directly`
        2. click `Create policy` then sub-page will be opened
            1. click `JSON`
            2. Copy and paste the content of `access.txt`
            3. click `Next` button
            4. click `Next` button
            5. Name: `AWS-WIREGUARD`
            6. click `Create policy` button
            7. close the window and go back to original page
        3. click refresh button
        4. find `AWS-WIREGUARD` policy and check it
        5. click `Next: Tags` button
    3. 3rd page
        1. click `Next: Review` button
    4. 4th page
        1. click `Create user` button
    5. 5th page
        1. click `Download .csv` button.
        2. `***.csv` file will be downloaded. this file contains the secret key to access AWS resource. **Do not share/upload secret key.**
        3. copy the file into current folder and rename it `credentials.csv`
    6. Done!
3. Install Python and Pip. (Use Google!)
4. open PowerShell(Windows) or Terminal(Linux)
    1. `pip install -r requirements.txt`
5. `python3 vpn.py`
