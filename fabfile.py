#!/usr/bin/env python
""" Fabric wrappers around EC2 Command Line Tools and other helper functions
 for bringing up boxes that are ready to be provisioned with puppet
 You need the EC2 command line tools installed and configured properly
"""
import logging
import time
import re

from fabric.api import task, local, run, sudo, env, settings, put

## General setup
logging.basicConfig(level=logging.DEBUG)
env.user = 'ubuntu'  # I only really use ubuntu boxes


###
### The tasks
###
@task
def create_instance(name,
                    ami_id=None,
                    box_type='t1.micro',
                    size_gb=8,
                    zone='us-east-1c',
                    key_pair='venmo_macbook_air_danny_rsa'):
    """ Create an ebs-backed instance, with hostname set to its EC2 Name tag
        :name => EC2 Name and hostname
    """
    ### Create the box
    ###   (some details are hard-coded for now, until I need to tweak them)
    ami_ubuntu_1004_32_bit = "ami-057bcf6c"
    params = {'ami_id': ami_id or ami_ubuntu_1004_32_bit, 'box_type': box_type,
        'size_gb': size_gb, 'zone': zone, 'hostname': name,
        'key_pair': 'venmo_macbook_air_danny_rsa'}
    cmd = "ec2-run-instances {ami_id} --instance-type {box_type} " \
        "--availability-zone {zone} --user-data 'hostname={hostname}' " \
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
    """ Creates an instance, waits for it come up, then sets the hostname
    """
    box_id = create_instance(name, **kwargs)
    ### Wait for box to come up and tests to pass
    logging.debug('checking status for box_id: {0}'.format(box_id))
    while True:
        logging.debug('waiting to come on line...')
        time.sleep(10)
        ok = get_status(box_id)
        if ok:
            break
    logging.info('box running!')

    ### set hostname & install puppet
    host = get_public_dns_from_id(box_id)
    with settings(host_string=host):
        set_hostname(name)
        sudo('apt-get update')
    return box_id


@task
def create_instance_puppet_agent(name,
                                 puppetmaster_ip,
                                 puppetmaster_dns,
                                 **kwargs):
    """ Create box that will run as puppet agent, install puppet, and register
        it with the puppetmaster

        :name => name & hostname of box
        :puppetmaster_ip => ip address where new box will be able to reach
            the puppetmaster server
        :puppetmaster_dns=> domain name where local box can ssh to
            the puppetmaster server
        :kwargs => passed through to the `create_instance` task
    """
    LOCAL_PUPPET_CONF = 'puppet/puppet.conf'
    box_id = create_instance_and_set_hostname(name, **kwargs)
    host = get_public_dns_from_id(box_id)
    with settings(host_string=host):
        install_puppet_agent(LOCAL_PUPPET_CONF, puppetmaster_ip)
        puppet_cert_handshake(puppetmaster_dns)
    return box_id


@task
def install_puppet_agent(local_puppet_conf, puppetmaster_ip):
    """ install puppet and set box up as a puppet agent
        :puppet_dir => local directory of where to find puppet.conf
    """
    sudo('apt-get install -y puppet')
    # put puppetmaster into the /etc/hosts file
    sudo('echo -e "\\n{0}    puppetmaster.$(dnsdomainname) puppetmaster puppet" ' \
         '>> /etc/hosts'.format(puppetmaster_ip))
    # clean out default puppet stuff since the agent doesn't need it
    sudo('rm -rf /etc/puppet/*')
    put(local_puppet_conf, '/etc/puppet/puppet.conf', use_sudo=True)


@task
def puppet_cert_handshake(puppetmaster_dns):
    """ do the master/agent cert handshake for setting up a new puppet agent
        :puppetmaster_dns => dns to reach the puppet master from local box
    """
    agent_fqdn = sudo('facter fqdn', pty=True)
    # initialize handshake
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
        logging.info('All good!')
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
