#!/usr/bin/env python
""" Fabric tasks for bringing up boxes with EC2 Command Line Tools and setting
them up as puppet agents connecting to an existing puppet master.

Must have AWS tools installed and set up properly
  (try `fab get_status:box_id=BOX_ID` to test that credentials are set up)

Various fallback values imported from fab_conf.py
"""
import logging
import time
import re

from fabric.api import task, local, run, sudo, settings, put
## Keep general setup options & defaults in fab_conf.py
from fab_conf import *

###
### The tasks
###
@task
def create_instance(name,
                    ami_id=None,
                    box_type=None,
                    size_gb=None,
                    zone=None,
                    key_pair=None):
    """ Create an ebs-backed instance, with hostname set to its EC2 Name tag
        :name => EC2 Name and hostname
        :ami_id => the AWS AMI ID of the OS image to install on the box
        :box_type => amazon box size (e.g. t1.micro, m1.large, etc)
        :zone => zone (within us-east region) to use
        :key_pair => AWS private key to accept as default on the new box
    """
    ### Create the box
    ###   (some details are hard-coded for now, until I need to tweak them)
    params = {'ami_id': ami_id or DEFAULT_AMI,
              'box_type': box_type or DEFAULT_BOX_TYPE,
              'size_gb': size_gb or DEFAULT_SIZE,
              'zone': zone or DEFAULT_ZONE,
              'name': name,
              'key_pair': key_pair or DEFAULT_KEY_PAIR}
    cmd = "ec2-run-instances {ami_id} --instance-type {box_type} " \
        "--availability-zone {zone} --user-data 'name={name}' " \
        "--block-device-mapping /dev/sda1=:{size_gb}:true " \
        "--key {key_pair}".format(**params)
    logging.info("Creating box {0}...".format(name))
    result = local(cmd, capture=True)
    box_id = _grab_instance_line_and_split(result)[1]
    ### set Name tag
    cmd = 'ec2-create-tags {0} --tag Name={1}'.format(box_id, name)
    local(cmd, capture=True)
    return box_id


@task
def create_instance_and_set_hostname(name, **kwargs):
    """ Creates an instance, waits for it come up, then sets the hostname and
        updates apt
    """
    box_id = create_instance(name, **kwargs)
    ### Wait for box to come up and tests to pass
    logging.debug('checking status for box_id: {0}'.format(box_id))
    while True:
        logging.debug('waiting to come on line...')
        time.sleep(15)
        ok = get_status(box_id)
        if ok:
            break
    logging.info('box running!')
    ### set hostname & update apt
    host = get_public_dns_from_id(box_id)
    with settings(host_string=host):
        set_hostname(name)
        sudo('apt-get update')
    return box_id


@task
def create_instance_puppet_agent(name, **kwargs):
    """ Create box that will run as puppet agent, install puppet, and register
        it with the puppetmaster
        :name => name & hostname of box
        :puppetmaster_ip => ip address where new box will be able to reach
            the puppetmaster server
        :puppetmaster_dns => domain name where local box can ssh to
            the puppetmaster server
        :puppet_agent_conf_file => puppet.conf file to give to puppet agent
        :kwargs => passed through to the `create_instance` task
    """
    # set up args
    puppetmaster_ip = kwargs.get('puppetmaster_ip') or PUPPETMASTER_IP
    puppetmaster_dns = kwargs.get('puppetmaster_dns') or PUPPETMASTER_DNS
    puppet_agent_conf_file = kwargs.get('puppet_agent_conf_file') or \
            PUPPET_AGENT_CONF_FILE
    # make box
    box_id = create_instance_and_set_hostname(name, **kwargs)
    host = get_public_dns_from_id(box_id)
    with settings(host_string=host):
        install_puppet_agent(puppet_agent_conf_file, puppetmaster_ip)
        puppet_cert_sign(puppetmaster_dns)
    return box_id


@task
def install_puppet_agent(puppet_agent_conf_file, puppetmaster_ip):
    """ install puppet and set box up as a puppet agent
        :puppet_dir => local directory of where to find puppet.conf
    """
    sudo('apt-get install -y puppet')
    # put puppetmaster into the /etc/hosts file
    sudo('echo -e "\\n{0}    puppetmaster.$(dnsdomainname) puppetmaster puppet" ' \
         '>> /etc/hosts'.format(puppetmaster_ip))
    #sudo('rm -rf /etc/puppet/*')   # i was cleaning it out, but no reason to
    put(puppet_agent_conf_file, '/etc/puppet/puppet.conf', use_sudo=True)


@task
def puppet_cert_sign(puppetmaster_dns):
    """ do the master/agent cert handshake for setting up a new puppet agent
        :puppetmaster_dns => dns to reach the puppet master from local box
    """
    agent_fqdn = sudo('facter fqdn', pty=True)
    # initialize handshake - it will fail since it's not signed yet, so exit 0
    sudo('puppet agent -t || exit 0')
    # sign the cert on puppetmaster
    with settings(host_string=puppetmaster_dns):
        sudo('puppet cert sign {0}'.format(agent_fqdn))


@task
def set_hostname(hostname):
    """ Set the hostname and fqdn on the box
    """
    logging.info('setting hostname to {0}'.format(hostname))
    cmd = 'echo "{hostname}" > /etc/hostname'
    # make it indempotent - if this hostname is already mapped to 127.0.0.1, 
    #  don't add another line to /etc/hosts
    hosts_lines = sudo('cat /etc/hosts', pty=True).split('\n')
    a = filter(lambda x: re.match('127\.0\.0\.1.+' + hostname, x), hosts_lines)
    dnsdn = None
    if len(a) == 0:
        dnsdn = run('dnsdomainname', pty=True) or 'localdomain'
        cmd += '; echo -e "\\n127.0.0.1    {hostname}.{domain} {hostname}" >> /etc/hosts'
    cmd += '; hostname $(cat /etc/hostname);'
    cmd = cmd.format(hostname=hostname, domain=dnsdn)
    logging.debug('running: {0}'.format(cmd))
    sudo(cmd)


###
### Helpers
###
@task
def get_status(box_id):
    """ Check that box is running and tests show "ok". Returns a boolean
    """
    cmd = "ec2-describe-instance-status {0}".format(box_id)
    result = local(cmd, capture=True)
    status = _grab_instance_line_and_split(result)
    ## check that we're even parsing correctly
    if len(status) < 7:
        logging.error('command: `{0}` returned: {1}'.format(
            cmd, result))
        return False
    ## now check the status
    if status[3] == "running" and status[5] == "ok" and status[6] == "ok":
        logging.info('Status ok')
        return True
    else:
        logging.info('Status not running or tests not passing')
        return False

@task
def get_public_dns_from_id(box_id):
    """ Finds the public domain name from AWS
        :box_id => the aws instance id
    """
    cmd = 'ec2-describe-instances {0}'.format(box_id)
    result = local(cmd, capture=True)
    status = _grab_instance_line_and_split(result)
    logging.info('box {0} is at domain name: {1}'.format(box_id, status[3]))
    return status[3]

def _grab_instance_line_and_split(output):
    """ Ignore irrelevant lines of output and split relevant line into list
    """
    lines = output.split('\n')
    tmp = filter(lambda x: x.startswith('INSTANCE'), lines)
    if len(tmp) == 0:
        return []
    return re.split('\s', tmp[0])
