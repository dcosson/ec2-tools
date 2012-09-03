## EC2 Puppet Fabric

A work in progress - mostly just my own experiments, not sure how useful it actually is.

Some [fabric](http://fabfile.org) tasks around launching EC2 boxes set up as puppet agents.

Currently does the following:
* Creates new EC2 box (with `ec2-run-instances`)
* Sets its hostname (used by puppetmaster to identify nodes and know which catalog to send)
* installs `puppet`
* registers as agent (sends cert to the puppetmaster server and server signs it)
* Starts the puppet agent daemon (`sudo puppet agent`) to provision the new server

The idea is to run one command `fab create_instance_puppet_agent:yourbox` and get a new EC2 server that registers with your puppetmaster and then provisions itself with puppet.  Most of the individual steps can also be run separately, use `fab -l` to list available commands and `fab -d COMMANDNAME` to see full docstring.

You need EC2 Command Line Tools installed with the keys set up (run a command like `ec2-describe-instances` to test the setup).  Only tested on puppet 2.7 on Ubuntu at the moment.

There are a bunch of defaults that you can put in a `fab_conf.py` file so you don't have to type as much to run the commands - see the example file.
