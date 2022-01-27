# The order of packages is significant as there are dependencies between
# the packages. Typically generated namespaces are used by other packages.
SINGLE_PACKAGES =  model-a


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
	@echo "Current build: $(wildcard *-BUILD)"
	@echo "NSO major version: $(NSO_MAJOR_VERSION) ($(NSO_VERSION))"
	@echo
	@echo "Makefile rules:"
	@echo " * single        Setup a single node NSO system."
	@echo " * lsa           Setup an LSA NSO system with one CFS and two RFS nodes."
	@echo " * start         start environment"
	@echo " * stop          stop environment"
	@echo " * cli-<host>    start an NSO CLI in node/container <host>"

.PHONY: check-build
check-build:
	@if [ ! -e SINGLE-BUILD -a ! -e LSA-BUILD ]; then \
	  echo 'ERROR: You need to build before starting. Run "make single" or "make lsa" to build.'; \
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

.PHONY: build-pkgs
build-pkgs: pkg-repo/BUILT
pkg-repo/BUILT:
	for i in $(shell find pkg-repo -type d -maxdepth 1 -mindepth 1); do \
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
	rm -f SINGLE-BUILD LSA-BUILD
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
	ncs
	./initial_data/startup.sh


.PHONY: start-lsa
start-lsa:
	cd upper-nso;   NCS_IPC_PORT=4569 sname=upper-nso ncs -c ncs.conf
	cd lower-nso-1; NCS_IPC_PORT=4570 sname=lower-nso-1 ncs -c ncs.conf
	cd lower-nso-2; NCS_IPC_PORT=4571 sname=lower-nso-2 ncs -c ncs.conf
	initial_data/startup-lsa.sh

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
	-ncs --stop

.PHONY: stop-lsa
stop-lsa:
	-NCS_IPC_PORT=4569 ncs --stop
	-NCS_IPC_PORT=4570 ncs --stop
	-NCS_IPC_PORT=4571 ncs --stop

.PHONY: reset
reset:
	ncs-setup --reset

#
# CLI
#

.PHONY: cli cli-upper-nso cli-lower-nso-1 cli-lower-nso-2
cli:
	ncs_cli -u admin
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

