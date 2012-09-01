#!/bin/bash
# Copy over the puppet dir to /etc/puppet

if [ ! $# -eq 2 ]
then
    echo 'usage: ./copy_puppet_dir.sh LOGIN PUPPET_DIR_LOCAL'
    exit 1;
fi

LOGIN=$1
PUPPET_DIR=$2

if [ ! -d $PUPPET_DIR ]
then
    echo "local directory: $PUPPET_DIR doesn't exist, exiting."
    exit 1
fi
ssh $LOGIN 'sudo mkdir -p /tmp && sudo chmod 777 /tmp'
scp -r $PUPPET_DIR $LOGIN:/tmp/puppet
ssh $LOGIN 'sudo rm -rf /etc/puppet && sudo mv /tmp/puppet /etc/puppet'
