ip route add 172.18.2.0/24 via 172.18.1.100
cat >> /etc/hosts <<EOL
172.18.2.2	n2
EOL
mkdir /root/.ssh
chmod 700 /root/.ssh
mv nct_known_hosts /root/.ssh/.
