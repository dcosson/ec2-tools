###
### Configuration for the ec2-puppet fabfile
###
import logging
from fabric.api import env

# In particular, you should define:
# DEFAULT_AMI  # default amazon ami to use, so you don't have specify each time
# PUPPETMASTER_IP  # internal ip address for boxes to reach puppetmaster
# PUPPETMASTER_DNS  # public ip or domain to reach puppetmaster on the internet

# Optional
# logging.basicConfig(level=logging.DEBUG)  # whatever level you want
# env.user = 'ubuntu'  # default user for your ami
