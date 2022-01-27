
DIR=$(shell basename `pwd`)

N1=n1
N2=n2

all:
	@echo "Makefile rules:"
	@echo " * start         start environment"
	@echo " * stop          stop environment"
	@echo " * bash-n1       start a bash shell in node/container n1"
	@echo " * bash-n2       start a bash shell in node/container n2"
	@echo " * cli-n1        start an NSO CLI in node/container n1"
	@echo " * cli-n2        start an NSO CLI in node/container n2"
	@echo " * formarding    start sshuttle to forward tcp traffic destinated to 172.18.0.0/16 to the router container"

start: environment
	docker-compose up

stop:
	docker-compose down

bash-$(N1):
	docker exec -it $(DIR)_$(N1)_1 /bin/bash -c "cd /root/nso-project;/bin/bash"
bash-$(N2):
	docker exec -it $(DIR)_$(N2)_1 /bin/bash -c "cd /root/nso-project;/bin/bash"
bash-router:
	docker exec -it $(DIR)_router_1 /bin/bash -c "cd /root;/bin/bash"

cli-$(N1):
	docker exec -it $(DIR)_$(N1)_1 /bin/bash -lc "ncs_cli -u admin -C"
cli-$(N2):
	docker exec -it $(DIR)_$(N2)_1 /bin/bash -lc "ncs_cli -u admin -C"

forwarding:
	sshuttle -e 'ssh -q -o CheckHostIP=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null' -r root@localhost:2200 172.18.0.0/16

java-dbg-n1:
	ssh -L9001:localhost:9000 172.18.1.2 -l root
java-dbg-n2:
	ssh -L9002:localhost:9000 172.18.2.2 -l root

.PHONY: enviroment
environment: n1 n2

n1: pkgs
	mkdir n1
	cp hostsfile n1/.
	cp nct_known_hosts n1/.
	cp setup-n1.sh n1/setup.sh
	rsync -ra nso-project/ n1/.
	cp -rp pkgs/model-a n1/var/packages/.
	cd n1; ln -s var/packages .
	cd n1; ln -s var/state .
	cd n1; ln -s var/cdb ncs-cdb
n2: pkgs
	mkdir n2
	cp hostsfile n2/.
	cp nct_known_hosts n2/.
	cp setup-n2.sh n2/setup.sh
	rsync -ra nso-project/ n2/.
	cp -rp pkgs/model-a n2/var/packages/.
	cd n2; ln -s var/packages .
	cd n2; ln -s var/state .
	cd n2; ln -s var/cdb ncs-cdb

.PHONY: pkgs
pkgs:
	make -C pkgs/model-a/src all

.PHONY: clean
clean:
	rm -rf n1 n2
	make -C pkgs/model-a/src clean

