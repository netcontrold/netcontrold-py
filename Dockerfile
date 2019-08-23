FROM rhel7:latest
LABEL version=0.1
LABEL maintainer="Gowrishankar Muthukrishnan <gmuthukr@redhat.com>"

COPY dist/netcontrold-0.1.el7-1.noarch.rpm ./
RUN yum install -y --enablerepo="rhel-7-server-openstack-13-rpms" openvswitch && \
    yum install -y ./netcontrold-* && \
    yum clean all

ENTRYPOINT ["sh", "-c", "/usr/bin/ncd_ctl start && tail -f /var/log/ncd.log"]
