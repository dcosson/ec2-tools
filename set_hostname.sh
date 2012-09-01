#!/bin/bash

# Set the hostname on an ubuntu box
# (set /etc/hostname to hostname and append to /etc/hosts for fqdn)

if [ ! $# -eq 1 ]
then
    echo 'usage: sudo ./set_hostname.sh HOSTNAME'
    exit 1;
fi

HN=$1
echo $HN > /etc/hostname
# make indempotent (only paste it in if it's not there)
if [ `cat /etc/hosts | tail -1 | grep $HN | wc -l` -eq 0 ]
then
    echo "127.0.0.1    $HN.ec2.internal $HN" >> /etc/hosts
fi
hostname `cat /etc/hostname`
echo "Successfully set hostname to $HN"
