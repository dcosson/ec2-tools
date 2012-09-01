#!/bin/bash

###
### Some of the vars
###

if [ ! $# -eq 2 ]
then
    echo 'usage: ./create_instance.sh BOXNAME HOSTNAME'
    exit 1;
fi
BOXNAME=$1
HOSTNAME=$2

### 
### EC2 Commands
### 
# create a new 8GB ebs-backed micro instance in us east 1c.  We're passing in hostname as userdata
AMI_ID=`ec2-run-instances ami-057bcf6c --instance-type t1.micro --availability-zone us-east-1c --user-data "hostname=$HOSTNAME" --block-device-mapping /dev/sda1=:8:true --key venmo_macbook_air_danny_rsa | egrep '^INSTANCE' | cut -f 2`
PUBLIC_DNS=`ec2-describe-instances $AMI_ID | egrep '^INSTANCE' | cut -f 4`
# set the name
ec2-create-tags $AMI_ID --tag Name=$BOXNAME > /dev/null
echo "Created box $BOXNAME at $PUBLIC_DNS"


###
### Set up the Hostname using the script
###
SET_HOSTNAME_SCRIPT='./set_hostname.sh'
USER=ubuntu
scp $SET_HOSTNAME_SCRIPT $USER@$PUBLIC_DNS:/home/$USER/set_hostname.sh
ssh -oStrictHostKeyChecking=no $USER@$PUBLIC_DNS "sudo /home/$USER/set_hostname.sh $HOSTNAME" 
