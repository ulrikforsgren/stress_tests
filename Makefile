# The order of packages is significant as there are dependencies between
# the packages. Typically generated namespaces are used by other packages.
SINGLE_PACKAGES = \
    model-a\
    manual-ha\
    empty-template-service\
    empty-python-service\
    empty-java-service\
    template-service\
    python-service\
    java-service\
    router

ifeq "$(NCS_DIR)" ""
$(error NCS_DIR is not setup. Source ncsrc to setup NSO environment before proceeding)
endif

NSO_VERSION = $(shell ncs --version)
NSO_VER_MAJ = $(shell echo $(NSO_VERSION) | cut -f1 -d.)
NSO_VER_MIN = $(shell echo $(NSO_VERSION) | cut -f2 -d. | cut -f1 -d_)
NSO_MAJOR_VERSION = $(NSO_VER_MAJ).$(NSO_VER_MIN)

# Handle version dependent differencies
ifeq "$(NSO_MAJOR_VERSION)" "5.2"
LSA_NED=tailf-nso-nc-$(NSO_MAJOR_VERSION)
else ifeq "$(NSO_MAJOR_VERSION)" "5.3"
LSA_NED=tailf-nso-nc-$(NSO_MAJOR_VERSION)
else
LSA_NED=cisco-nso-nc-$(NSO_MAJOR_VERSION)
RFS_NED_OPTIONS=--lsa-lower-nso $(LSA_NED)
endif

.PHONY: all
all:
	@echo "Current build:     $(wildcard *-BUILD)"
	@echo "HA setup:          $(wildcard HA)"
	@echo "NSO major version: $(NSO_MAJOR_VERSION) ($(NSO_VERSION))"
	@echo
	@echo "Makefile rules:"
	@echo " * single        Setup a single node NSO system."
	@echo " * lsa           Setup an LSA NSO system with one CFS and two RFS nodes."
	@echo " * ha            Setup complementary nodes for HA."
	@echo " * start         start environment"
	@echo " * stop          stop environment"
	@echo " * cli-<host>    start an NSO CLI in node/container <host>"


.PHONY: check-build
check-build:
	@if [ ! -e SINGLE-BUILD -a ! -e LSA-BUILD ]; then \
	  echo 'ERROR: You need to build before starting. Run "make single" or "make lsa" to build.'; \
	  exit 1; \
        fi

.PHONY: check-ha
check-ha: check-build
	@if [ ! -e HA ]; then \
	  echo 'ERROR: Not built for HA Run "make ha" to setup complementary nodes.'; \
	  exit 1; \
	fi


.PHONY: single
single: SINGLE-BUILD packages ncs.conf venv initial-data

.PHONY: SINGLE-BUILD
SINGLE-BUILD:
	@if [ -e LSA-BUILD ]; then \
	  echo 'ERROR: Already built for LSA. Run "make clean single" to rebuild for single node.'; \
	  exit 1; \
        fi
	@touch SINGLE-BUILD


.PHONY: lsa
lsa: LSA-BUILD upper-nso lower-nso-1 lower-nso-2 venv

.PHONY: LSA-BUILD
LSA-BUILD:
	@if [ -e SINGLE-BUILD ]; then \
	  echo 'ERROR: Already built for single node. Run "make clean lsa" to rebuild for lsa.'; \
	  exit 1; \
        fi
	@touch LSA-BUILD

# Setup complementary high-availability node(s)
.PHONY: ha
ha: check-build
	@if [ ! -e HA ]; then \
	  if [ -e SINGLE-BUILD ]; then \
	    $(MAKE) ha-single; \
	  fi; \
	  touch HA; \
	fi

.PHONY: ha-single
ha-single:
	ln -sf ../pkg-repo/manual-ha packages/.
	. venv/bin/activate; ./xmlmerge.py ncs.conf enable-ha-n1.xml > ha-n1-tmp.xml
	mv ha-n1-tmp.xml ncs.conf
	cp initial_data/ha-config.xml ncs-cdb/.
	$(MAKE) follower/ncs.conf
	for i in $(SINGLE_PACKAGES); do \
	  ln -sf ../../pkg-repo/$${i} follower/packages/.; \
	done
	. venv/bin/activate; ./xmlmerge.py follower/ncs.conf enable-ha-n2.xml > ha-n2-tmp.xml
	mv ha-n2-tmp.xml follower/ncs.conf
	cp initial_data/ha-config.xml follower/ncs-cdb/.
	ln -s ../local-start-java-vm follower/.

