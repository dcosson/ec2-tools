#!/bin/bash

###
### Some of the vars
###
if [ ! $# -eq 1 ] && [ ! $# -eq 2 ]
then
    echo 'usage: ./create_instance.sh BOXNAME [HOSTNAME]'
    exit 1;
fi
BOXNAME=$1
# HOSTNAME is optional, it will default to BOXNAME
if [ $# -eq 2 ]
then
    HOSTNAME=$2
else
    HOSTNAME=$BOXNAME
fi

### 
### EC2 Commands
### 
echo "Creating box $BOXNAME"
# create a new 8GB ebs-backed micro instance in us east 1c.  We're passing in hostname as userdata
AMI_ID=`ec2-run-instances ami-057bcf6c --instance-type t1.micro --availability-zone us-east-1c --user-data "hostname=$HOSTNAME" --block-device-mapping /dev/sda1=:8:true --key venmo_macbook_air_danny_rsa | egrep '^INSTANCE' | cut -f 2`
PUBLIC_DNS=`ec2-describe-instances $AMI_ID | egrep '^INSTANCE' | cut -f 4`
# set the name
ec2-create-tags $AMI_ID --tag Name=$BOXNAME > /dev/null
echo "domain name: $PUBLIC_DNS"

### give the box time to come up
echo -n "waiting for box to launch"
while [ true ] ;
do
    STATUSLINE=`ec2-describe-instance-status $AMI_ID | egrep '^INSTANCE\s'` 
    if [ `echo $STATUSLINE | cut -d' ' -f 4` == "running" ] && [ `echo $STATUSLINE | cut -d' ' -f 6` == "ok" ] && [ `echo $STATUSLINE | cut -d' ' -f 7` == "ok" ] ;
    then
        break
    fi
    echo -n '.'
    sleep 1
done
echo ' box running!'

###
### Set up the Hostname using the script
###
SET_HOSTNAME_SCRIPT='./set_hostname.sh'
USER=ubuntu
scp -oStrictHostKeyChecking=no $SET_HOSTNAME_SCRIPT $USER@$PUBLIC_DNS:/home/$USER/$SET_HOSTNAME_SCRIPT
ssh $USER@$PUBLIC_DNS "sudo /home/$USER/$SET_HOSTNAME_SCRIPT $HOSTNAME" 