.PHONY: ha-on
ha-on: check-ha
	@if [ -e SINGLE-BUILD ]; then \
	    $(MAKE) ha-on-single; \
	fi
	@$(MAKE) ha-status

.PHONY: ha-on-single
ha-on-single:
	echo "ha-config be-master" | NCS_IPC_PORT=4569 ncs_cli -u admin -C
	sleep 2
	echo "ha-config be-slave" | NCS_IPC_PORT=4579 ncs_cli -u admin -C

.PHONY: ha-off
ha-off: check-ha
	@if [ -e SINGLE-BUILD ]; then \
	    $(MAKE) ha-off-single; \
	fi
	@$(MAKE) ha-status

.PHONY: ha-off-single
ha-off-single:
	echo "ha-config be-none" | NCS_IPC_PORT=4569 ncs_cli -u admin -C
	echo "show ncs-state ha" | NCS_IPC_PORT=4569 ncs_cli -u admin -C

.PHONY: ha-status
ha-status: check-ha
	@if [ -e SINGLE-BUILD ]; then \
	    $(MAKE) ha-status-single; \
	fi

.PHONY: ha-status-single
ha-status-single:
	echo "show ncs-state ha" | NCS_IPC_PORT=4569 ncs_cli -u admin -C

.PHONY: build-pkgs
build-pkgs: pkg-repo/BUILT
pkg-repo/BUILT:
	for i in $(shell find pkg-repo -type d -maxdepth 1 -mindepth 1); do \
	  echo "==== Building $${i} ===="; \
	  $(MAKE) -C $${i}/src all || exit 1; \
	done
	touch pkg-repo/BUILT

.PHONY: venv
venv: venv/bin/activate
venv/bin/activate:
	python3 -m venv venv
	(. venv/bin/activate; python3 -m pip install -r requirements.txt)

#
# Single node
#

ncs.conf:
	ncs-setup --dest . --package cisco-ios-cli-3.0

follower/ncs.conf:
	mkdir follower; \
	cd follower; \
	ncs-setup --dest .

packages: build-pkgs
	mkdir -p packages
	for i in $(SINGLE_PACKAGES); do \
	  ln -sf ../pkg-repo/$${i} packages/.; \
	done

initial-data:
	cp initial_data/service-plan-notifications.xml ncs-cdb/.
	cp initial_data/global-settings.xml ncs-cdb/.
#
# LSA
#

upper-nso: build-pkgs
	ncs-setup --no-netsim --dest $@
	if [ -e nso-etc/$@/ncs.conf-$(NSO_MAJOR_VERSION) ]; then \
	cp nso-etc/$@/ncs.conf-$(NSO_MAJOR_VERSION) $@/ncs.conf; \
	else \
	cp nso-etc/$@/ncs.conf $@; \
	fi
	cp initial_data/global-settings.xml $@/ncs-cdb/.
	for i in $(CFS_PACKAGES); do \
	  ln -sf ../../pkg-repo/$${i} $@/packages/.; \
	done
	$(MAKE) $@/packages/rfs-vlan-ned
	ln -s ${NCS_DIR}/packages/lsa/$(LSA_NED) $@/packages/.

upper-nso/packages/rfs-vlan-ned:
	ncs-make-package --no-netsim --no-java --no-python \
	    $(RFS_NED_OPTIONS) \
	    --lsa-netconf-ned pkg-repo/rfs-vlan/src/yang \
	    --dest $@ --build $(@F)

lower-nso-%: build-pkgs
	ncs-setup --no-netsim --dest $@
	cp nso-etc/$@/ncs-cdb/devs.xml $@/ncs-cdb/.
	cp initial_data/global-settings.xml $@/ncs-cdb/.
	if [ -e nso-etc/$@/ncs.conf-$(NSO_MAJOR_VERSION) ]; then \
	cp nso-etc/$@/ncs.conf-$(NSO_MAJOR_VERSION) $@/ncs.conf; \
	else \
	cp nso-etc/$@/ncs.conf $@; \
	fi
	for i in $(RFS_PACKAGES); do \
	  ln -sf ../../pkg-repo/$${i} $@/packages/.; \
	done



.PHONY: clean
clean:
	rm -rf packages upper-nso lower-nso-1 lower-nso-2
	for i in $(shell find pkg-repo -type d -maxdepth 1 -mindepth 1); do \
	  $(MAKE) -C $${i}/src clean || exit 1; \
	done
	rm -f pkg-repo/BUILT
	rm -rf ncs-cdb state logs scripts target ncs.conf storedstate
	rm -rf README.ncs
	rm -rf __pycache__
	rm -f *.log
	rm -f SINGLE-BUILD LSA-BUILD HA
	rm -rf follower
	@echo "NOTE! Directory 'venv' is not removed."
	@echo "      It must be manually deleted to be rebuilt."

.PHONY: start
start: check-build
	@if [ -e SINGLE-BUILD ]; then \
	  $(MAKE) start-single; \
	fi
	@if [ -e LSA-BUILD ]; then \
	  $(MAKE) start-lsa; \
	fi

.PHONY: start-single
start-single:
	@if [ ! -e HA ]; then \
	  $(MAKE) start-single-noha; \
	else \
	  $(MAKE) start-single-ha; \
	fi

.PHONY: start-single-noha
start-single-noha:
	ncs
	./initial_data/startup.sh

.PHONY: start-single-ha
start-single-ha:
	NCS_IPC_PORT=4569 sname=n1 NCS_HA_NODE=n1 ncs -c ncs.conf
	NCS_IPC_PORT=4569 ./initial_data/startup.sh
	(cd follower; NCS_IPC_PORT=4579 sname=n2 NCS_HA_NODE=n2 ncs -c ncs.conf)
	NCS_IPC_PORT=4579 ./initial_data/startup.sh

cli-n1:
	NCS_IPC_PORT=4569 ncs_cli -u admin -C
cli-n2:
	NCS_IPC_PORT=4579 ncs_cli -u admin -C

.PHONY: start-lsa
start-lsa:
	cd upper-nso;   NCS_IPC_PORT=4569 sname=upper-nso ncs -c ncs.conf
	cd lower-nso-1; NCS_IPC_PORT=4570 sname=lower-nso-1 ncs -c ncs.conf
	cd lower-nso-2; NCS_IPC_PORT=4571 sname=lower-nso-2 ncs -c ncs.conf
	initial_data/startup-lsa.sh

.PHONY: start-refserver
start-refserver:
	./reference_tests/reference_server.py 2>/dev/null&
	echo "It is now started in the background."

.PHONY: stop-refserver
stop-refserver:
	pkill -f reference_server.py

.PHONY: stop
stop: check-build
	@if [ -e SINGLE-BUILD ]; then \
	  $(MAKE) stop-single; \
	fi
	@if [ -e LSA-BUILD ]; then \
	  $(MAKE) stop-lsa; \
	fi

.PHONY: stop-single
stop-single:
	@if [ ! -e HA ]; then \
	  $(MAKE) stop-single-noha; \
	else \
	  $(MAKE) stop-single-ha; \
	fi

.PHONY: stop-single-noha
stop-single-noha:
	-ncs --stop

.PHONY: stop-single-ha
stop-single-ha:
	-NCS_IPC_PORT=4569 ncs --stop
	-NCS_IPC_PORT=4579 ncs --stop


.PHONY: stop-lsa
stop-lsa:
	-NCS_IPC_PORT=4569 ncs --stop
	-NCS_IPC_PORT=4570 ncs --stop
	-NCS_IPC_PORT=4571 ncs --stop
	pNCS_IPC_PORT=4569 ncs --stop
	-NCS_IPC_PORT=4570 ncs --stop

.PHONY: reset
reset:
	ncs-setup --reset

#
# CLI
#

.PHONY: cli cli-ha cli-upper-nso cli-lower-nso-1 cli-lower-nso-2
cli:
	ncs_cli -u admin
cli-ha:
	NCS_IPC_PORT=4579 ncs_cli -C -u admin
cli-upper-nso: cli
cli-lower-nso-1:
	NCS_IPC_PORT=4570 ncs_cli -C -u admin
cli-lower-nso-2:
	NCS_IPC_PORT=4571 ncs_cli -C -u admin

.PHONY: test
test:
	@if [ -e SINGLE-BUILD ]; then \
	elif [ -e LSA-BUILD ]; then \
	fi

