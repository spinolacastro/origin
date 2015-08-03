#debuginfo not supported with Go
%global debug_package %{nil}
%global gopath      %{_datadir}/gocode
%global import_path github.com/openshift/origin
%global kube_plugin_path /usr/libexec/kubernetes/kubelet-plugins/net/exec/redhat~openshift-ovs-subnet
%global sdn_import_path github.com/openshift/openshift-sdn

# %commit and %ldflags are intended to be set by tito custom builders provided
# in the rel-eng directory. The values in this spec file will not be kept up to date.
%{!?commit:
%global commit 7a15ba79de721dcf70b2f062e43ec22a3b9de4d2
}
%global shortcommit %(c=%{commit}; echo ${c:0:7})
# OpenShift specific ldflags from hack/common.sh os::build:ldflags
%{!?ldflags:
%global ldflags -X github.com/openshift/origin/pkg/version.majorFromGit 1 -X github.com/openshift/origin/pkg/version.minorFromGit 0+ -X github.com/openshift/origin/pkg/version.versionFromGit v1.0.3-174-g7a15ba7 -X github.com/openshift/origin/pkg/version.commitFromGit 7a15ba7 -X github.com/GoogleCloudPlatform/kubernetes/pkg/version.gitCommit cd82144 -X github.com/GoogleCloudPlatform/kubernetes/pkg/version.gitVersion v1.0.0
}

Name:           openshift
# Version is not kept up to date and is intended to be set by tito custom
# builders provided in the rel-eng directory of this project
Version:        1.0.4
Release:        1%{?dist}
Summary:        Open Source Platform as a Service by Red Hat
License:        ASL 2.0
URL:            https://%{import_path}
ExclusiveArch:  x86_64
Source0:        https://%{import_path}/archive/%{commit}/%{name}-%{version}.tar.gz

BuildRequires:  systemd
BuildRequires:  golang >= 1.4


%description
%{summary}

%package master
Summary:        OpenShift Master
Requires:       %{name} = %{version}-%{release}
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

%description master
%{summary}

%package node
Summary:        OpenShift Node
Requires:       %{name} = %{version}-%{release}
Requires:       docker-io >= 1.6.2
Requires:       tuned-profiles-openshift-node
Requires:       util-linux
Requires:       socat
Requires:       nfs-utils
Requires(post): systemd
Requires(preun): systemd
Requires(postun): systemd

%description node
%{summary}

%package -n tuned-profiles-openshift-node
Summary:        Tuned profiles for OpenShift Node hosts
Requires:       tuned >= 2.3
Requires:       %{name} = %{version}-%{release}

%description -n tuned-profiles-openshift-node
%{summary}

%package clients
Summary:      Openshift Client binaries for Linux, Mac OSX, and Windows
BuildRequires: golang-pkg-darwin-amd64
BuildRequires: golang-pkg-windows-386

%description clients
%{summary}

%package dockerregistry
Summary:        Docker Registry v2 for OpenShift
Requires:       %{name} = %{version}-%{release}

%description dockerregistry
%{summary}

%package pod
Summary:        OpenShift Pod
Requires:       %{name} = %{version}-%{release}

%description pod
%{summary}

%package sdn-ovs
Summary:          OpenShift SDN Plugin for Open vSwitch
Requires:         openvswitch >= 2.3.1
Requires:         %{name}-node = %{version}-%{release}
Requires:         bridge-utils
Requires:         ethtool

%description sdn-ovs
%{summary}

%prep
%setup -q

%build

# Don't judge me for this ... it's so bad.
mkdir _build

# Horrid hack because golang loves to just bundle everything
pushd _build
    mkdir -p src/github.com/openshift
    ln -s $(dirs +1 -l) src/%{import_path}
popd


# Gaming the GOPATH to include the third party bundled libs at build
# time. This is bad and I feel bad.
mkdir _thirdpartyhacks
pushd _thirdpartyhacks
    ln -s \
        $(dirs +1 -l)/Godeps/_workspace/src/ \
            src
popd
export GOPATH=$(pwd)/_build:$(pwd)/_thirdpartyhacks:%{buildroot}%{gopath}:%{gopath}
# Build all linux components we care about
for cmd in openshift dockerregistry
do
        go install -ldflags "%{ldflags}" %{import_path}/cmd/${cmd}
done

# Build only 'openshift' for other platforms
GOOS=windows GOARCH=386 go install -ldflags "%{ldflags}" %{import_path}/cmd/openshift
GOOS=darwin GOARCH=amd64 go install -ldflags "%{ldflags}" %{import_path}/cmd/openshift

#Build our pod
pushd images/pod/
    go build -ldflags "%{ldflags}" pod.go
popd

%install

install -d %{buildroot}%{_bindir}
install -d %{buildroot}%{_datadir}/%{name}/{linux,macosx,windows}

# Install linux components
for bin in openshift dockerregistry
do
  echo "+++ INSTALLING ${bin}"
  install -p -m 755 _build/bin/${bin} %{buildroot}%{_bindir}/${bin}
done
# Install 'openshift' as client executable for windows and mac
install -p -m 755 _build/bin/openshift %{buildroot}%{_datadir}/%{name}/linux/oc
install -p -m 755 _build/bin/darwin_amd64/openshift %{buildroot}%{_datadir}/%{name}/macosx/oc
install -p -m 755 _build/bin/windows_386/openshift.exe %{buildroot}%{_datadir}/%{name}/windows/oc.exe
#Install openshift pod
install -p -m 755 images/pod/pod %{buildroot}%{_bindir}/

install -d -m 0755 %{buildroot}/etc/%{name}/{master,node}
install -d -m 0755 %{buildroot}%{_unitdir}
install -m 0644 -t %{buildroot}%{_unitdir} rel-eng/openshift-master.service
install -m 0644 -t %{buildroot}%{_unitdir} rel-eng/openshift-node.service

mkdir -p %{buildroot}%{_sysconfdir}/sysconfig
install -m 0644 rel-eng/openshift-master.sysconfig %{buildroot}%{_sysconfdir}/sysconfig/openshift-master
install -m 0644 rel-eng/openshift-node.sysconfig %{buildroot}%{_sysconfdir}/sysconfig/openshift-node

mkdir -p %{buildroot}%{_sharedstatedir}/%{name}

ln -s %{_bindir}/openshift %{buildroot}%{_bindir}/oc
ln -s %{_bindir}/openshift %{buildroot}%{_bindir}/oadm
ln -s %{_bindir}/openshift %{buildroot}%{_bindir}/kubectl

install -d -m 0755 %{buildroot}%{_prefix}/lib/tuned/openshift-node-{guest,host}
install -m 0644 tuned/openshift-node-guest/tuned.conf %{buildroot}%{_prefix}/lib/tuned/openshift-node-guest/
install -m 0644 tuned/openshift-node-host/tuned.conf %{buildroot}%{_prefix}/lib/tuned/openshift-node-host/
install -d -m 0755 %{buildroot}%{_mandir}/man7
install -m 0644 tuned/man/tuned-profiles-openshift-node.7 %{buildroot}%{_mandir}/man7/tuned-profiles-openshift-node.7

# Install sdn scripts
install -d -m 0755 %{buildroot}%{kube_plugin_path}
pushd _thirdpartyhacks/src/%{sdn_import_path}/ovssubnet/bin
   install -p -m 755 openshift-ovs-subnet %{buildroot}%{kube_plugin_path}/openshift-ovs-subnet
   install -p -m 755 openshift-sdn-kube-subnet-setup.sh %{buildroot}%{_bindir}/
popd
install -d -m 0755 %{buildroot}%{_prefix}/lib/systemd/system/openshift-node.service.d
install -p -m 0644 rel-eng/openshift-sdn-ovs.conf %{buildroot}%{_prefix}/lib/systemd/system/openshift-node.service.d/
install -d -m 0755 %{buildroot}%{_prefix}/lib/systemd/system/docker.service.d
install -p -m 0644 rel-eng/docker-sdn-ovs.conf %{buildroot}%{_prefix}/lib/systemd/system/docker.service.d/

# Install bash completions
install -d -m 755 %{buildroot}/etc/bash_completion.d/
install -p -m 644 rel-eng/completions/bash/* %{buildroot}/etc/bash_completion.d/

%files
%defattr(-,root,root,-)
%doc README.md LICENSE
%{_bindir}/openshift
%{_bindir}/oc
%{_bindir}/oadm
%{_bindir}/kubectl
%{_sharedstatedir}/%{name}
/etc/bash_completion.d/*

%files master
%defattr(-,root,root,-)
%{_unitdir}/openshift-master.service
%config(noreplace) %{_sysconfdir}/sysconfig/openshift-master
%config(noreplace) /etc/%{name}/master

%post master
%systemd_post %{basename:openshift-master.service}

%preun master
%systemd_preun %{basename:openshift-master.service}

%postun master
%systemd_postun


%files node
%defattr(-,root,root,-)
%{_unitdir}/openshift-node.service
%config(noreplace) %{_sysconfdir}/sysconfig/openshift-node
%config(noreplace) /etc/%{name}/node

%post node
%systemd_post %{basename:openshift-node.service}

%preun node
%systemd_preun %{basename:openshift-node.service}

%postun node
%systemd_postun

%files sdn-ovs
%defattr(-,root,root,-)
%{_bindir}/openshift-sdn-kube-subnet-setup.sh
%{kube_plugin_path}/openshift-ovs-subnet
%{_prefix}/lib/systemd/system/openshift-node.service.d/openshift-sdn-ovs.conf
%{_prefix}/lib/systemd/system/docker.service.d/docker-sdn-ovs.conf

%files -n tuned-profiles-openshift-node
%defattr(-,root,root,-)
%{_prefix}/lib/tuned/openshift-node-host
%{_prefix}/lib/tuned/openshift-node-guest
%{_mandir}/man7/tuned-profiles-openshift-node.7*

%post -n tuned-profiles-openshift-node
recommended=`/usr/sbin/tuned-adm recommend`
if [[ "${recommended}" =~ guest ]] ; then
  /usr/sbin/tuned-adm profile openshift-node-guest > /dev/null 2>&1
else
  /usr/sbin/tuned-adm profile openshift-node-host > /dev/null 2>&1
fi

%preun -n tuned-profiles-openshift-node
# reset the tuned profile to the recommended profile
# $1 = 0 when we're being removed > 0 during upgrades
if [ "$1" = 0 ]; then
  recommended=`/usr/sbin/tuned-adm recommend`
  /usr/sbin/tuned-adm profile $recommended > /dev/null 2>&1
fi

%files clients
%{_datadir}/%{name}/linux/oc
%{_datadir}/%{name}/macosx/oc
%{_datadir}/%{name}/windows/oc.exe

%files dockerregistry
%defattr(-,root,root,-)
%{_bindir}/dockerregistry

%files pod
%defattr(-,root,root,-)
%{_bindir}/pod

%changelog
* Mon Aug 03 2015 Unknown name 1.0.4
- bump version (spinolacastro@gmail.com)
- fix gendocs (deads@redhat.com)
- Added verification script for Swagger API object descriptions
  (skuznets@redhat.com)
- fail a build if there are no container statuses in the build pod
  (bparees@redhat.com)
- Add TLS support to docker client (cewong@redhat.com)
- UPSTREAM: 9844: EmptyDir volume SELinux support (pmorie@gmail.com)
- UPSTREAM: 9384: Make emptyDir volumes work for non-root UIDs
  (pmorie@gmail.com)
- UPSTREAM: 9844: revert origin e53e78f: Support emptyDir volumes for
  containers running as uid != 0 (pmorie@gmail.com)
- UPSTREAM: 9384: revert origin 4e5cebd: EmptyDir volumes for non-root 2/2
  (pmorie@gmail.com)
- UPSTREAM: 9384: revert origin b92d1c7: Handle SecurityContext correctly for
  emptyDir volumes (pmorie@gmail.com)
- UPSTREAM: 9844: revert origin 73b2454: fix emptyDir idempotency bug
  (pmorie@gmail.com)
- UPSTREAM: 9384: revert origin 2d83001: Make emptyDir work when SELinux is
  disabled (pmorie@gmail.com)
- UPSTREAM: 9384: revert origin ac5f35b: Increase clarity in empty_dir volume
  plugin (pmorie@gmail.com)
- UPSTREAM: 9384: revert origin 6e57b2d: Make empty_dir unit tests work with
  SELinux disabled (pmorie@gmail.com)
- export: Initialize map for image stream tags
  (kargakis@users.noreply.github.com)
- add Group kind (deads@redhat.com)
- add cli display coverage tests (deads@redhat.com)
- issue3894: update vagrant sections of contributing and readme doc to account
  for recent tweaks in runtime (gmontero@redhat.com)
- test-cmd.sh broken on Mac (ccoleman@redhat.com)
- Generated docs (ccoleman@redhat.com)
- Make naming less specific to OpenShift (ccoleman@redhat.com)
- buildchain: Refactor to use the graph library
  (kargakis@users.noreply.github.com)
- Updated update scripts to allow for a settable output directory
  (skuznets@redhat.com)
- Newapp: fix image stream name used in deployment trigger (cewong@redhat.com)
- Cleanup deployment describe slightly (ccoleman@redhat.com)
- Add app=<name> label to new-app groups (ccoleman@redhat.com)
- Release tar should contain smaller oc (ccoleman@redhat.com)
- Remove gographviz (kargakis@users.noreply.github.com)
- UPSTREAM: 9384: Make empty_dir unit tests work with SELinux disabled
  (pmorie@gmail.com)
- render graph using DOT (deads@redhat.com)
- clean up handling of no output builds (bparees@redhat.com)
- UPSTREAM: 11303: Add CA data to service account tokens if missing or
  different (jliggitt@redhat.com)
- Make 'make check' run the kubernetes unit tests (pmorie@gmail.com)
- Add information about copying kubernetes artifacts in to HACKING.md
  (pmorie@gmail.com)
- UPSTREAM: add dependencies for packages missing for upstream unit tests
  (pmorie@gmail.com)
- Add third party deps stub (pmorie@gmail.com)
- UPSTREAM: 11147: Fix TestRunExposeService (pmorie@gmail.com)
- Add upstream examples, README files, etc (pmorie@gmail.com)
- Add copy-kube-artifacts.sh script (pmorie@gmail.com)
- WIP: make hack/test-go.sh run upstream unit tests (pmorie@gmail.com)
- UPSTREAM: 11698: Make copy_test.go failures easier to debug
  (pmorie@gmail.com)
- Newapp: Use labels for deployment config and service selectors
  (cewong@redhat.com)
- reintroduce missing conversions for imagestream kind and lowercase build
  trigger types (bparees@redhat.com)
- UPSTREAM: 9009: Retry service account update when adding token reference
  (deads@redhat.com)
- UPSTREAM: revert da0a3d: 9009: Retry service account update when adding token
  reference (deads@redhat.com)
- Generated docs (ccoleman@redhat.com)
- update swagger spec to match (deads@redhat.com)
- Add Cache-Control header (spadgett@redhat.com)
- Update swagger spec (spadgett@redhat.com)
- fix colliding serial numbers in certs (deads@redhat.com)
- Update object-describer to v1.0.2 (jforrest@redhat.com)
- Move Build cancellation and Pod deletion logic to HandleBuild
  (nagy.martin@gmail.com)
- bump(github.com/openshift/source-to-image)
  587d0f0a63589436322ac2ba6e01abb2f98a8dae (cewong@redhat.com)
- Updated Swagger spec, added Swagger spec verification (skuznets@redhat.com)
- Add a 'rsh' command for simpler remote access (ccoleman@redhat.com)
- Fix incorrect ENV["VAGRANT_LIBVIRT_URI"] if statement which causes "Missing
  required arguments: libvirt_uri (ArgumentError)" (takayoshi@gmail.com)
- UPSTREAM: 11729: Make exec reusable (ccoleman@redhat.com)
- Print consistent output for oadm manage-node --list-pods (rpenta@redhat.com)
- oc volume will allow changing volume type in case of unabiguous mount-path
  (rpenta@redhat.com)
- UPSTREAM: <carry>: Correct v1 deep_copy_generated.go (pmorie@gmail.com)
- Fix for tito 0.6.0 (sdodson@redhat.com)
- add reconcile-cluster-roles command (deads@redhat.com)
- Customize the events table layout and styles for better readability on mobile
  devices. (sgoodwin@redhat.com)
- UPSTREAM: 11669: add non root marker to sc types (pweil@redhat.com)
- OS: validation of host network and host ports in the SCC. (pweil@redhat.com)
- handle kube resources in project request template (deads@redhat.com)
- Bug 1245455 - fixes duplicated search results with openshift namespace
  (contact@fabianofranz.com)
- Bug 1245447 - fixes template search (contact@fabianofranz.com)
- use env var for config arg value (pweil@redhat.com)
- Rolling updater enhancements (ironcladlou@gmail.com)
- output invalid config field name (deads@redhat.com)
- UPSTREAM: 7893: validation of host network and host ports in the SCC.
  (pweil@redhat.com)
- New-app: set name of image stream with --name argument (cewong@redhat.com)
- don't fail status on forbidden lists (deads@redhat.com)
- update forbidden error to include structured kind (deads@redhat.com)
- Adding kubectl symlink for atomic host compatibility (bleanhar@redhat.com)
- Diff whole template for deployment config changes (ironcladlou@gmail.com)
- add tls termination type to printer and describer (pweil@redhat.com)
- new-app search/list (contact@fabianofranz.com)
- make oc status output describeable (deads@redhat.com)
- Allow registry client to work with registries that don't implement
  repo/tag/[tag] (cewong@redhat.com)
- do not use vagrant shared dir for volumes (pweil@redhat.com)
- do not use vagrant shared dir for volumes (pweil@redhat.com)
- Don't handle errors for dcs on retry failures
  (kargakis@users.noreply.github.com)
- add revision info to build descriptions (bparees@redhat.com)
- make fake client thread-safe (deads@redhat.com)
- UPSTREAM: 11597: make fake client thread-safe (deads@redhat.com)
- Refine canary text a bit more (ccoleman@redhat.com)
- Line up breadcrumbs and content on create from template page
  (spadgett@redhat.com)
- UPSTREAM: 10062: Rolling updater enhancements (ironcladlou@gmail.com)
- UPSTREAM: 10062: revert origin 316c2e84783fdb93450865eb8801f9d4dbe1f79c:
  support acceptance check in rolling updater (ironcladlou@gmail.com)
- Defer to Kubernetes factory where appropriate
  (kargakis@users.noreply.github.com)
- add dueling rc warning (deads@redhat.com)
- add graph markers (deads@redhat.com)
- Show more detail on browse image streams page (spadgett@redhat.com)
- expose: Default to the service generator when not exposing services
  (kargakis@users.noreply.github.com)
- Minor fixes to deployment README (rhcarvalho@gmail.com)
- Add canary doc (ccoleman@redhat.com)
- Deployment examples (ccoleman@redhat.com)
- Route should default to name, not serviceName (ccoleman@redhat.com)
- Fix nodeSelector enforcement by the kubelet (jliggitt@redhat.com)
- Fix errors creating from source in UI (spadgett@redhat.com)
- UPSTREAM: 10647 (carry until 10656): increase Kubelet timeouts to 1 hour
  (agoldste@redhat.com)
- Remove generated name from container ports (jliggitt@redhat.com)
- status: Warn for circular deps in buildConfigs
  (kargakis@users.noreply.github.com)
- cluster groups proposal (deads@redhat.com)
- Handle unrecognized types in DataService.createList() (spadgett@redhat.com)
- Default DNS name should change (ccoleman@redhat.com)
- Remove 12MB from the oc binary (ccoleman@redhat.com)
- react to gonum/graph rebase (deads@redhat.com)
- bump(github.com/gonum/graph)bde6d0fbd9dec5a997e906611fe0364001364c41
  (deads@redhat.com)
- remove auto build triggering and make jenkins auto deploy work
  (bparees@redhat.com)
- always show markers is oc status (deads@redhat.com)
- oc exec upgrade.md (deads@redhat.com)
- examples/sample-app: Use the registry kubeconfig, not master
  (walters@verbum.org)
- Test resource builder file extensions (jliggitt@redhat.com)
- Duplicate serials were being handed out because objects were copied
  (ccoleman@redhat.com)
- Move NoNamespaceKeyFunc into origin (jliggitt@redhat.com)
- UPSTREAM: revert 6cc0c51: Ensure no namespace on create/update root scope
  types (jliggitt@redhat.com)
- Describe security in readme (ccoleman@redhat.com)
- UPSTREAM: carry: support pointing oc exec to old openshift server
  (deads@redhat.com)
- UPSTREAM: 11333: pass along status errors for upgrades (deads@redhat.com)
- Update oc logs examples and docs (kargakis@users.noreply.github.com)
- make claim name parameterized (bparees@redhat.com)
- UPSTREAM: 10866: don't check extension for single files (jliggitt@redhat.com)
- fix racy SAR test (deads@redhat.com)
- clean up jenkins example (bparees@redhat.com)
- Web Console: Handle docker and custom builder strategy in templates
  (spadgett@redhat.com)
- update policy for pods/exec (deads@redhat.com)
- allow multiple edges of different kinds between nodes (deads@redhat.com)
- [docs] group cli commands; add missing ones (tnguyen@redhat.com)
- Output emptyDir notice to standard error (nagy.martin@gmail.com)
- Fix command descriptions and alignment (ccoleman@redhat.com)
- Run hack/test-assets first and fail if error (ccoleman@redhat.com)
- Completion and doc updates (ccoleman@redhat.com)
- Refactor for printer/namespace changes (ccoleman@redhat.com)
- Update completions (ccoleman@redhat.com)
- Don't print subcommands info (ccoleman@redhat.com)
- Print the version of the master and node on start (ccoleman@redhat.com)
- Provide a way to get the exact IP used by the master (ccoleman@redhat.com)
- Use containerized builds (ccoleman@redhat.com)
- UPSTREAM: <carry>: Leave v1beta3 enabled for now (ccoleman@redhat.com)
- UPSTREAM: 10024: add originator to reflector logging (deads@redhat.com)
- UPSTREAM: 9384: Increase clarity in empty_dir volume plugin
  (pmorie@gmail.com)
- UPSTREAM: 9384: Fixes for empty_dir merge problem (pmorie@gmail.com)
- UPSTREAM: 10841: Default --ignore-not-found to true for delete --all
  (jliggitt@redhat.com)
- UPSTREAM: <carry>: Add deprecated fields to migrate 1.0.0 k8s v1 data
  (jliggitt@redhat.com)
- UPSTREAM: 9971: add imports for map conversion types (bparees@redhat.com)
- UPSTREAM: 9009: Retry service account update when adding token reference
  (deads@redhat.com)
- UPSTREAM: 5093: adding downward api volume plugin (salvatore-
  dario.minonne@amadeus.com)
- UPSTREAM: 8890: Allowing ActiveDeadlineSeconds to be updated for a pod
  (abhgupta@redhat.com)
- UPSTREAM: 6649: Add CephFS volume plugin (deads@redhat.com)
- UPSTREAM: 9976: search for mount binary in hostfs (ccoleman@redhat.com)
- UPSTREAM: 9976: nsenter path should be relative (ccoleman@redhat.com)
- UPSTREAM: 8530: GCEPD mounting on Atomic (deads@redhat.com)
- UPSTREAM: <carry>: Enable LimitSecretReferences in service account admission
  (jliggitt@redhat.com)
- UPSTREAM: <none>: Suppress aggressive output of warning (ccoleman@redhat.com)
- UPSTREAM: <none>: Hack date-time format on *util.Time (ccoleman@redhat.com)
- UPSTREAM: <carry>: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: 9844: fix emptyDir idempotency bug (deads@redhat.com)
- UPSTREAM: 9384: Handle SecurityContext correctly for emptyDir volumes
  (pmorie@gmail.com)
- UPSTREAM: 9384: Make emptyDir work when SELinux is disabled
  (pmorie@gmail.com)
- UPSTREAM: 9384: EmptyDir volumes for non-root 2/2 (deads@redhat.com)
- UPSTREAM: 9844: Support emptyDir volumes for containers running as uid != 0
  (deads@redhat.com)
- UPSTREAM: 9321: update describer for dockercfg secrets (deads@redhat.com)
- UPSTREAM: 9971: generated conversion updates (deads@redhat.com)
- UPSTREAM: 10636(extra): patch to fix kubelet startup (deads@redhat.com)
- UPSTREAM: <carry>: Allow pod start to be delayed in Kubelet
  (ccoleman@redhat.com)
- UPSTREAM: 10636: Split kubelet server initialization for easier reuse
  (deads@redhat.com)
- UPSTREAM: 10635: Cloud provider should return an error (deads@redhat.com)
- UPSTREAM: 9870: Allow Recyclers to be configurable (deads@redhat.com)
- UPSTREAM: 7893: scc allocation interface methods (deads@redhat.com)
- UPSTREAM: 10062: support acceptance check in rolling updater
  (deads@redhat.com)
- UPSTREAM: <carry>: implement a generic webhook storage (ccoleman@redhat.com)
- UPSTREAM: <carry>: Ensure no namespace on create/update root scope types
  (jliggitt@redhat.com)
- UPSTREAM: 8607: service account groups (deads@redhat.com)
- UPSTREAM: 9472: expose name validation method (deads@redhat.com)
- UPSTREAM: 7893: scc (deads@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):v1.0.0 (ccoleman@redhat.com)
- issue2740: updates to debugging doc for SELinux intermittent label issue
  (gmontero@redhat.com)
- status to indicate resources with broken secret/SA refs (deads@redhat.com)
- add graph analysis helpers (deads@redhat.com)
- issue1875: make the force pull option configurable in the sti build strategy
  definition; various upstream documentation clarifications / enhancements;
  comments around reqs for coding/testing changes that run in the builder pod;
  fixes after merging (changes lost); incorporate comments from Ben
  (gmontero@redhat.com)
- display standalone rcs (deads@redhat.com)
- Split oc and gitserver into their own binaries (ccoleman@redhat.com)
- Fix help message for client-certificate (chmouel@redhat.com)
- show standalone pods that back services (deads@redhat.com)
- suggest oc status from new-app (deads@redhat.com)
- Group commands in oadm for ease of use (rpenta@redhat.com)
- fix mutex for projectstatus (deads@redhat.com)
- README for hacking CLI commands (contact@fabianofranz.com)
- Show command to load templates on "Add to Project" page (spadgett@redhat.com)
- deploy: --enable-triggers should be used alone
  (kargakis@users.noreply.github.com)
- Clarify policy command on all projects page (spadgett@redhat.com)
- Added test for external kube proxied watches (skuznets@redhat.com)
- Issue 3502 - removing label propagation to build pods in build controller.
  (maszulik@redhat.com)
- LDAP password authenticator (jliggitt@redhat.com)
- Add scala source detector (jatescher@gmail.com)
- show RCs for services in oc status (deads@redhat.com)
- bump(github.com/openshift/source-to-image)
  72ed2c7edc4c4e03d490716404a25a6b7a15c890 (cewong@redhat.com)
- Handle "" for service.spec.portalIP on overview page (spadgett@redhat.com)
- return api error for privilege escalation attempt (deads@redhat.com)
- parallel resource lists for status (deads@redhat.com)
- Defer closing resp.Body after issuing an HTTP request
  (kargakis@users.noreply.github.com)
- UPSTREAM: 10024: add originator to reflector logging (deads@redhat.com)
- bump(github.com/vjeantet/asn1-ber): 85041cd0f4769ebf4a5ae600b1e921e630d6aff0
  (jliggitt@redhat.com)
- bump(github.com/vjeantet/ldapserver):
  5700661e721f508db936af42597a254c4ea6aea4 (jliggitt@redhat.com)
- bump(gopkg.in/asn1-ber.v1): 9eae18c3681ae3d3c677ac2b80a8fe57de45fc09
  (jliggitt@redhat.com)
- bump(github.com/go-ldap/ldap): 83e65426fd1c06626e88aa8a085e5bfed0208e29
  (jliggitt@redhat.com)
- Simplify rollback arguments (ironcladlou@gmail.com)
- Added test cases for HandleBuildPodDeletion and HandleBuildDeletion methods
  in build controller. (maszulik@redhat.com)
- refactor internal build api to match v1 (bparees@redhat.com)
- Docker registry client: handle [registry]/[name] specs (cewong@redhat.com)
- scaler: Sync with upstream behavior (kargakis@users.noreply.github.com)
- add masterCA to SA token controller (deads@redhat.com)
- Update headers and breadcrumbs to match button text (spadgett@redhat.com)
- Set expanded property on ng-repeat child scope for tasks
  (spadgett@redhat.com)
- Expose oapi (jliggitt@redhat.com)
- Vagrantfile: enable running on remote libvirtd (lmeyer@redhat.com)
- Bug 1232177 - handle mutually exclusive flags on oc process
  (contact@fabianofranz.com)
- add kubectl patch (deads@redhat.com)
- Sync .jshint options between root .jshintrc & test/.jshintrc, then fix
  outstanding errors (admin@benjaminapetersen.me)
- indicate builds that can't push (deads@redhat.com)
- UPSTREAM: 9384: Increase clarity in empty_dir volume plugin
  (pmorie@gmail.com)
- Awkward text wrapping on overview page (jhadvig@redhat.com)
- UPSTREAM: 9384: Fixes for empty_dir merge problem (pmorie@gmail.com)
- Add link to dismiss builds from overview (spadgett@redhat.com)
- UPSTREAM: 10841: Default --ignore-not-found to true for delete --all
  (jliggitt@redhat.com)
- [RPMs] Add nfs-utils to openshift-node requires (sdodson@redhat.com)
- Add 1.0.0 k8s v1 compatibility test (jliggitt@redhat.com)
- UPSTREAM: Carry: Add deprecated fields to migrate 1.0.0 k8s v1 data
  (jliggitt@redhat.com)
- Fix confusing output when cancelling deployments (ironcladlou@gmail.com)
- Remove unused function in CatalogImagesController (spadgett@redhat.com)
- Remove selection highlighting when sidebar hidden (spadgett@redhat.com)
- Remove "There is no service" message from overview (spadgett@redhat.com)
- Updating sti-image-builder with latest s2i (maszulik@redhat.com)
- run e2e cleanup as system:admin (deads@redhat.com)
- bump(github.com/openshift/source-to-
  image):e28fc867a72a6f2d1cb9898e0ce47c70e26909eb (maszulik@redhat.com)
- Clean-up desired replicas annotation for a complete deployment
  (kargakis@users.noreply.github.com)
- UPSTREAM: 9971: add imports for map conversion types (bparees@redhat.com)
- UPSTREAM: 9009: Retry service account update when adding token reference
  (deads@redhat.com)
- UPSTREAM: 5093: adding downward api volume plugin (salvatore-
  dario.minonne@amadeus.com)
- UPSTREAM: 8890: Allowing ActiveDeadlineSeconds to be updated for a pod
  (abhgupta@redhat.com)
- Avoid flicker on overview page when scaling (spadgett@redhat.com)
- Cleaned CONTRIBUTING.adoc and added information about problems with vagrant's
  synced folders. (maszulik@redhat.com)
- Image pruning improvements (agoldste@redhat.com)
- make imagestreamtag usage consistent (deads@redhat.com)
- prevent skydns metrics panic (deads@redhat.com)
- DeepCopy in Scheme (deads@redhat.com)
- update conversion/deep-copy generator (deads@redhat.com)
- NewProxier port range (deads@redhat.com)
- swagger API changes (deads@redhat.com)
- boring refactors (deads@redhat.com)
- UPSTREAM: 6649: Add CephFS volume plugin (deads@redhat.com)
- UPSTREAM: search for mount binary in hostfs (ccoleman@redhat.com)
- UPSTREAM: nsenter path should be relative (ccoleman@redhat.com)
- UPSTREAM: Run had invalid arguments (ccoleman@redhat.com)
- UPSTREAM: 8530: GCEPD mounting on Atomic (deads@redhat.com)
- UPSTREAM: 10169: Work around for PDs stop mounting after a few hours issue
  (deads@redhat.com)
- UPSTREAM: Enable LimitSecretReferences in service account admission
  (jliggitt@redhat.com)
- UPSTREAM: Hack date-time format on *util.Time (ccoleman@redhat.com)
- UPSTREAM: Suppress aggressive output of warning (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: 9844: fix emptyDir idempotency bug (deads@redhat.com)
- UPSTREAM: MISSING PULL: Handle SecurityContext correctly for emptyDir volumes
  (pmorie@gmail.com)
- UPSTREAM: MISSING PULL: Make emptyDir work when SELinux is disabled
  (pmorie@gmail.com)
- UPSTREAM: 9384: EmptyDir volumes for non-root 2/2 (deads@redhat.com)
- UPSTREAM: 9844: Support emptyDir volumes for containers running as uid != 0
  (deads@redhat.com)
- UPSTREAM: kube: update describer for dockercfg secrets (deads@redhat.com)
- UPSTREAM: 9971: generated conversion updates (deads@redhat.com)
- UPSTREAM: patch to fix kubelet startup (deads@redhat.com)
- UPSTREAM: fix SCC printers (deads@redhat.com)
- UPSTREAM: Allow pod start to be delayed in Kubelet (ccoleman@redhat.com)
- UPSTREAM: 10636: Split kubelet server initialization for easier reuse
  (deads@redhat.com)
- UPSTREAM: 10635 Cloud provider should return an error (deads@redhat.com)
- UPSTREAM: 9870 Allow Recyclers to be configurable (deads@redhat.com)
- UPSTREAM: scc allocation interface methods (deads@redhat.com)
- UPSTREAM: 10062 support acceptance check in rolling updater
  (deads@redhat.com)
- UPSTREAM: implement a generic webhook storage (ccoleman@redhat.com)
- UPSTREAM: Ensure no namespace on create/update root scope types
  (jliggitt@redhat.com)
- UPSTREAM: 8607 service account groups (deads@redhat.com)
- UPSTREAM: kube: expose name validation method (deads@redhat.com)
- UPSTREAM: Make util.Empty public (ccoleman@redhat.com)
- UPSTREAM: 7893 scc (deads@redhat.com)
- UPSTREAM: 7893 scc design (deads@redhat.com)
- UPSTREAM: Add "Info" to go-restful ApiDecl (ccoleman@redhat.com)
- UPSTREAM: Handle missing resolv.conf (ccoleman@redhat.com)
- UPSTREAM: Disable systemd activation for DNS (ccoleman@redhat.com)
- bump(github.com/elazarl/go-bindata-
  assetfs):3dcc96556217539f50599357fb481ac0dc7439b9 (deads@redhat.com)
- bump(github.com/syndtr/gocapability/capability):8e4cdcb3c22b40d5e330ade0b68cb
  2e2a3cf6f98 (deads@redhat.com)
- bump(github.com/miekg/dns):c13058f493c3756207ced654dce2986e812f2bcf
  (deads@redhat.com)
- bump(github.com/spf13/pflag): 381cb823881391d5673cf2fc41e38feba8a8e49a
  (jliggitt@redhat.com)
- bump(github.com/spf13/cobra): a8f7f3dc25e03593330100563f6c392224221899
  (jliggitt@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):96828f203c8d960bb7a5ad649d1f3
  8f77ae8910f (deads@redhat.com)
- edit: Default to notepad for Windows and env renaming
  (kargakis@users.noreply.github.com)
- describe: Use spec.replicas when describing a deployment
  (kargakis@users.noreply.github.com)
- oc volume fixes (rpenta@redhat.com)
- Clean up to status output for ports and messages (ccoleman@redhat.com)
- Fix database service name copy&paste mistake (nagy.martin@gmail.com)
- Change our example templates to use ReadWriteOnce access modes
  (nagy.martin@gmail.com)
- Update readme to indicate docker 1.7 is broken (ccoleman@redhat.com)
- Restore failed initial deployment events (ironcladlou@gmail.com)
- Give cap_sys_net_bind to openshift binary (ccoleman@redhat.com)
- Support quay.io by allowing cookies on connect (ccoleman@redhat.com)
- further doc corrections/clarifications based on exercising *-ex; update
  .gitignore for .project; incorporate Ben's suggestions and Clayton's
  clarifications; general minor cleanup; fix typo (gmontero@redhat.com)
- Stop defaulting to Recreate deployment strategy (jliggitt@redhat.com)
- Add EXPOSE to our public Dockerfile (ccoleman@redhat.com)
- Refactored the use of restful.Container.Handle() method (skuznets@redhat.com)
- Stop creating deployments with recreate strategy (jliggitt@redhat.com)
- sample that uses direct docker pullspec for builder image
  (bparees@redhat.com)
- Don't produce events when initial deployment fails (ironcladlou@gmail.com)
- refactor graph veneers (deads@redhat.com)
- Added healthz endpoint to OpenShift (steve.kuznetsov@gmail.com)
- deploy: Remove extra newline when describing deployments
  (kargakis@users.noreply.github.com)
- deploy: Better message (kargakis@users.noreply.github.com)
- Making build logs error msgs more clear (j.hadvig@gmail.com)
- new-app: Don't swallow error (kargakis@users.noreply.github.com)
- sample-app: Show real output from oadm registry
  (kargakis@users.noreply.github.com)
- Fix for https://github.com/openshift/origin/issues/3446 (sgoodwin@redhat.com)
- Look for deployer label when filtering pods on overview page
  (spadgett@redhat.com)
- make test-cmd RCs non-conflicting (deads@redhat.com)
- Remove ellipses from links and buttons (spadgett@redhat.com)
- Wrapped tile content on builds and pods pages into 2 column layout for better
  presentation by using available space Update UI screenshots for browse builds
  and pods pages (sgoodwin@redhat.com)
- Avoid warning icon flicker on browse deployments page (spadgett@redhat.com)
- Remove v1beta1 annotation/label mapping (ironcladlou@gmail.com)
- update host name section (pweil@redhat.com)
- Reorganized master code (steve.kuznetsov@gmail.com)
- Use relative URIs in create flow links (spadgett@redhat.com)
- filter the pods the build controller looks at (bparees@redhat.com)
- add graph testing helpers (deads@redhat.com)
- Tweak headings and add separator on create page (spadgett@redhat.com)
- Make \w special character in template expression behave like PCRE
  (mfojtik@redhat.com)
- log event for invalid output error (bparees@redhat.com)
- Bug 1223252: UPSTREAM: label: Invalidate empty or invalid value labels
  (kargakis@users.noreply.github.com)
- MySQL/Wordpress on NFS PVs (mturansk@redhat.com)
- Introduces auto-generation of CLI documents (contact@fabianofranz.com)
- Show namespace on project settings page (spadgett@redhat.com)
- Newapp: expose multiple ports in generated services (cewong@redhat.com)
- Add API version and kind to POST request content (spadgett@redhat.com)
- Fix deployment scaling race in test-cmd.sh (ironcladlou@gmail.com)
- allow http proxy env variables to be set in privileged sti container
  (bparees@redhat.com)
- More robust websocket error handling (spadgett@redhat.com)
- Correct registry auth for pruning (agoldste@redhat.com)
- Add image pruning e2e test (agoldste@redhat.com)
- require required fields in build objects (deads@redhat.com)
- remove dead build etcd package (deads@redhat.com)
- Allow private network to be used locally (ccoleman@redhat.com)
- Adjust examples indentation (contact@fabianofranz.com)
- Adjust 'kubectl config' examples to 'oc config' (contact@fabianofranz.com)
- Updated bash completion files (contact@fabianofranz.com)
- UPSTREAM: fixes kubectl config set-credentials examples
  (contact@fabianofranz.com)
- Remove `width: 100%%` from tile class (spadgett@redhat.com)
- Remove some pointless deployment logging (ironcladlou@gmail.com)
- Issue 3391 - allow optional image output for custom builder.
  (maszulik@redhat.com)
- Use a predictable tempdir naming convention (ironcladlou@gmail.com)
- add pod and rc spec nodes (deads@redhat.com)
- update prune error message to mention --confirm (chmouel@enovance.com)
- Fix typos in the repo (rpenta@redhat.com)
- elminate internal json tags forever (deads@redhat.com)
- Added support for multiple roles in oc secrets add
  (steve.kuznetsov@gmail.com)
- Correct Docker image Config type (agoldste@redhat.com)
- add warning for missing security allocator (deads@redhat.com)
- Add verification of generated content to make test (jliggitt@redhat.com)
- Fixed routes from root (steve.kuznetsov@gmail.com)
- Deflake TestBasicGroupManipulation (jliggitt@redhat.com)
- Allow who-can to check cluster-level access (jliggitt@redhat.com)
- make conversions convert and validation validate (deads@redhat.com)
- Always do a canary check during deployment (ironcladlou@gmail.com)
- More e2e-docker fixes (agoldste@redhat.com)
- Prevent long unbroken words from extending outside tile boundaries
  (spadgett@redhat.com)
- Fix typo (rhcarvalho@gmail.com)
- wait for imagestreamtags before requesting them (deads@redhat.com)
- validate extended args in config (deads@redhat.com)
- Warn user when using EmptyDir volumes (nagy.martin@gmail.com)
- Add EmptyDir volumes for new-app containers (nagy.martin@gmail.com)
- Clean up residual volume mounts from e2e-docker (agoldste@redhat.com)
- Newapp: Allow Docker FROM in Dockerfile to point to an image stream or
  invalid image (cewong@redhat.com)
- Split java console into separate package (jliggitt@redhat.com)
- bump(github.com/elazarl/go-bindata-assetfs):
  3dcc96556217539f50599357fb481ac0dc7439b9 (jliggitt@redhat.com)
- Use correct images for test-cmd (agoldste@redhat.com)
- Use correct images for e2e-docker (agoldste@redhat.com)
- Fix volume dir label for e2e-docker (agoldste@redhat.com)
- split graph package (deads@redhat.com)
- Adding rhel7 based origin-base Dockerfile (j.hadvig@gmail.com)
- dockercfg secret controllers shouldn't fail on NotFound deletes
  (deads@redhat.com)
- Update bash autocompletions (jliggitt@redhat.com)
- bump(github.com/spf13/cobra): a8f7f3dc25e03593330100563f6c392224221899
  (jliggitt@redhat.com)
- bump(github.com/spf13/pflag): 381cb823881391d5673cf2fc41e38feba8a8e49a
  (jliggitt@redhat.com)
- Remove duplicated template (rhcarvalho@gmail.com)
- Fix README.md markdown formatting (rhcarvalho@gmail.com)
- Remove imagemin step from asset build (jliggitt@redhat.com)
- bump(github.com/openshift/source-to-
  image):358cdb59db90b920e90a5f9a952ef7a3e11df3ad (bparees@redhat.com)
- sti to s2i (bparees@redhat.com)
- Show namespace, verb, resource for 'oadm policy who-can' cmd
  (rpenta@redhat.com)
- 'oc volume' test cases and fixes (rpenta@redhat.com)
- Updated 'oc env' help message (rpenta@redhat.com)
- Add policy cache wait in build admission integration tests
  (jliggitt@redhat.com)
- Template and image catalog updates (spadgett@redhat.com)
- defend against new-project racers (deads@redhat.com)
- Remove error when tracking tag target isn't found (agoldste@redhat.com)
- New-app: Expose ports specified in source Dockerfile (cewong@redhat.com)
- Add asset failure debugging (jliggitt@redhat.com)
- Make emptyDir work when SELinux is disabled (pmorie@gmail.com)
- Not beta! (ccoleman@redhat.com)
- fixed bash error (mturansk@redhat.com)
- fixed typo in script name (mturansk@redhat.com)
- fixed plugin init (mturansk@redhat.com)
- Add descriptions to our core objects and fix typos (ccoleman@redhat.com)
- Filter builds by completion rather than creation time on overview page
  (spadgett@redhat.com)
- add test for old config compatibility (deads@redhat.com)
- only handleErr on last retry failure (bparees@redhat.com)
- Now at one dot oh (ccoleman@redhat.com)
- bump(github.com/openshift/openshift-
  sdn/ovssubnet):cdd9955dc602abe8ef2d934a3c39417375c486c6 (rchopra@redhat.com)
- UPSTREAM: Ensure service account does not exist before deleting added/updated
  tokens (jliggitt@redhat.com)
- UPSTREAM: Add logging for invalid JWT tokens (jliggitt@redhat.com)
- Make etcd example more resilient to failure (mfojtik@redhat.com)
- new-app: Don't set spec.tags in output streams
  (kargakis@users.noreply.github.com)
- Bug 1232694 - Make the secret volume for push/pull secrets unique
  (mfojtik@redhat.com)
- use cookies for sticky sessions on http based routes (pweil@redhat.com)
- bump(github.com/openshift/openshift-
  sdn/ovssubnet):2bf8606dd9e0d5c164464f896e2223431f4b5099 (rchopra@redhat.com)
- Minor fixup to profiling instructions (ccoleman@redhat.com)
- Chmod hack/release.sh (ccoleman@redhat.com)
- UPSTREAM: fix emptyDir idempotency bug (pmorie@gmail.com)
- DeepCopy for util.StringSet (ccoleman@redhat.com)
- UPSTREAM: Make util.Empty public (ccoleman@redhat.com)
- UPSTREAM: use api.Scheme.DeepCopy() (ccoleman@redhat.com)
- Update default hostnames in cert (jliggitt@redhat.com)
- changed Recycler config for OS and added custom script for scrubbing in
  origin image (mturansk@redhat.com)
- Remove cached docker client repo on error (agoldste@redhat.com)
- update secret commands to give usage errors (deads@redhat.com)
- eliminate extra policy casting (deads@redhat.com)
- make policy interfaces (deads@redhat.com)
- switch policy types to map to pointers (deads@redhat.com)
- Prevent local fragment from being sent to a remote server
  (jliggitt@redhat.com)
- Properly handle Dockerfile build with no newline at the end
  (cewong@redhat.com)
- Validate redirect_uri doesn't contain path traversals (jliggitt@redhat.com)
- Add documentation on how to profile OpenShift (ccoleman@redhat.com)
- UPSTREAM: Allow recyclers to be configurable (mturansk@redhat.com)
- Re-enable timeout of -1 (no timeout) (jliggitt@redhat.com)
- UPSTREAM: Handle SecurityContext correctly for emptyDir volumes
  (pmorie@gmail.com)
- UPSTREAM: add client field mappings for v1 (jliggitt@redhat.com)
- UPSTREAM: Validate port protocol case strictly (jliggitt@redhat.com)
- bump(github.com/openshift/openshift-
  sdn/ovssubnet):962bcbc2400f6e66e951e61ba259e81a6036f1a2 (rchopra@redhat.com)
- Use uppercase protocol when creating from source in Web Console
  (spadgett@redhat.com)
- allow some resources to be created while the namespace is terminating
  (deads@redhat.com)
- Newapp: preserve tag specified in image stream input (cewong@redhat.com)
- add buildUpdate validation to protect spec (deads@redhat.com)
- UPSTREAM: fix exec infinite loop (agoldste@redhat.com)
- Ensure we're importing everything necessary for fallback codepaths too
  (sdodson@redhat.com)
- Improve deployment strategy logging (ironcladlou@gmail.com)
- Set min-width on pod-template-block (spadgett@redhat.com)
- Update registry/router to use rolling deployments (jliggitt@redhat.com)
- Add admission controller for build strategy policy check (cewong@redhat.com)
- Add admission controller for build strategy policy check (cewong@redhat.com)
- Population tuning should be parameterizable (ccoleman@redhat.com)
- Utility class for word-break. Fix for
  https://github.com/openshift/origin/issues/2560 (sgoodwin@redhat.com)
- prevent panic in oc process error handling (deads@redhat.com)
- UPSTREAM Fix bug where network container could be torn down before other pods
  (decarr@redhat.com)
- Set cache control headers for protected requests (ccoleman@redhat.com)
- Update build and deployment config associations when filter changes
  (spadgett@redhat.com)
- add service account to ipfailover (pweil@redhat.com)
- Impose a high default QPS and rate limit (ccoleman@redhat.com)
- Show correct restart policy on browse pods page (spadgett@redhat.com)
- Fixed the message about image being pushed with authorization
  (maszulik@redhat.com)
- Set some timeout values explicitly to http.Transport
  (nakayamakenjiro@gmail.com)
- Set http.Transport to get proxy from environment (nakayamakenjiro@gmail.com)
- Fix syntax error in e2e (pmorie@gmail.com)
- Adding validatiions for deployment config LatestVersion  - LatestVersion
  cannot be negative  - LatestVersion cannot be decremented  - LatestVersion
  can be incremented by only 1 (abhgupta@redhat.com)
- Deflake TestServiceAccountAuthorization (jliggitt@redhat.com)
- Only challenge for errors that can be fixed by authorizing
  (jliggitt@redhat.com)
- Add registry auth tests, fix short-circuit (jliggitt@redhat.com)
- Clean up orphaned deployers and use pod watches (ironcladlou@gmail.com)
- Make base filename configurable for create-api-client-config
  (jliggitt@redhat.com)
- UPSTREAM Fix ReadinessProbe: seperate readiness and liveness in the code
  (bparees@redhat.com)
- make service name a parameter (bparees@redhat.com)
- fix new-app errors (deads@redhat.com)
- OpenShift CLI cmd for volumes (rpenta@redhat.com)
- Create a formal release script (ccoleman@redhat.com)
- Updates to address part of bug 1230483 (slewis@fusesource.com)
- Specify seperate icon for 'pending' state vs 'running' state Add browse
  screenshots for Ashesh (sgoodwin@redhat.com)
- Setting NodeSelector on deployer/hook pods (abhgupta@redhat.com)
- make a non-escalating policy resource group (deads@redhat.com)
- UPSTREAM Don't pretty print by default (decarr@redhat.com)
- Export command to template should let me provide template name
  (decarr@redhat.com)
- UPSTREAM: Add CephFS volume plugin (mturansk@redhat.com)
- feedback for nodes group, namespace name check and weights (pweil@redhat.com)
- Add routingConfig.subdomain to master config (jliggitt@redhat.com)
- Test the origin docker container (ccoleman@redhat.com)
- UPSTREAM: search for mount binary in hostfs (ccoleman@redhat.com)
- Update readme (ccoleman@redhat.com)
- doc: Sync with master (kargakis@users.noreply.github.com)
- Change system:openshift-client username to system:master
  (jliggitt@redhat.com)
- config: Use already existing path (kargakis@users.noreply.github.com)
- Make admission errors clearer (jliggitt@redhat.com)
- Simplify createProvidersFromConstraints, add non-mutating test
  (jliggitt@redhat.com)
- UPSTREAM Rate limit scheduler to bind pods burst qps (decarr@redhat.com)
- More updates to data population scripts (decarr@redhat.com)
- Add non-mutating test (jliggitt@redhat.com)
- UPSTREAM: Expand variables in containers' env, cmd, args (pmorie@gmail.com)
- Update readme (ccoleman@redhat.com)
- Don't show "Get Started" message when project has replication controllers
  (spadgett@redhat.com)
- scc admission (pweil@redhat.com)
- router as restricted uid (pweil@redhat.com)
- UPSTREAM: work with SC copy, error formatting, add GetSCCName to provider
  (pweil@redhat.com)
- Disable image triggers on rollback (ironcladlou@gmail.com)
- Initial scripts for data population (decarr@redhat.com)
- Added parsing for new secret sources to enable naming source keys.
  (steve.kuznetsov@gmail.com)
- Support a containerized node (ccoleman@redhat.com)
- Fix command help for expose service (cewong@redhat.com)
- Use stricter name validation creating from source repository
  (spadgett@redhat.com)
- UPSTREAM its bad to spawn a gofunc per quota with large number of quotas
  (decarr@redhat.com)
- UPSTREAM: add simple variable expansion (pmorie@gmail.com)
- UPSTREAM: nsenter path should be relative (ccoleman@redhat.com)
- Build fixes. (avagarwa@redhat.com)
- Newapp: Remove hard coded image names for code detection (cewong@redhat.com)
- UPSTREAM: Add omitempty to RBD/ISCSI volume sources (jliggitt@redhat.com)
- update db templates to use imagestreams in openshift project
  (bparees@redhat.com)
- Cleaning up deployments on failure  - The failed deployment is scaled to 0  -
  The last completed deployment is scaled back up  - The cleanup is done before
  updating the deployment status to Failed  - A failure to clean up results in
  a transient error that is retried indefinitely (abhgupta@redhat.com)
- Test for and fix invalid markup nesting (jliggitt@redhat.com)
- Show "no deployments" message on browse page consistently
  (spadgett@redhat.com)
- Display start time instead of IP when not present (ccoleman@redhat.com)
- Bug 1229642 - new-build generates ImageStreams along with BuildConfig when
  needed. (maszulik@redhat.com)
- Allow setting service account in oadm registry/router (jliggitt@redhat.com)
- UPSTREAM: validate service account name in pod.spec (jliggitt@redhat.com)
- UPSTREAM: EmptyDir volumes for non-root 2/2 (pmorie@gmail.com)
- Fix broken --filename for oc env cmd (rpenta@redhat.com)
- Add tooltips to values we elide in the Web Console (spadgett@redhat.com)
- UPSTREAM: Added stop channel to prevent thread leak from watch
  (mturansk@redhat.com)
- app: Add element around overview on project.html page (stefw@redhat.com)
- Record events for initial deployment failures (ironcladlou@gmail.com)
- Node was blocking rather than running in goroutine (ccoleman@redhat.com)
- change .config/openshift to .kube (deads@redhat.com)
- Image push/pull policy updates (agoldste@redhat.com)
- change OPENSHIFTCONFIG to KUBECONFIG (deads@redhat.com)
- Bug 1229555 - fix broken example in oc new-app (contact@fabianofranz.com)
- Fix application template double escaping (decarr@redhat.com)
- Added stop channel to watched pods to prevent thread leak
  (mturansk@redhat.com)
- Use line-height: 1.3 for component headers (spadgett@redhat.com)
- Correlate and retrieve deployments by label (ironcladlou@gmail.com)
- Expose upstream generators and fix kubectl help (ccoleman@redhat.com)
- Support push secrets in the custom builder (agoldste@redhat.com)
- Prevent invalid names in new-app (cewong@redhat.com)
- Add emptyDir volumes to database templates (nagy.martin@gmail.com)
- Component refs are not docker image refs (ccoleman@redhat.com)
- Update README with create flow improvements (ccoleman@redhat.com)
- UPSTREAM: Run had invalid arguments (ccoleman@redhat.com)
- UPSTREAM: kill namespace defaulting (deads@redhat.com)
- Make tests more explicit (jliggitt@redhat.com)
- fix accessReview integration tests (deads@redhat.com)
- Implement deployment canary and fixes (ironcladlou@gmail.com)
- Upstream: node restart should not restart docker; fix node registration in
  vagrant (rchopra@redhat.com)
- Use better link for web console doc (dmcphers@redhat.com)
- Fix spelling errors (dmcphers@redhat.com)
- UPSTREAM: Add Pod IP to pod describe (ccoleman@redhat.com)
- expose stats port based on config (pweil@redhat.com)
- Upstream: make docker bridge configuration more dynamic (sdodson@redhat.com)
- UPSTREAM: add debug output for client calls (deads@redhat.com)
- Bug 1230066 - fixes oc help to use public git repo (contact@fabianofranz.com)
- bump(github.com/google/cadvisor):0.15.0-4-ga36554f (ccoleman@redhat.com)
- update imagestream location for ga (bparees@redhat.com)
- Add .tag* to gitignore, files generated by atom ctag (sdodson@redhat.com)
- Update bash completion for osc/osadm -> oc/oadm (sdodson@redhat.com)
- UPSTREAM: rest_client logging is generating too many metrics
  (ccoleman@redhat.com)
- whoami should show the current token and context (ccoleman@redhat.com)
- Cert serial numbers must be unique per execution (ccoleman@redhat.com)
- * Implement input from review (jhonce@redhat.com)
- Update to openshift-jvm 1.0.19 (slewis@fusesource.com)
- Infrastructure - Add and call vm-provision-fixup.sh (jhonce@redhat.com)
- fixes to sample app related instructions (gmontero@redhat.com)
- Handle spec.tags where tag name has a dot (spadgett@redhat.com)
- Change error check from IsConflict to IsAlreadyExists (jliggitt@redhat.com)
- add attach secret command (deads@redhat.com)
- deploy: Fix example and usage message (kargakis@users.noreply.github.com)
- Update README for images (j.hadvig@gmail.com)
- new-app: Fix empty tag in logs (kargakis@users.noreply.github.com)
- UPSTREAM: Support emptydir volumes for containers running as non-root
  (pmorie@gmail.com)
- Deflake integration test for overwrite policy (ccoleman@redhat.com)
- Allow GOMAXPROCS to be customized for openshift (ccoleman@redhat.com)
- Add test case for parallel.Run (ccoleman@redhat.com)
- SDN should signal when it's ready for pods to run (ccoleman@redhat.com)
- UPSTREAM: Allow OSDN to signal ready (ccoleman@redhat.com)
- UPSTREAM: Allow pod start to be delayed in Kubelet (ccoleman@redhat.com)
- Parallelize cert creation and test integration (ccoleman@redhat.com)
- bump(github.com/coreos/go-etcd/etcd):4cceaf7283b76f27c4a732b20730dcdb61053bf5
  (ccoleman@redhat.com)
- fix bad custom template (bparees@redhat.com)
- better error message for invalid source uri in sample custom builder
  (bparees@redhat.com)
- 'oc tag': create target stream if not found (agoldste@redhat.com)
- Update e2e test for new get pod output (decarr@redhat.com)
- UPSTREAM Decrease columns and refactor get pods layout (decarr@redhat.com)
- Support insecure registries (cewong@redhat.com)
- Fix deployer log message (jliggitt@redhat.com)
- changed hard-coded time to flag coming from CLI (mturansk@redhat.com)
- Expand short isimage id refs (agoldste@redhat.com)
- UPSTREAM: Add available volumes to index when not present
  (mturansk@redhat.com)
- Added PVRecycler controller to master (mturansk@redhat.com)
- Updated example README (steve.kuznetsov@gmail.com)
- UPSTREAM: GCEPD mounting on Atomic (mturansk@redhat.com)
- Adding a "/ready" endpoint for OpenShift (steve.kuznetsov@gmail.com)
- storage unit test to confirm validation (deads@redhat.com)
- add validateUpdate for API types (deads@redhat.com)
- add secrets subcommand to osc (deads@redhat.com)
- Use service accounts for build controller, deployment controller, and
  replication controller (jliggitt@redhat.com)
- Add tag command (agoldste@redhat.com)
- UPSTREAM: Adds ISCSI to PV and fixes a nil pointer issue
  (mturansk@redhat.com)
- return valid http status objects on rest errors (bparees@redhat.com)
- UPSTREAM: Normalize and fix PV support across volumes (mturansk@redhat.com)
- Disable QPS for internal API client (jliggitt@redhat.com)
- UPSTREAM: Added PV support for NFS (mturansk@redhat.com)
- update validation to handle validation argument reordering (deads@redhat.com)
- Update openshift-object-describer to 1.0.1 (spadgett@redhat.com)
- UPSTREAM: PV Recycling support (mturansk@redhat.com)
- update: Remove disabled --patch example (kargakis@users.noreply.github.com)
- Allow all Kubernetes controller arguments to be configured
  (ccoleman@redhat.com)
- UPSTREAM: Kubelet should log events at V(3) (ccoleman@redhat.com)
- Bug 1229731 - Updating docker rpm dependency in the specfile
  (bleanhar@redhat.com)
- Add registry-url flag to prune images (agoldste@redhat.com)
- UPSTREAM: Improve signature consistency for ValidateObjectMetaUpdate
  (deads@redhat.com)
- Issue 2880 - allow debugging docker push command. (maszulik@redhat.com)
- remove imagerepository policy refs (deads@redhat.com)
- Update to openshift-jvm 1.0.18 (slewis@fusesource.com)
- UPSTREAM: kube: update describer for dockercfg secrets (deads@redhat.com)
- Don't mutate build.spec when creating build pod (jliggitt@redhat.com)
- check name validation (deads@redhat.com)
- UPSTREAM: kube: expose name validation method (deads@redhat.com)
- make build config and instantiate consistent rest strategy (deads@redhat.com)
- expose: Bump validation and default flag message to routes
  (kargakis@users.noreply.github.com)
- Mostly golinting (kargakis@users.noreply.github.com)
- Fix webhook URL generation in UI (jliggitt@redhat.com)
- add version specific imagestream tags (bparees@redhat.com)
- add a default SCC for the cluster (pweil@redhat.com)
- Fix typos in tooltips on create from source page (spadgett@redhat.com)
- Consider existing deployments correctly when creating a new deployment
  (abhgupta@redhat.com)
- Switch the default API to v1 (ccoleman@redhat.com)
- UPSTREAM: v1 Secrets/ServiceAccounts needed a conversion
  (ccoleman@redhat.com)
- UPSTREAM: Alter default Kubernetes API versions (ccoleman@redhat.com)
- Remove trailing periods from help (ccoleman@redhat.com)
- Add types command showing OpenShift concepts (ccoleman@redhat.com)
- bump(github.com/MakeNowJust/heredoc):1d91351acdc1cb2f2c995864674b754134b86ca7
  (ccoleman@redhat.com)
- Pod failed, pending, warning style updates along with several bug fixes,
  inclusion of meta tags, and removal of inline styles and unused classes.
  (sgoodwin@redhat.com)
- Add shortcuts for service accounts (ccoleman@redhat.com)
- osc describe is should show spec tags when status empty (ccoleman@redhat.com)
- Update bindata.go for modified hawtio-core-navigation 2.0.48
  (spadgett@redhat.com)
- return proper http status failures from get logs (bparees@redhat.com)
- lower log level of missing tag for image message (bparees@redhat.com)
- Deleting deployment hook pods after a deployment completes
  (abhgupta@redhat.com)
- Subcommands should not display additional commands (ccoleman@redhat.com)
- Improve consistency of build trigger types (rhcarvalho@gmail.com)
- Replace occurrences of Github -> GitHub (rhcarvalho@gmail.com)
- Fixed webhook URLs (maszulik@redhat.com)
- Update CONTRIBUTING.adoc (bchilds@redhat.com)
- allow stats user/port/password to be configured (pweil@redhat.com)
- UPSTREAM: Pass memory swap limit -1 by default (decarr@redhat.com)
- Add get endpoints permission to node role for glusterfs (jliggitt@redhat.com)
- Add an export command to oc (ccoleman@redhat.com)
- Add support for processing multiple templates (mfojtik@redhat.com)
- Fix message in extended tests fixture (mfojtik@redhat.com)
- Security Allocator is configurable (ccoleman@redhat.com)
- Implemented an interface to expose the PolicyCache List() and Get() methods
  for policies and bindings on project and cluster level to the project
  authorization cache. (steve.kuznetsov@gmail.com)
- Namespace all build secrets (mfojtik@redhat.com)
- Update `osc` to `oc` in Web Console help text (spadgett@redhat.com)
- updates for feedback (pweil@redhat.com)
- promote whoami to osc (deads@redhat.com)
- add api description unit test (deads@redhat.com)
- UPSTREAM: Remove CORS headers from pod proxy responses (cewong@redhat.com)
- New-app: fix message when language is not detected. (cewong@redhat.com)
- new-app: Fix detectSource test (kargakis@users.noreply.github.com)
- Add persistent volume claims to database example templates
  (nagy.martin@gmail.com)
- Fix time duration formatting in push retry (mfojtik@redhat.com)
- UPSTREAM: Disable --patch for kubectl update
  (kargakis@users.noreply.github.com)
- Add process from stdin to hack/test-cmd.sh (mfojtik@redhat.com)
- Support processing using standard input (mfojtik@redhat.com)
- UPSTREAM: adding downward api volume plugin (salvatore-
  dario.minonne@amadeus.com)
- Must not apply labels to nested objects (contact@fabianofranz.com)
- UPSTREAM: Split resource.AsVersionedObject (ccoleman@redhat.com)
- UPSTREAM: ToJSON must support support forcing a JSON syntax check
  (contact@fabianofranz.com)
- Allow more master options to be configurable (ccoleman@redhat.com)
- Refactor usage and help templates to better catch corner cases
  (ccoleman@redhat.com)
- Fix travis builds (ccoleman@redhat.com)
- Add binaries for find and tree to registry image (pmorie@gmail.com)
- build hello-pod statically (bparees@redhat.com)
- Handle watch window expirations in UI (jliggitt@redhat.com)
- Generated conversions and deep copies (ccoleman@redhat.com)
- Make verify-generated-(deep-copies|conversion).sh required
  (ccoleman@redhat.com)
- Enable deep copy and conversions in OpenShift (ccoleman@redhat.com)
- UPSTREAM: Improve deep copy to work with OpenShift (ccoleman@redhat.com)
- Move conversions out of init() and give them names (ccoleman@redhat.com)
- Group commands in osc for ease of use (ccoleman@redhat.com)
- Rename 'osc' to 'os' and 'osadm' to 'oadm' (ccoleman@redhat.com)
- Display current and desired replicas on overview page (spadgett@redhat.com)
- Image API cleanup (agoldste@redhat.com)
- never retry pod/build sync delete failures (bparees@redhat.com)
- Controllers should be able to be lazily started (ccoleman@redhat.com)
- Round trip service account correctly in buildconfig/build
  (jliggitt@redhat.com)
- UPSTREAM: Enable LimitSecretReferences in service account admission
  (jliggitt@redhat.com)
- Properly resolve tag of build.Output in conversion (ccoleman@redhat.com)
- Fixed the error from webhook when secret mismatch (maszulik@redhat.com)
- Minor master cleanups (ccoleman@redhat.com)
- Remove v1beta1 (ccoleman@redhat.com)
- Renamed --build flag to --strategy and fixed taking that flag into account
  even when repo has Dockerfile. (maszulik@redhat.com)
- Issue 2695 - new-build command creating just BuildConfig from provided source
  and/or image. (maszulik@redhat.com)
- have osc status highlight disabled deployment configs (deads@redhat.com)
- Too much logging from cert creation (ccoleman@redhat.com)
- Use deployer service account for deployments (jliggitt@redhat.com)
- UPSTREAM: process new service accounts (jliggitt@redhat.com)
- Differentiate nodes volumes directories (jhonce@redhat.com)
- ensure route exists under one service only (pweil@redhat.com)
- UPSTREAM: remove client facet from metrics (ccoleman@redhat.com)
- Show correct message on project settings when no display name
  (spadgett@redhat.com)
- UPSTREAM Insert 'svc' into the DNS search paths (decarr@redhat.com)
- add output for what remove-user is doing (deads@redhat.com)
- Fix typos in documentation (konzems@gmail.com)
- Fix vagrant setup so that minions are pre-registered; Update Godeps with
  latest openshift-sdn (rchopra@redhat.com)
- Fix image reference generation for deployment configs (cewong@redhat.com)
- Remove TaskList polling (jliggitt@redhat.com)
- Updates to create flow forms (spadgett@redhat.com)
- UPSTREAM: security context constraints (pweil@redhat.com)
- Ensure KubeletConfig's RootDirectory is correct (agoldste@redhat.com)
- Converted glog.Error() -> util.HandleError(errors.New()), glog.Errorf() ->
  util.HandleError(fmt.Errorf()) where code was eating the error.
  (steve.kuznetsov@gmail.com)
- disable kube v1beta1 and v1beta2 by default (deads@redhat.com)
- update docs to remove v1beta1 (deads@redhat.com)
- Don't default displayname/description to project name (jliggitt@redhat.com)
- Support template watch (jimmidyson@gmail.com)
- reaper: Exit tests as soon as actions lengths don't match
  (kargakis@users.noreply.github.com)
- README.md: Fix up the 'Start Developing' instructions (stefw@redhat.com)
- Update CONTRIBUTING.adoc (hyun.soo.kim1112@gmail.com)
- Don't import if a spec.tag is tracking another (agoldste@redhat.com)
- Expose _endpoints.<> as a DNS endpoint (ccoleman@redhat.com)
- Fixing console link and adding link to new api doc (dmcphers@redhat.com)
- do not bounce router for endpoint changes that do not change the data
  (pweil@redhat.com)
- Fixes to Contributing doc (dmcphers@redhat.com)
- Updated swagger doc (ccoleman@redhat.com)
- Add test for tracking tags when ISMs are posted (agoldste@redhat.com)
- Add 'osc import-image' command (agoldste@redhat.com)
- New-app: more helpful message when not generating a service
  (cewong@redhat.com)
- Update proxy URL path (slewis@fusesource.com)
- Fix new-app help for app-from-image (cewong@redhat.com)
- Add v1 descriptions to oauth (decarr@redhat.com)
- Fix device busy issues on serial e2e runs (pmorie@gmail.com)
- Fix CLI deployment cancellation (ironcladlou@gmail.com)
- Make deployment config reaper reentrant (ironcladlou@gmail.com)
- don't share volumes directory in vagrant (pweil@redhat.com)
- Allow overriding registry URL when image pruning (agoldste@redhat.com)
- Minor spec file fixes. (avagarwa@redhat.com)
- UPSTREAM: Fix proxying of URLs that end in "/" in the pod proxy
  (cewong@redhat.com)
- UPSTREAM: make getFromCache more tolerant (deads@redhat.com)
- Allow the kubelet to take the full set of params (ccoleman@redhat.com)
- Adding 'openshift.io/' namespace to 'displayName', 'description' annotations.
  Added annotations to api/types.go and updated references.
  (steve.kuznetsov@gmail.com)
- UPSTREAM: Support kubelet initialization in order (ccoleman@redhat.com)
- UPSTREAM Fix error in quantity code conversion (decarr@redhat.com)
- UPSTREAM Fix namespace controller to tolerate not found items
  (decarr@redhat.com)
- New-app: add support for template files (cewong@redhat.com)
- Revert SDN and Kubelet initialization ordering (sdodson@redhat.com)
- update origin-version-change for configapi.Config objects (deads@redhat.com)
- fix output messages for api versions (deads@redhat.com)
- Rename dry-run to confirm for prune commands (agoldste@redhat.com)
- sticky sessions (pweil@redhat.com)
- Actually remove router and registry from experimental commands
  (kargakis@users.noreply.github.com)
- UPSTREAM: Match the isDefaultRegistryMatch with upstream (mfojtik@redhat.com)
- expose: Allow specifying a hostname when generating routes
  (kargakis@users.noreply.github.com)
- expose: Fix service validation (kargakis@users.noreply.github.com)
- dcController: Use annotations to list deployments
  (kargakis@users.noreply.github.com)
- Make origin project delete controller more fault tolerant to stop O(n) minute
  deletes (decarr@redhat.com)
- Make default namespace and osadm new-project set up service account roles
  (jliggitt@redhat.com)
- Update e2e to handle registry auth (agoldste@redhat.com)
- Require token in client config for image pruning (agoldste@redhat.com)
- Image policy updates (agoldste@redhat.com)
- Update registry policy (agoldste@redhat.com)
- Allow registry /healthz without auth (agoldste@redhat.com)
- Enable registry authentication (agoldste@redhat.com)
- Remove username validation for registry login (agoldste@redhat.com)
- Delete deploymentConfig before reaping deployments (ironcladlou@gmail.com)
- fix reverted code (pweil@redhat.com)
- Fix incorrect Content-Type in some Web Console responses
  (spadgett@redhat.com)
- Add v1 descriptions to image api (decarr@redhat.com)
- update generated kubeconfig keys to match osc login (deads@redhat.com)
- Move registry and router out of experimental commands
  (kargakis@users.noreply.github.com)
- Relax source repository URL validation (spadgett@redhat.com)
- Updated validation for builds per @rhcarvalho comments in #2699: separated
  and hardened test cases and simplified validation for multiple ICTs
  (maszulik@redhat.com)
- Remove "image repositories" from example osc command (spadgett@redhat.com)
- Add v1 descriptions to user api (decarr@redhat.com)
- Add v1 descriptions to external template api (decarr@redhat.com)
- UPSTREAM: json marshalling error must manifest earlier in resource visitors
  (contact@fabianofranz.com)
- fix overwrite-policy prefix (deads@redhat.com)
- Add v1 descriptions to sdn api (decarr@redhat.com)
- Add v1 descriptions to route api (decarr@redhat.com)
- Add missing description to v1 project api (decarr@redhat.com)
- Project node selector fixes (rpenta@redhat.com)
- Don't reopen websockets closed by DataService.unwatch() (spadgett@redhat.com)
- Add v1 descriptions to all build fields (decarr@redhat.com)
- Bug 1224089: UPSTREAM: expose: Better error formatting and generic flag
  message (kargakis@users.noreply.github.com)
- Add descriptions to v1 policy api, remove deprecated field
  (decarr@redhat.com)
- stop: Reap all deployments of a config (kargakis@users.noreply.github.com)
- Update `osc logs` examples (rhcarvalho@gmail.com)
- Guard against null deployment config triggers (spadgett@redhat.com)
- Update hawtio-core-navigation to 2.0.48 (spadgett@redhat.com)
- Add commit to github links, improve git link display (jliggitt@redhat.com)
- Remove --node-selector from osc new-project (jliggitt@redhat.com)
- Add godoc for mcs.ParseRange (pmorie@gmail.com)
- Fix issue#2655; bz1225410; rebase openshift-sdn Godeps (rchopra@redhat.com)
- Switch UI to using legacy API prefix (jliggitt@redhat.com)
- fix grammar of resource create message (bparees@redhat.com)
- disable v1beta1 by default (deads@redhat.com)
- UPSTREAM: Backport schema output fixes (ccoleman@redhat.com)
- JSON examples migration to v1beta3 leftovers (maszulik@redhat.com)
- Make pod eviction timeout configurable (rpenta@redhat.com)
- Honor clicks anywhere inside a link (jliggitt@redhat.com)
- add tmp volume so scratch image will work (bparees@redhat.com)
- Allow populating bearer token from file contents (jliggitt@redhat.com)
- Issue 2586 - allow only one ImageChangeTrigger for BuildConfig.
  (maszulik@redhat.com)
- Generate swagger specs and docs for our API (ccoleman@redhat.com)
- Refactor deploy hook retry policy (ironcladlou@gmail.com)
- Tearing down old deployment before bringing up new one for the recreate
  strategy (abhgupta@redhat.com)
- Simplify the deploy trigger int test (ironcladlou@gmail.com)
- UPSTREAM: Add "Info" to go-restful ApiDecl (ccoleman@redhat.com)
- UPSTREAM: Hack date-time format on *util.Time (ccoleman@redhat.com)
- UPSTREAM: Expose OPTIONS but not TRACE (ccoleman@redhat.com)
- UPSTREAM: Patch needs a type for swagger doc (ccoleman@redhat.com)
- Properly support the 'oapi' prefix (ccoleman@redhat.com)
- Show template parameter descriptions on create page (spadgett@redhat.com)
- Restore comments and remove empty ServiceAccount (mfojtik@redhat.com)
- Migrate YAML files to v1beta3 (mfojtik@redhat.com)
- Fix hack/convert-samples to deal with YAML files (mfojtik@redhat.com)
- Follow-on Web Console fixes for osapi/v1beta3 (spadgett@redhat.com)
- Fix Cancel button error on Web Console create pages (spadgett@redhat.com)
- Add UI e2e tests (jliggitt@redhat.com)
- Rework dockercfg in builder package to use upstream keyring
  (mfojtik@redhat.com)
- expose: Fix service validation and help message
  (kargakis@users.noreply.github.com)
- Retry the output image push if failed (mfojtik@redhat.com)
- UPSTREAM: fix omitempty on service account in v1beta3 (jliggitt@redhat.com)
- Deleting deployer pods for failed deployment before retrying
  (abhgupta@redhat.com)
- Update Web Console to use osapi/v1beta3 (spadgett@redhat.com)
- Fixing doc to make clear where the source should be (scitronpousty@gmail.com)
- Updated code with latest S2I. (maszulik@redhat.com)
- bump(github.com/openshift/source-to-
  image):77e3b722b028b8af94a3606d0dbb76dc377755fd (maszulik@redhat.com)
- Added Lists to origin-version-changer (maszulik@redhat.com)
- fix long help description to remove garbage chars (decarr@redhat.com)
- Re-generate bash completions (contact@fabianofranz.com)
- Fixes bash completion gen script (contact@fabianofranz.com)
- validate lasttriggeredimageid hasn't changed before running build
  (bparees@redhat.com)
- create osc policy * for non-cluster admin usage (deads@redhat.com)
- make subcommands return non-zero status on failures (deads@redhat.com)
- Build ImageChangeController shouldn't return early if it encounters an
  Instantiate error (mfojtik@redhat.com)
- Adds steps for safely restarting iptables (mrunal@me.com)
- deployconfig requires kind (deads@redhat.com)
- Security allocator and repair logic (ccoleman@redhat.com)
- Create UID and MCS category allocators (ccoleman@redhat.com)
- UPSTREAM: Add contiguous allocator (ccoleman@redhat.com)
- UPSTREAM Force explicit namespace provision (decarr@redhat.com)
- UPSTREAM Do not set container requests in limit ranger for Kube 1.0
  (decarr@redhat.com)
- [RPMs]: Install bash completion files (sdodson@redhat.com)
- Make the TriggeredByImage field ObjectReference (mfojtik@redhat.com)
- UPSTREAM: kube: serialize dockercfg files with auth (deads@redhat.com)
- auto-generate dockercfg secrets for service accounts (deads@redhat.com)
- UPSTREAM: kube: cleanup unused service account tokens (deads@redhat.com)
- Print name of existing pods with deployer-pod names (pmorie@gmail.com)
- Fixed typo in BuildRequest field name (mfojtik@redhat.com)
- Replace custom/flaky pod comparison with DeepEqual (ironcladlou@gmail.com)
- Adding meaningful comments deployments cannot be started/retried
  (abhgupta@redhat.com)
- Added missing test object and updated DeploymentConfig's ImageChange trigger
  definition to match current validations. (maszulik@redhat.com)
- Guard against missing error details kind or ID (spadgett@redhat.com)
- Add example Git URL to Create page (spadgett@redhat.com)
- integration/dns_test.go: don't expect recursion (lmeyer@redhat.com)
- SkyDNS: don't recurse requests (lmeyer@redhat.com)
- UPSTREAM: Disable systemd activation for DNS (ccoleman@redhat.com)
- UPSTREAM: Handle missing resolv.conf (ccoleman@redhat.com)
- bump(github.com/skynetservices/skydns):01de2a7562896614c700547f131e240b665468
  0c (lmeyer@redhat.com)
- Show correct error details on browse builds page (spadgett@redhat.com)
- UPSTREAM: Show pods number when describing services
  (kargakis@users.noreply.github.com)
- Use kubectl constants for dc reaper interval/timeout
  (kargakis@users.noreply.github.com)
- Make node's Docker exec handler configurable (agoldste@redhat.com)
- Rename BuildRequest.Image to TriggedByImage (mfojtik@redhat.com)
- Support cancelling deployment hooks (etc) (ironcladlou@gmail.com)
- Add more description for the BuildRequest Image field (mfojtik@redhat.com)
- UPSTREAM: kube: add pull secrets to service accounts (deads@redhat.com)
- Rename osc resize to osc scale (kargakis@users.noreply.github.com)
- make api levels configuratable (deads@redhat.com)
- UPSTREAM: rename resize to scale (kargakis@users.noreply.github.com)
- Tolerate missing BuildStatusNew in webhookgithub integration test
  (mfojtik@redhat.com)
- Fix TestWebhookGithubPushWithImage integration test (mfojtik@redhat.com)
- Resolve ImageStream reference outside loop in resolveImageSecret
  (mfojtik@redhat.com)
- Do not mutate DefaultServiceAccountName in BuildGenerator
  (mfojtik@redhat.com)
- Fix build image change race (agoldste@redhat.com)
- Provide default PushSecret and PullSecret using Service Account
  (mfojtik@redhat.com)
- Auto-wire push secrets into builds (agoldste@redhat.com)
- UPSTREAM: Add 'docker.io' and 'index.docker.io' to default registry
  (mfojtik@redhat.com)
- Fix name collisions between build and deployment pods (cewong@redhat.com)
- Fix structure of webhooks URL display in web console (cewong@redhat.com)
- UPSTREAM: Allowing ActiveDeadlineSeconds to be updated for a pod
  (abhgupta@redhat.com)
- Bug 1220998 - improve message in osc env update errors
  (contact@fabianofranz.com)
- make registry and router exit non-zero for failures (deads@redhat.com)
- UPSTREAM: Add support for pluggable Docker exec handlers
  (agoldste@redhat.com)
- Ensure OpenShift content creation results in namespace finalizer
  (decarr@redhat.com)
- remove-from-project and integration tests (deads@redhat.com)
- Update README.md (hyun.soo.kim1112@gmail.com)
- Deployer pod failure detection improvements (ironcladlou@gmail.com)
- update readme - centos7 has docker 1.6 (matt@redhat.com)
- Fix pkg/template test to use stored JSON fixture (mfojtik@redhat.com)
- Set default BuildTriggerPolicy.ImageChange when not given
  (rhcarvalho@gmail.com)
- Bug 1224097: Don't use custom names for route.servicename
  (kargakis@users.noreply.github.com)
- UPSTREAM: expose: Use separate parameters for default and custom name
  (kargakis@users.noreply.github.com)
- Fix pkg/template tests to use v1beta3 (mfojtik@redhat.com)
- Migrate all JSON examples to v1beta3 (mfojtik@redhat.com)
- Add script which migrate all JSON samples to certain version
  (mfojtik@redhat.com)
- Removing unnecessary namespace prefix for deployment/deploymentConfig/Repo
  (j.hadvig@gmail.com)
- Add test to detect config changes (jliggitt@redhat.com)
- Fix flaky TestConcurrentBuild* tests (jliggitt@redhat.com)
- Add proxy examples to master and node sysconfig files (sdodson@redhat.com)
- Add eth1 to virtual box interfaces and add support to not watch/monitor port
  for the f5 ipfailover use case (--watch-port=0). (smitram@gmail.com)
- Don't default node selector for openshift admin manag-node cmd
  (rpenta@redhat.com)
- Refactor to match upstream (ccoleman@redhat.com)
- UPSTREAM: Add groups to service account JWT (jliggitt@redhat.com)
- UPSTREAM: print more useful error (ccoleman@redhat.com)
- UPSTREAM: implement a generic webhook storage (ccoleman@redhat.com)
- UPSTREAM: Suppress aggressive output of warning (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):496be63c0078ce7323aede59005ad
  bd3e9eef8c7 (ccoleman@redhat.com)
- Refactor deployment cancellation handling (ironcladlou@gmail.com)
- Add breadcrumbs to pages in create flow (spadgett@redhat.com)
- Use tooltip rather than popover on settings page (spadgett@redhat.com)
- Show loading message until builders are loaded (spadgett@redhat.com)
- Fix error manually starting first build in Web Console (spadgett@redhat.com)
- Support rolling deployment hooks (ironcladlou@gmail.com)
- Remove Deployment resource (ironcladlou@gmail.com)
- Add --selector support to osadm registry (agoldste@redhat.com)
- Don't show get empty project message if project has monopods
  (spadgett@redhat.com)
- Improving/Adding/Refactoring logging messages (j.hadvig@gmail.com)
- Update labels and styles for create flow (spadgett@redhat.com)
- fix remove-user/group validation (deads@redhat.com)
- new-app: Add ability to specify a context directory
  (kargakis@users.noreply.github.com)
- Flip-flop priorities so that we distribute vips evenly. (smitram@gmail.com)
- Force refresh of projects when OpenShift Origin clicked (spadgett@redhat.com)
- pod/build delete sync (bparees@redhat.com)
- 'cat' here document rather than 'echo' (mjisyang@gmail.com)
- Fix ProjectNodeSelector config (jliggitt@redhat.com)
- Update vmware fedora version to be consistent (dmcphers@redhat.com)
- Disable `Next` button unless source URL is valid (spadgett@redhat.com)
- Added the deployment cancellation command to the CLI (abhgupta@redhat.com)
- Wait for service account before creating pods (jliggitt@redhat.com)
- system:node, system:sdn-reader, system:sdn-manager roles
  (jliggitt@redhat.com)
- Warn about pods with containers in bad states (spadgett@redhat.com)
- Update openshift-object-describer and k8s-label-selector dependencies
  (spadgett@redhat.com)
- Formatting fixes (dmcphers@redhat.com)
- UPSTREAM: resize: Enable resource type/name syntax
  (kargakis@users.noreply.github.com)
- Add minlength to name field on project create form (spadgett@redhat.com)
- Rename 'Management Console' to 'Web Console' (jliggitt@redhat.com)
- Updated image name in sample-app's pullimages.sh script (maszulik@redhat.com)
- UPSTREAM: kube: add pull secrets to service accounts (deads@redhat.com)
- Beef up osc label help message (kargakis@users.noreply.github.com)
- Bug 1223252: UPSTREAM: label: Invalidate empty or invalid value labels
  (kargakis@users.noreply.github.com)
- Fix repo name (dmcphers@redhat.com)
- Bug 1214205 - editor must always use the original object namespace when
  trying to update (contact@fabianofranz.com)
- Unpack and change versions of Template objects in origin-version-change
  (mfojtik@redhat.com)
- Show build pods events together with build events on osc describe build
  (maszulik@redhat.com)
- Fail build after 30 minutes of errors. (maszulik@redhat.com)
- use kubernetes plugin list instead of custom os list (mturansk@redhat.com)
- Add ServiceAccount type to list of exposed kube resources
  (jliggitt@redhat.com)
- Setting deployment/cancellation reason based on constants
  (abhgupta@redhat.com)
- Enable service account admission, token controller, auth, bootstrap policy
  (jliggitt@redhat.com)
- UPSTREAM: Add groups to service account JWT (jliggitt@redhat.com)
- UPSTREAM: gate token controller until caches are filled (jliggitt@redhat.com)
- add configchange trigger to frontend deployments (bparees@redhat.com)
- Added volume plugins to match upstream (mturansk@redhat.com)
- Added deleteTemplates method to remove templates from namespace
  (steve.kuznetsov@gmail.com)
- #1224083 - Update openshift-jvm to 1.0.17 (slewis@fusesource.com)
- UPSTREAM: bump timeout back to previous time
  (kargakis@users.noreply.github.com)
- UPSTREAM: Reduce reaper poll interval and wait while resizing
  (kargakis@users.noreply.github.com)
- Don't error out when exposing a label-less service as a route
  (kargakis@users.noreply.github.com)
- Added Kube PVC to OS whitelist (mturansk@redhat.com)
- Adding deployment cancellation controller (abhgupta@redhat.com)
- Disable triggers while reaping a deploymentConfig
  (kargakis@users.noreply.github.com)
- Display error when processing a template fails. (cewong@redhat.com)
- Don't repeat builder images in image catalog (spadgett@redhat.com)
- Add json tag for NetworkConfig (jdetiber@redhat.com)
- Move mock client calls under testclient (kargakis@users.noreply.github.com)
- Make golint happier (kargakis@users.noreply.github.com)
- Omit internal field when empty (rhcarvalho@gmail.com)
- Add test-cmd test to validate that we can create using a stored template
  (cewong@redhat.com)
- bump(github.com/openshift/openshift-
  sdn):7752990d5095d92905752aa5165a3d65ba8195e6 (sdodson@redhat.com)
- [RPMs] add openshift-sdn-ovs subpackage to carry ovs scripts and ovs dep
  (sdodson@redhat.com)
- Fix port ordering for a service (spadgett@redhat.com)
- Bug 1216930 - fix runtime error in rollback --dry-run
  (contact@fabianofranz.com)
- Validate project and image stream namespaces and names (jliggitt@redhat.com)
- Support custom CA for registry pruning (agoldste@redhat.com)
- Avoid warning icon flicker for deployment configs (spadgett@redhat.com)
- add TODO for watching delete events; catch error on StartMaster; do not try
  to create clusternetwork if it already exists (rchopra@redhat.com)
- Project status should include pod information (ccoleman@redhat.com)
- handle secret types (deads@redhat.com)
- Make link show up again and pass along token to openshift-jvm
  (slewis@fusesource.com)
- Added test cases to verify that ActiveDeadlineSeconds is set
  (abhgupta@redhat.com)
- Use client config's CA for registry pruning (agoldste@redhat.com)
- Duplicate default value in create node config was wrong (ccoleman@redhat.com)
- Replace secrets in BuildConfig with LocalObjectReference (mfojtik@redhat.com)
- Move deployment config to etcdgeneric storage patterns (decarr@redhat.com)
- grammar fix (somalley@redhat.com)
- respect --api-version flag for osc login (deads@redhat.com)
- Setting ActiveDeadlineSeconds on the deployment hook pod
  (abhgupta@redhat.com)
- UPSTREAM: kube: tolerate fatals without newlines (deads@redhat.com)
- Setting max/default ActiveDeadlineSeconds on the deployer pod
  (abhgupta@redhat.com)
- Add func for pruning an image from a stream (agoldste@redhat.com)
- Simplify output in login and project (ccoleman@redhat.com)
- Expose routes from services (kargakis@users.noreply.github.com)
- UPSTREAM: expose: Use resource builder (kargakis@users.noreply.github.com)
- Issue 2358 - better handling of server url parsing in osc login
  (contact@fabianofranz.com)
- UPSTREAM: Attach pull secrets to pods (mfojtik@redhat.com)
- Handle change in imageChange trigger status for v1beta3 (ccoleman@redhat.com)
- Test changes caused by version defaults (ccoleman@redhat.com)
- Add origin-version-change script (ccoleman@redhat.com)
- Make v1beta3 the default storage version (ccoleman@redhat.com)
- Initial commit of v1 api (ccoleman@redhat.com)
- remove unnecessary double escape replacement and add validation to ensure no
  one is relying on the removed behavior (pweil@redhat.com)
- fix looping on a closed channel - bz1222853, bz1223274 (rchopra@redhat.com)
- add prune images command (agoldste@redhat.com)
- Use correct deployer annotation (jliggitt@redhat.com)
- update forbidden messages (deads@redhat.com)
- relax restrictions on bundle secret (deads@redhat.com)
- Retry stream updates when pruning (agoldste@redhat.com)
- fix e2e public master (deads@redhat.com)
- Helpful hints for osc deploy make osc status worse (ccoleman@redhat.com)
- Remove summary pruner (agoldste@redhat.com)
- Fix template decode error when using new-app to create from a named template
  (cewong@redhat.com)
- Update pruning tests (agoldste@redhat.com)
- Replace _pods.less with _components.less (sgoodwin@redhat.com)
- Reenable CPU profiling default (ccoleman@redhat.com)
- manage-node tests can't rely on scheduling in hack/test-cmd.sh
  (ccoleman@redhat.com)
- wip (agoldste@redhat.com)
- Delegate manifest deletion to original Repository (agoldste@redhat.com)
- Image Pruning (agoldste@redhat.com)
- Image pruning (agoldste@redhat.com)
- Image pruning (agoldste@redhat.com)
- Image pruning (agoldste@redhat.com)
- Image Pruning (agoldste@redhat.com)
- Image pruning (agoldste@redhat.com)
- Image pruning (agoldste@redhat.com)
- Add image pruning support (agoldste@redhat.com)
- UPSTREAM(docker/distribution): manifest deletions (agoldste@redhat.com)
- UPSTREAM(docker/distribution): custom routes/auth (agoldste@redhat.com)
- UPSTREAM(docker/distribution): add BlobService (agoldste@redhat.com)
- Making the deployer pod name deterministic  - deployer pod name is now the
  same as the deployment name  - if an unrelated pod exists with the same name,
  the deployment is set to Failed (abhgupta@redhat.com)
- UPSTREAM(docker/distribution): add layer unlinking (agoldste@redhat.com)
- Add an example for a quota tracked project (decarr@redhat.com)
- Refactor overview page, combine route/service blocks (jliggitt@redhat.com)
- static markup and styles for overview (sgoodwin@redhat.com)
- Update install-assets.sh to use curl (jliggitt@redhat.com)
- Add Labels field into DockerConfig type (mfojtik@redhat.com)
- Fix generic webhook URL display (cewong@redhat.com)
- Code cleanup: Leveraging golang swap (abhgupta@redhat.com)
- Builds from BuildConfig missing BuildParameters.Resources (decarr@redhat.com)
- Code cleanup for openshift admin manage-node (rpenta@redhat.com)
- Update the help on admin commands (ccoleman@redhat.com)
- Display metadata about images in describe (ccoleman@redhat.com)
- Considering existing deployments for deployment configs  - If a
  running/pending/new deployment exists, the config is requeued  - If multiple
  running/previous/new deployments exists, older ones are cancelled
  (abhgupta@redhat.com)
- Use upstream RunKubelet method to run kubelet (cewong@redhat.com)
- Reduce fuzz iterations (ccoleman@redhat.com)
- Print more info on image tags and images (ccoleman@redhat.com)
- Minor change to the ipfailover Dockerfile for consistency
  (bleanhar@redhat.com)
- Add admin prune command (decarr@redhat.com)
- test-cmd: Check for removed rc (kargakis@users.noreply.github.com)
- test-cmd: Check for removed rc (kargakis@users.noreply.github.com)
- Build output round trip test can have ':' (ccoleman@redhat.com)
- Refactor etcd server start (ccoleman@redhat.com)
- Refactor to match upstream (ccoleman@redhat.com)
- UPSTREAM: print more useful error (ccoleman@redhat.com)
- UPSTREAM: implement a generic webhook storage (ccoleman@redhat.com)
- UPSTREAM: Suppress aggressive output of warning (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):6b6b47a777b4802c9c1360ea0d583
  da6cfec7363 (ccoleman@redhat.com)
- bump(etcd):v2.0.11 (ccoleman@redhat.com)
- Retry image import conflicts (ccoleman@redhat.com)
- Issue 2293 - fixes options help message (contact@fabianofranz.com)
- Add text-overflow: ellipsis style to project select (spadgett@redhat.com)
- remove extraneous escapes (bparees@redhat.com)
- More login tests (contact@fabianofranz.com)
- Set default project in login so we can generate a ctx name properly
  (contact@fabianofranz.com)
- Bug 1218126 - login needs to make use of token if provided
  (contact@fabianofranz.com)
- gofmt and doc changes for Go 1.4 (ccoleman@redhat.com)
- Issue 2322 - fixes pod rendering in deployments screen
  (contact@fabianofranz.com)
- Add osc stop and osc label (kargakis@users.noreply.github.com)
- Docker registry installed should be logged (ccoleman@redhat.com)
- Stop using ephemeral ports for integration tests (jliggitt@redhat.com)
- Remember token ttl, stop retrieving user/token from localStorage after
  expiration (jliggitt@redhat.com)
- Added Kubernetes PVClaimBinder to OpenShift (mturansk@redhat.com)
- Prune deployment utilities (decarr@redhat.com)
- Fix go cross compiler package names in release image (mfojtik@redhat.com)
- Describe project should show quota and resource limits (decarr@redhat.com)
- Set NOFILE to 128k/64k for master/node, set CORE=infinity
  (sdodson@redhat.com)
- UPSTREAM: Disable 'Timestamps' in Docker logs to prevent double-timestamps
  (mfojtik@redhat.com)
- Don't show undefined in error messages when error details incomplete
  (spadgett@redhat.com)
- gofmt fix (kargakis@users.noreply.github.com)
- Unbreak default profiling behavior (ccoleman@redhat.com)
- Set TTL on oauth tokens (jliggitt@redhat.com)
- Fix gofmt error (jliggitt@redhat.com)
- Use client.TransportFor to set an etcd transport (ccoleman@redhat.com)
- Expose kubernetes components as symlink binaries (ccoleman@redhat.com)
- Embed Kube binaries (ccoleman@redhat.com)
- bump(): add packages for kubelet/cloudprovider (ccoleman@redhat.com)
- Use secure csrf/session cookies when serving on HTTPS (jliggitt@redhat.com)
- Use rand.Reader directly to generate tokens (jliggitt@redhat.com)
- Add custom token generation functions (jliggitt@redhat.com)
- bump(github.com/RangelReale/osin):a9958a122a90a3b069389d394284283c19d58913
  (jliggitt@redhat.com)
- Update k8s-label-selector to 0.0.4 (spadgett@redhat.com)
- Rename user visible errors to s2i or source-to-image (ccoleman@redhat.com)
- Rename STIStrategy to SourceStrategy in v1beta3 (ccoleman@redhat.com)
- update sti image builder sti release (bparees@redhat.com)
- bump (github.com/openshift/source-to-
  image):ac0b2512c9f933afa985b056a7f3cbce1942cacb (bparees@redhat.com)
- Add create project to web console (spadgett@redhat.com)
- Update openshift-object-describer dependency to 0.0.9 (spadgett@redhat.com)
- add non-resource urls to role describer (deads@redhat.com)
- Ignore things that cannot be known in admission control (decarr@redhat.com)
- Prune builds (decarr@redhat.com)
- nits to config output (deads@redhat.com)
- fix rolebinding describer (deads@redhat.com)
- Persist a master count config variable to enable multi-master
  (ccoleman@redhat.com)
- Add integration tests to validate build controller HA tolerance
  (cewong@redhat.com)
- Improve image change controller HA tolerance (cewong@redhat.com)
- osc login stanza names (deads@redhat.com)
- don't write project request template (deads@redhat.com)
- Copy sdn scripts into node subpackage (sdodson@redhat.com)
- Transition to Kube 1.0 DNS schema (ccoleman@redhat.com)
- Add connect link to pod list for pods that expose jolokia port
  (slewis@fusesource.com)
- resize: Defer any kind except dcs to kubectl
  (kargakis@users.noreply.github.com)
- Move creation of Docker registry before osc login (mfojtik@redhat.com)
- Fix curl command in sample-app README (mfojtik@redhat.com)
- Validate user and identity objects on update (jliggitt@redhat.com)
- Make csrf and session cookies httpOnly (jliggitt@redhat.com)
- Ensure real DNS subjectAltNames precede IP DNS subjectAltNames in generated
  certs (jliggitt@redhat.com)
- Deployment configs on the web console, with deployments grouped
  (contact@fabianofranz.com)
- Add selector option to router. (smitram@gmail.com)
- OpenShift admin command to manage node operations (rpenta@redhat.com)
- Fix new-app build config image reference (cewong@redhat.com)
- Bug 1221041 - fixes example in osc env (contact@fabianofranz.com)
- update sdn types to work nicely in v1beta3 and osc (deads@redhat.com)
- Moved Node.js instructions to be with its own repo (sspeiche@redhat.com)
- Added clustered etcd example (mfojtik@redhat.com)
- Add test, include groups from virtual users in users/~ (deads@redhat.com)
- Initial group support (jliggitt@redhat.com)
- fix vagrant-fedora21 networking issue; update openshift-sdn version
  (rchopra@redhat.com)
- Add PullSecretName to v1beta1 (mfojtik@redhat.com)
- Set default policy for pod exec, port-forward, and proxy (cewong@redhat.com)
- Fix deploymentConfig defaulting (ironcladlou@gmail.com)
- log nested error (bparees@redhat.com)
- Fix the origin release image (ccoleman@redhat.com)
- flag.Addr should not default URLs to DefaultPort (ccoleman@redhat.com)
- in new-app flow: Fix where to get the port for the service, skip service
  generation if no port is exposed; fix the namespace use to check for resource
  existence (jcantril@redhat.com)
- UPSTREAM: Continue on errors in kubectl (ccoleman@redhat.com)
- Wrap navbar controls naturally for small screens (spadgett@redhat.com)
- Namespace deployment annotations for v1beta3 (ironcladlou@gmail.com)
- Remove entire os coverage package (dmcphers@redhat.com)
- Add osc resize (kargakis@users.noreply.github.com)
- Beef-up new-app help message (kargakis@users.noreply.github.com)
- Bug 1218971: Persist existing imageStream name in buildCofig
  (kargakis@users.noreply.github.com)
- Add support for PULL_DOCKERCFG_PATH to docker build strategy
  (mfojtik@redhat.com)
- Update strategies to inject pull dockercfg into builder containers
  (mfojtik@redhat.com)
- Card origin_devexp_567 - Add PullSecretName to all build strategies
  (mfojtik@redhat.com)
- Fix gofmt errors. (smitram@gmail.com)
- Add NodeSelector support to enable placement of router and ipfailover
  components. (smitram@gmail.com)
- Add support to deployments history in osc describe and deploy
  (contact@fabianofranz.com)
- add default conversion handling for imagestream kind (bparees@redhat.com)
- Fix conversion of output.DockerImageReference on v1beta3 builds
  (cewong@redhat.com)
- Migrate build and build config to latest patterns in storage
  (decarr@redhat.com)
- Refactor to match upstream (ccoleman@redhat.com)
- UPSTREAM: print more useful error (ccoleman@redhat.com)
- UPSTREAM: implement a generic webhook storage (ccoleman@redhat.com)
- UPSTREAM: Suppress aggressive output of warning (ccoleman@redhat.com)
- UPSTREAM: Ensure no namespace on create/update root scope types
  (jliggitt@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):25d32ee5132b41c122fe2929f3c6b
  e7c3eb74f1d (ccoleman@redhat.com)
- Be more aggressive about input and output on build From (ccoleman@redhat.com)
- update user/~ to return a user, even without an backing etcd entry
  (deads@redhat.com)
- Sort projects by display name (spadgett@redhat.com)
- Cleanup coverage profiles from output (dmcphers@redhat.com)
- SDN integration (rchopra@redhat.com)
- Bug 1218971: new-app: Create input imageStream
  (kargakis@users.noreply.github.com)
- Add descriptions to all API fields (ironcladlou@gmail.com)
- Make stanzas in test-cmd.sh independent (kargakis@users.noreply.github.com)
- Remove deployment followed by pull/1986 (nakayamakenjiro@gmail.com)
- Add bash-completion support (nakayamakenjiro@gmail.com)
- Remove cpu.pprof (ccoleman@redhat.com)
- bump (github.com/openshift/source-to-
  image):14c0ebafd9875ddba45ad53c220c3886458eaa44 (bparees@redhat.com)
- Ensure ImageStreamTag is exposed in v1beta3 (ccoleman@redhat.com)
- Ensure build output in v1beta3 is in ImageStreamTag (ccoleman@redhat.com)
- Add processedtemplates to policy (ccoleman@redhat.com)
- Switch integration tests to v1beta3 (ccoleman@redhat.com)
- Allow POST on empty namespace (ccoleman@redhat.com)
- Switch default API version to v1beta3 (ccoleman@redhat.com)
- UPSTREAM: allow POST on all namespaces in v1beta3 (ccoleman@redhat.com)
- UPSTREAM: disable minions/status in v1 Kube api (ccoleman@redhat.com)
- Combine coverage (dmcphers@redhat.com)
- Get rid of overly complex loop in favor of two commands with local variables
  (sdodson@redhat.com)
- merge default config with user config (akostadi@redhat.com)
- Added support for project node selector (rpenta@redhat.com)
- Accept ImageStreamTag as an image trigger kind (ironcladlou@gmail.com)
- Implement a Rolling deployment strategy (ironcladlou@gmail.com)
- Hide failed monopods in project overview (spadgett@redhat.com)
- Add config for number of cpus and memory (dmcphers@redhat.com)
- add cluster-reader role (deads@redhat.com)
- Show routes on project overview page (spadgett@redhat.com)
- Initialize object labels while processing a template
  (kargakis@users.noreply.github.com)
- Fix error loading view during karma tests (jliggitt@redhat.com)
- Allow process to output a template (ccoleman@redhat.com)
- Hide build pods based on annotations (spadgett@redhat.com)
- Updated tests for generic webhook (maszulik@redhat.com)
- Added support for gogs webhooks in github webhook, also removed requirement
  for User-Agent (maszulik@redhat.com)
- 'osadm create-api-client-config' was overwriting the client certificate with
  the CA (bleanhar@redhat.com)
- Morse code change - dah to dit (dots). (smitram@gmail.com)
- annotate build pods (bparees@redhat.com)
- Only show 'None' when labels is empty (spadgett@redhat.com)
- merge env statements when concatenating (bparees@redhat.com)
- Annotate generated hosts (jliggitt@redhat.com)
- build openshift-pod rpm (tdawson@redhat.com)
- Add `osc env` command for setting and reading env (ccoleman@redhat.com)
- Clean up various help commands (ccoleman@redhat.com)
- Handle 'Cancelled' and 'Error' build status in the web console
  (spadgett@redhat.com)
- Card origin_devexp_286 - Added ssh key-based access to private git
  repository. (maszulik@redhat.com)
- Fixed godoc for push secrets. (maszulik@redhat.com)
- fix grep and insert hostnames (rchopra@redhat.com)
- vagrant changes to support fedora21 (rchopra@redhat.com)
- Preventing multiple deployments from running concurrently
  (abhgupta@redhat.com)
- Empty state message for project overview (spadgett@redhat.com)
- update references to policy commands (deads@redhat.com)
- Issue 1509 - fix usage error in openshift start (contact@fabianofranz.com)
- osadm certs: inform user of file writes (lmeyer@redhat.com)
- osadm certs: provide command descriptions (lmeyer@redhat.com)
- osadm create-master-certs: no overwrite by default (lmeyer@redhat.com)
- reduce visibility of dockercfg not found error (bparees@redhat.com)
- Fix watching builds with fields filters (cewong@redhat.com)
- hack/common.sh uses the `which` command (akostadi@redhat.com)
- allow assigning floating IPs to openstack VMs (akostadi@redhat.com)
- VM prefixes for easy sharing AMZ and openstack accounts (akostadi@redhat.com)
- properly relativize paths (deads@redhat.com)
- Removed requirement for content-type in generic webhook, and added testcase
  for gitlab webhook push event. (maszulik@redhat.com)
- build-chain: s/repository/stream (kargakis@users.noreply.github.com)
- Add resource type descriptions to details sidebar (spadgett@redhat.com)
- Grammar fix in README (pmorie@gmail.com)
- UPSTREAM: Subresources inherit parent scope (ccoleman@redhat.com)
- Review comments (ccoleman@redhat.com)
- Detect and merge conflicts during osc edit (ccoleman@redhat.com)
- Exclude registered resources from latest.RESTMapper (ccoleman@redhat.com)
- UPSTREAM: print more useful error (ccoleman@redhat.com)
- UPSTREAM: legacy root scope should set NamespaceNone (ccoleman@redhat.com)
- UPSTREAM: SetNamespace should ignore root scopes (ccoleman@redhat.com)
- Perma-deflake TestDNS (ccoleman@redhat.com)
- Bug 1214229 - project admin cannot start build from another build
  (cewong@redhat.com)
- Add webhook to policy (ccoleman@redhat.com)
- Implement webhooks in v1beta3 (ccoleman@redhat.com)
- UPSTREAM: implement a generic webhook storage (ccoleman@redhat.com)
- change etcd paths (deads@redhat.com)
- Fix issues found by golint or govet within the build code (cewong@redhat.com)
- make project cache handle cluster policy (deads@redhat.com)
- cluster policy commands (deads@redhat.com)
- split cluster policy from local policy (deads@redhat.com)
- update for new STI request structure (bparees@redhat.com)
- bump (github.com/openshift/source-to-
  image):e71f7da750b1d81285597afacea8e365a991f04d (bparees@redhat.com)
- add all possible ips to the serving certs (deads@redhat.com)
- Remove deletion of registry pod from test-cmd (agoldste@redhat.com)
- Preserve scaling factor of prior deployment (ironcladlou@gmail.com)
- Change base paths for our resources (ccoleman@redhat.com)
- default node names always lowercase (deads@redhat.com)
- don't apply template if project exists (deads@redhat.com)
- Reenable deploy_trigger_test (agoldste@redhat.com)
- Use v1beta3 ObjectMeta for Route rather than internal representation
  (jimmidyson@gmail.com)
- Initial Image Metadata proposal (mfojtik@redhat.com)
- README.md: Use sudo in docker commands (stefw@redhat.com)
- Revert "Reenable deploy_trigger_test" (ccoleman@redhat.com)
- Implement a simple Git server for hosting repos (ccoleman@redhat.com)
- generic webhook should handle Git post-receive (ccoleman@redhat.com)
- bump(github.com/AaronO/go-git-http):0ebecedc64b67a3a8674c56724082660be48216e
  (ccoleman@redhat.com)
- properly handle bad projectRequestTemplates (deads@redhat.com)
- Add Browse -> Events page (spadgett@redhat.com)
- Wait for project to be deleted in hack/test-cmd.sh (ccoleman@redhat.com)
- Reenable deploy_trigger_test (agoldste@redhat.com)
- fix handling of imagestreamimage kinds in v1b1 (bparees@redhat.com)
- missed name when switching to new keys (pweil@redhat.com)
- Ignore openshift.local.* in test-go.sh (agoldste@redhat.com)
- Add conversion.go for generating conversions (ccoleman@redhat.com)
- Fix grep for registry pod in e2e (agoldste@redhat.com)
- Refactor to match upstream changes (ccoleman@redhat.com)
- UPSTREAM: kube: register types with gob (deads@redhat.com)
- UPSTREAM: Encode binary assets in ASCII only (jliggitt@redhat.com)
- UPSTREAM: Disable systemd activation for DNS (ccoleman@redhat.com)
- UPSTREAM: Handle missing resolv.conf (ccoleman@redhat.com)
- UPSTREAM: Suppress aggressive output of warning (ccoleman@redhat.com)
- UPSTREAM: add context to ManifestService methods (rpenta@redhat.com)
- UPSTREAM: Ensure no namespace on create/update root scope types
  (jliggitt@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):c07896ee358addb44cc063eff3db1
  fcd0fe9767b (ccoleman@redhat.com)
- NodeController has been moved (ccoleman@redhat.com)
- Revert "Added support for project node selector" (ccoleman@redhat.com)
- Remove namespace conflict (kargakis@users.noreply.github.com)
- Use unified diff output for testing (nagy.martin@gmail.com)
- Link to the github page for github repositories (nagy.martin@gmail.com)
- Rename no syncing var (dmcphers@redhat.com)
- Added support for project node selector (rpenta@redhat.com)
- Fix not-a-function errors navigating between pages (spadgett@redhat.com)
- Separate 'Example' field in cli help (contact@fabianofranz.com)
- Make indentation consistent in help and usage (contact@fabianofranz.com)
- Adjust usage on several commands (contact@fabianofranz.com)
- Restores usage to cli templates (contact@fabianofranz.com)
- Use default port to proxy to backend (jliggitt@redhat.com)
- add php stream to repo list (bparees@redhat.com)
- Fix formatting and typos (dmcphers@redhat.com)
- describe: name/namespace to namespace/name syntax fix
  (kargakis@users.noreply.github.com)
- new-app: Use the right image stream for the build from
  (kargakis@users.noreply.github.com)
- Remove trailing spaces (rhcarvalho@gmail.com)
- Improve cleanup script (rhcarvalho@gmail.com)
- Fix formatting in sample-app/README.md (rhcarvalho@gmail.com)
- vagrant: fix creating minion config when provisioning master
  (thaller@redhat.com)
- Fix gofmt complaint (nakayamakenjiro@gmail.com)
- Fixing typos (dmcphers@redhat.com)
- Add cursor pointer to service component (sgoodwin@redhat.com)
- UPSTREAM Reject unbounded cpu and memory pods if quota is restricting it
  #7003 (decarr@redhat.com)
- osadm registry: require client cert when secure (agoldste@redhat.com)
- grant admin and edit access to secrets (deads@redhat.com)
- Allow registry to auto-provision image streams (agoldste@redhat.com)
- Bug 1214548 (somalley@redhat.com)
- make the new-project cli display the correct message on denial
  (deads@redhat.com)
- refactor bulk to take the interfaces it needs, not factory (deads@redhat.com)
- use a template for requested projects (deads@redhat.com)
- fix template processing to handle slices (deads@redhat.com)
- do not rewrite certs unless route has changed (pweil@redhat.com)
- refactor cert manager to allow testing, implement delete functionality
  (pweil@redhat.com)
- promote commands out of experimental (deads@redhat.com)
- Add pod logs and build logs to default policy constants (cewong@redhat.com)
- Fix minor deploy cmd typo (ironcladlou@gmail.com)
- object-describer 0.0.7, build bindata (jliggitt@redhat.com)
- Restyle of overview elements (sgoodwin@redhat.com)
- Object sidebar (jforrest@redhat.com)
- Add word-break mixin (sgoodwin@redhat.com)
- Highlight elements that are currently selected (jforrest@redhat.com)
- Style changes (sgoodwin@redhat.com)
- Object sidebar (jforrest@redhat.com)
- change policy binding names (deads@redhat.com)
- add cluster policy resources (deads@redhat.com)
- Generate webhook URLs from the client (ccoleman@redhat.com)
- Expose (broken) webhooks to v1beta3 (ccoleman@redhat.com)
- osc start-build should be able to trigger webhook (ccoleman@redhat.com)
- UPSTREAM: Allow URL to be generated by request.go (ccoleman@redhat.com)
- osc new-app shouldn't pull when image is chained (ccoleman@redhat.com)
- Improve ISTag image not found error response (agoldste@redhat.com)
- Invert the default behavior for osadm registry/router (ccoleman@redhat.com)
- add tracing in resolvimagestreamreference (bparees@redhat.com)
- properly handle external kube proxy case (deads@redhat.com)
- freshen template syntax (bparees@redhat.com)
- Use a safer delete of registry pod in test-cmd (agoldste@redhat.com)
- Deployment hooks inherit resources and working dir (ironcladlou@gmail.com)
- UPSTREAM: Handle conversion of boolean query parameters with a value of
  'false' (cewong@redhat.com)
- Allow 1 ImageStream tag to track another (agoldste@redhat.com)
- Fix build image change controller possible panic (agoldste@redhat.com)
- bump(docker/spdystream):e372247595b2edd26f6d022288e97eed793d70a2
  (agoldste@redhat.com)
- Make hook containers inherit environment (ironcladlou@gmail.com)
- Add long help to osc project (nakayamakenjiro@gmail.com)
- projectrequest get message (deads@redhat.com)
- explicitly set the project to avoid depending on project cache refresh
  (deads@redhat.com)
- if AllowDisabledDocker, allow docker to be missing (deads@redhat.com)
- gofmt fix (kargakis@users.noreply.github.com)
- new-app: Add image tag in generated imageStream
  (kargakis@users.noreply.github.com)
- Create build log subresource in the style of upstream pod log
  (cewong@redhat.com)
- UPSTREAM: Use Pod.Spec.Host instead of Pod.Status.HostIP for pod subresources
  (cewong@redhat.com)
- Dump metrics and run a CPU profile in hack/test-cmd (ccoleman@redhat.com)
- Set GOMAXPROCS by default (ccoleman@redhat.com)
- Return a template object from template process (ccoleman@redhat.com)
- only allow trusted env variables in sti builder container
  (bparees@redhat.com)
- Add v1beta3 cut of builds (ccoleman@redhat.com)
- Cleanup sysconfig values as everything is now in a config file
  (sdodson@redhat.com)
- add logout command (deads@redhat.com)
- Add replicated zookeeper example (mfojtik@redhat.com)
- Force no color in grep (ccoleman@redhat.com)
- Add a deploy command (ironcladlou@gmail.com)
- UPSTREAM: Switch kubelet log command to use pod log subresource
  (cewong@redhat.com)
- [RPMs] Move clients to common package and add dockerregistry subpkg
  (sdodson@redhat.com)
- force predictable ordering of removing users from a project
  (deads@redhat.com)
- refactor ict to remove from/image parameters (bparees@redhat.com)
- Replace docker-registry-*.json with osadm registry (agoldste@redhat.com)
- Use true generic objects in templates (ccoleman@redhat.com)
- Match changes to make []runtime.Object cleaner (ccoleman@redhat.com)
- UPSTREAM: Support unknown types more cleanly (ccoleman@redhat.com)
- UPSTREAM: add HasAny (deads@redhat.com)
- Hide images section when no images detected in template (cewong@redhat.com)
- Disable registry liveness probe to support v1 & v2 (agoldste@redhat.com)
- Web Console: Fix problems creating from templates (spadgett@redhat.com)
- WIP: displayName annotation (somalley@redhat.com)
- Fixed the sample-app readme (maszulik@redhat.com)
- Fix error handling of osc project (nakayamakenjiro@gmail.com)
- Update console for v2 image IDs (agoldste@redhat.com)
- Enable building v2 registry image (agoldste@redhat.com)
- Add info about Docker 1.6 to README (agoldste@redhat.com)
- [RPMs] Require docker >= 1.6.0 (sdodson@redhat.com)
- Require Docker 1.6 for node startup (agoldste@redhat.com)
- v2 registry updates (agoldste@redhat.com)
- UPSTREAM: add context to ManifestService methods (rpenta@redhat.com)
- bump(docker/distribution):62b70f951f30a711a8a81df1865d0afeeaaa0169
  (agoldste@redhat.com)
- Pass --force to docker push if needed (agoldste@redhat.com)
- * Add support for local-source configuration (jhonce@redhat.com)
- bad file references due to moved config (deads@redhat.com)
- Issue 1480 - switched to using goautoneg package for parsing accept headers
  (maszulik@redhat.com)
- UPSTREAM: Fix getting services in expose cmd
  (kargakis@users.noreply.github.com)
- Tests for new-app (kargakis@users.noreply.github.com)
- Rework new-app (kargakis@users.noreply.github.com)
- Remove experimental generate command (kargakis@users.noreply.github.com)
- UPSTREAM: cobra loses arguments with same value as subcommand
  (deads@redhat.com)
- bump(github.com/spf13/cobra):ebb2d55f56cfec37ad899ad410b823805cc38e3c
  (contact@fabianofranz.com)
- bump(github.com/spf13/pflag):60d4c375939ff7ba397a84117d5281256abb298f
  (contact@fabianofranz.com)
- make openshift start --write-config take a dir (deads@redhat.com)
- Add resource requirements to deployment strategy (decarr@redhat.com)
- don't let editors delete a project (deads@redhat.com)
- Show icons embedded as data uris in template and image catalogs in console
  (jforrest@redhat.com)
- Fix formatting (dmcphers@redhat.com)
- Handle portalIP 'None' and empty service.spec.ports (spadgett@redhat.com)
- Start/Rerun a build from the console (j.hadvig@gmail.com)
- Work around 64MB tmpfs limit (agoldste@redhat.com)
- UPSTREAM: describe: Support resource type/name syntax
  (kargakis@users.noreply.github.com)
- Add Deployment to v1beta3 (ccoleman@redhat.com)
- doc: fix instructions in example doc (mjisyang@gmail.com)
- Fix typo (rhcarvalho@gmail.com)
- Change available loglevel with openshift (nakayamakenjiro@gmail.com)
- default certificate support (pweil@redhat.com)
- Fixes as per @smarterclayton review comments. (smitram@gmail.com)
- Rename from ha*config to ipfailover. Fixes and cleanup as per @smarterclayton
  review comments. (smitram@gmail.com)
- Complete --delete functionality. (smitram@gmail.com)
- fix demo config (smitram@gmail.com)
- Convert to plugin code, add tests and use replica count in the keepalived
  config generator. (smitram@gmail.com)
- Checkpoint ha-config work. Add HostNetwork capabilities. Add volume mount to
  container. (smitram@gmail.com)
- Add HA configuration proposal. (smitram@gmail.com)
- Add new ha-config keepalived failover service container code, image and
  scripts. (smitram@gmail.com)
- Hide ugly output from osc status --help (nakayamakenjiro@gmail.com)
- Use unminified css on login page (jliggitt@redhat.com)
- sort projects (somalley@redhat.com)
- use CheckErr for pretty messages (deads@redhat.com)
- Add route to v1beta3 (ccoleman@redhat.com)
- add osadm to docker image (deads@redhat.com)
- Bug 1215014 - hostname for the node a pod is on is showing up as unknown due
  to an api change (jforrest@redhat.com)
- Embed the openshift-jvm console (jforrest@redhat.com)
- Added Node.js simple example workflow (sspeiche@redhat.com)
- migrate roles and bindings to new storage (deads@redhat.com)
- UPSTREAM: cobra loses arguments with same value as subcommand
  (deads@redhat.com)
- allow login with file that doesn't exist yet (deads@redhat.com)
- UPSTREAM Normalize to lower resource names in quota admission
  (decarr@redhat.com)
- [RPMs] Add socat and util-linux dependencies for node (sdodson@redhat.com)
- make request-project switch projects (deads@redhat.com)
- make project delegatable (deads@redhat.com)
- make osc login more userfriendly (deads@redhat.com)
- Produce events from deployment in failure scenarios (decarr@redhat.com)
- Deployments page throws JS error, still referencing /images when should be
  getting imageStreams (jforrest@redhat.com)
- Allow insecure registries for image import (ccoleman@redhat.com)
- Allow image specs of form foo:500/bar (ccoleman@redhat.com)
- Adopt multi-port services changes (spadgett@redhat.com)
- Validate ImageStreams in triggers (ironcladlou@gmail.com)
- enable stats listener for haproxy (pweil@redhat.com)
- UPSTREAM Fix nil pointer that can happen if no container resources are
  supplied (decarr@redhat.com)
- Initial work on multi-context html5 handling (jliggitt@redhat.com)
- Issue 1562 - relativize paths in client config file
  (contact@fabianofranz.com)
- Bug 1213648 - switch to a valid project after logging in
  (contact@fabianofranz.com)
- more tests (deads@redhat.com)
- make test-integration.sh allow single test (deads@redhat.com)
- add imagestream validation (deads@redhat.com)
- Disable building v2 registry image (agoldste@redhat.com)
- Fix URL for build webhooks docs in console + README (j.hadvig@gmail.com)
- Build controller logs events when failing to create pods (decarr@redhat.com)
- Forbidden resources should not break new-app (ccoleman@redhat.com)
- The order of "all" should be predictable (ccoleman@redhat.com)
- Add resource requirements to build parameters (decarr@redhat.com)
- try to match forbidden status to api version request (deads@redhat.com)
- Fix gofmt complaint (nakayamakenjiro@gmail.com)
- Add osadm to tarball (nakayamakenjiro@gmail.com)
- UPSTREAM Fixup event object reference generation to allow downstream objects
  (decarr@redhat.com)
- sample template messed up with v1beta3 (deads@redhat.com)
- Remove /tmp/openshift from README (ccoleman@redhat.com)
- correct registry and repository name (bparees@redhat.com)
- serve on multiple ports (pweil@redhat.com)
- UPSTREAM cherry pick make describeEvents DescribeEvents (decarr@redhat.com)
- add self-provisioned newproject (deads@redhat.com)
- Implement test config (ccoleman@redhat.com)
- migrate policy to new rest storage (deads@redhat.com)
- remove local .openshiftconfig (deads@redhat.com)
- Issue #1488 - added build duration and tweaked build counting in describer
  (maszulik@redhat.com)
- UPSTREAM: Allow resource builder to avoid fetching objects
  (jliggitt@redhat.com)
- Improve output of who-can command, fix oauthtokens bootstrap policy
  (jliggitt@redhat.com)
- Prepare v1beta3 Template types (ccoleman@redhat.com)
- Issue 1812 - subcommand 'options' must be exposed in every command that uses
  the main template (contact@fabianofranz.com)
- UPSTREAM Fix nil pointer in limit ranger (decarr@redhat.com)
- Add support to osc new-app from stored template (contact@fabianofranz.com)
- allow project admins to modify endpoints (deads@redhat.com)
- change openshiftconfig loading rules and files (deads@redhat.com)
- Replace all hardcoded default tags with DefaultImageTag
  (kargakis@users.noreply.github.com)
- Allow protocol prefixed docker pull specs (ccoleman@redhat.com)
- Support parameter substitution for all string fields (mfojtik@redhat.com)
- copy env variables into sti execution environment (bparees@redhat.com)
- Improve display of standalone build configs (ccoleman@redhat.com)
- Add build revision info to osc status (ccoleman@redhat.com)
- UPSTREAM: Suppress aggressive output of warning (ccoleman@redhat.com)
- Internal rename to v1beta3 (ccoleman@redhat.com)
- Update internal to v1beta3 for parity with Kube (ccoleman@redhat.com)
- Add round trip tests for images (ccoleman@redhat.com)
- Slightly simplify status output for service (ccoleman@redhat.com)
- Use extensions when editing a file (ccoleman@redhat.com)
- Fix issue in error reason detection (contact@fabianofranz.com)
- UPSTREAM: allow multiple changes in modifyconfig (deads@redhat.com)
- UPSTREAM: change kubeconfig loading order and update filename
  (deads@redhat.com)
- Bug 1201615 - Give swagger the correct base URL (ccoleman@redhat.com)
- Exposing the pod manifest file/dir option for the node in Origin
  (abhgupta@redhat.com)
- add db sample templates (bparees@redhat.com)
- UPSTREAM: resync api request resolver (deads@redhat.com)
- Add option to restrict google logins to custom domains (jliggitt@redhat.com)
- backends will be named based on the route ns/name, not the service name
  (pweil@redhat.com)
- UPSTREAM: Add URL parameters to proxy redirect Location header
  (cewong@redhat.com)
- missing json tag (deads@redhat.com)
- Remove trailing } (nagy.martin@gmail.com)
- Check /dev/tty if STDIN is not a tty (ccoleman@redhat.com)
- Add an edit command (ccoleman@redhat.com)
- stronger validation for tls termination type (pweil@redhat.com)
- Don't trigger a build if the namespaces differ (agoldste@redhat.com)
- UPSTREAM: It should be possible to have lists with mixed versions
  (ccoleman@redhat.com)
- Take storage version for kube/os as config params (ccoleman@redhat.com)
- First cut of resources without significant changes (ccoleman@redhat.com)
- Initial v1beta2 (experimental) cut (ccoleman@redhat.com)
- UPSTREAM: create parent dir structure when saving config to file
  (contact@fabianofranz.com)
- [BZ-1211516] Fix creating route even when choosing not to
  (jcantril@redhat.com)
- [BZ-1212362] Remove tls block for unsecure router generation from web console
  (jcantril@redhat.com)
- Some commenting here and there (kargakis@users.noreply.github.com)
- disallow empty static node names (deads@redhat.com)
- generate: Use Docker parser for validation
  (kargakis@users.noreply.github.com)
- change KUBECONFIG references to OPENSHIFTCONFIG (deads@redhat.com)
- restrict openshift loading chain to only openshift (deads@redhat.com)
- Use our mysql image (nagy.martin@gmail.com)
- Remove misleading comment from docs (rhcarvalho@gmail.com)
- Bump cadvisor, libcontainer (agoldste@redhat.com)
- Bug 1211235 - Validate user against OpenShift in case of docker login for v2
  registry (rpenta@redhat.com)
- UPSTREAM: allow multiple changes in modifyconfig (deads@redhat.com)
- bundle-secret updates (jliggitt@redhat.com)
- UPSTREAM: Fix a small regression on api server proxy after switch to v1beta3.
  #6701 (cewong@redhat.com)
- Convert OAuth registries to generic etcd (jliggitt@redhat.com)
- WIP: bundle-secret per feedback/rebase error (somalley@redhat.com)
- UPSTREAM: add flattening and minifying options to config view #6761
  (deads@redhat.com)
- Fix for Bug 1211210 in the ui where the tile list for builder images don't
  clear correctly in some situations. Remove animation transition css from
  _core, import new _component-animations and scope rule to .show-hide class
  (sgoodwin@redhat.com)
- bump(github.com/spf13/cobra): 9cb5e8502924a8ff1cce18a9348b61995d7b4fde
  (contact@fabianofranz.com)
- bump(github.com/spf13/pflag): 18d831e92d67eafd1b0db8af9ffddbd04f7ae1f4
  (contact@fabianofranz.com)
- [BUG 1211516] Fix service definition generation for v1beta3 when creating an
  app from source in the web console (jcantril@redhat.com)
- Show token expiration times (jliggitt@redhat.com)
- remove --username and --password from most osc commands (deads@redhat.com)
- Fix 'address already in use' errors in integration tests
  (jliggitt@redhat.com)
- Lengthen default access token lifetime to 1 day (jliggitt@redhat.com)
- Update keys for basicauth URL IDP to use OpenID standard claim names
  (jliggitt@redhat.com)
- Suppress swagger debug output (ccoleman@redhat.com)
- Bug 1209774: Trim windows newlines correctly (jliggitt@redhat.com)
- [RPMs] Generrate cross platform clients for MacOSX and Windows
  (sdodson@redhat.com)
- Add missing omitempty tags (ironcladlou@gmail.com)
- Minimize CPU churn in auth cache, re-enable integration test check
  (decarr@redhat.com)
- Remove all calls to the /images endpoint (jforrest@redhat.com)
- Correct kind, name, selfLink for ISTag, ISImage (agoldste@redhat.com)
- UPSTREAM: allow selective removal of kubeconfig override flags #6768
  (deads@redhat.com)
- Add e2e test coverage (ironcladlou@gmail.com)
- WIP (ironcladlou@gmail.com)
- Fix tests to be ifconfig 1.4.X compatible (epo@jemba.net)
- Implement deployment hooks (ironcladlou@gmail.com)
- Add limit range defaults to settings page (jforrest@redhat.com)
- build-chain: Fix test names for split (kargakis@users.noreply.github.com)
- Display login failures in osc (jliggitt@redhat.com)
- Add placeholder challenger when login is only possible via browser
  (jliggitt@redhat.com)
- Protect browsers from basic-auth CSRF attacks (jliggitt@redhat.com)
- Prevent duplicate resources in new-app (cewong@redhat.com)
- Disable refresh_token generation (jliggitt@redhat.com)
- Pass through remote OAuth errors (jliggitt@redhat.com)
- Create from template fails with JS error (jforrest@redhat.com)
- Enforce admission control of Origin resources in terminating namespaces
  (decarr@redhat.com)
- update osc config to use the same files as osc get (deads@redhat.com)
- UPSTREAM: make kubectl config behave more expectedly #6585 (deads@redhat.com)
- Add SyslogIdentifier=openshift-{master,node} respectively
  (sdodson@redhat.com)
- UPSTREAM: make APIInfoResolve work against subresources (deads@redhat.com)
- fix simulator urls (pweil@redhat.com)
- Provide easy delete of resources for new-app and generate
  (kargakis@users.noreply.github.com)
- Bug 1210659 - create from template fixes (jforrest@redhat.com)
- Cleanup the STI and Docker build output (mfojtik@redhat.com)
- UPSTREAM: Support setting up aliases for groups of resources
  (kargakis@users.noreply.github.com)
- Instructions to reload Network Manager (jliggitt@redhat.com)
- Update router integration test (ccoleman@redhat.com)
- TEMPORARY: osc build-logs failing in other namespace (ccoleman@redhat.com)
- Version lock e2e output tests (ccoleman@redhat.com)
- Master should send convertor, v1beta3 not experimental (ccoleman@redhat.com)
- Fix bug in error output (ccoleman@redhat.com)
- Refactor tests with port, command, testclient changes (ccoleman@redhat.com)
- Use Args instead of Command for OpenShift (ccoleman@redhat.com)
- Event recording has changed upstream, and changes to master/node args
  (ccoleman@redhat.com)
- Handle multi-port services in part (ccoleman@redhat.com)
- Update commands to handle change to cmd.Factory upstream
  (ccoleman@redhat.com)
- Refactor from upstream (ccoleman@redhat.com)
- UPSTREAM: Pass mapping version to printer always (ccoleman@redhat.com)
- UPSTREAM: entrypoint has wrong serialization flags in JSON
  (ccoleman@redhat.com)
- UPSTREAM: Ensure no namespace on create/update root scope types
  (jliggitt@redhat.com)
- UPSTREAM: add context to ManifestService methods (rpenta@redhat.com)
- UPSTREAM: Handle missing resolv.conf (ccoleman@redhat.com)
- UPSTREAM: Disable UI for Kubernetes (ccoleman@redhat.com)
- UPSTREAM: Disable systemd activation for DNS (ccoleman@redhat.com)
- UPSTREAM: Encode binary assets in ASCII only (jliggitt@redhat.com)
- UPSTREAM: support subresources in api info resolver (deads@redhat.com)
- UPSTREAM: Don't use command pipes for exec/port forward (agoldste@redhat.com)
- UPSTREAM: Prometheus can't be cross-compiled safely (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):b12d75d0eeeadda1282f5738663bf
  e38717ebaf4 (ccoleman@redhat.com)
- [DEVEXP-457] Create application from source. Includes changes from jwforres,
  cewong, sgoodwin (jcantril@redhat.com)
- NetworkPlugin option in node config (rchopra@redhat.com)
- [RPMs]: tuned profiles get installed into /usr/lib not /usr/lib64
  (sdodson@redhat.com)
- separate tls and non-tls backend lookups (pweil@redhat.com)
- Now that we have better error handling, dont attempt login when we get a 0
  status code (jforrest@redhat.com)
- Update Browse->Images to be Image Streams in console (jforrest@redhat.com)
- Stop polling for pods in the console and open a websocket instead
  (jforrest@redhat.com)
- build-chain: Print only DOT output when specified
  (kargakis@users.noreply.github.com)
- Adding some more notes on probing containers (bleanhar@redhat.com)
- Auto provision image repo on push (agoldste@redhat.com)
- Setup aliases for imageStream* (kargakis@users.noreply.github.com)
- Remove admission/resourcedefaults (ccoleman@redhat.com)
- Update rebase-kube (ccoleman@redhat.com)
- Add OpenID identity provider (jliggitt@redhat.com)
- Refactor OAuth config (jliggitt@redhat.com)
- Widen the OpenShift CIDR to 172.30.0.0/16 (ccoleman@redhat.com)
- Add running builds and deployments to status output (ccoleman@redhat.com)
- Separate project status loggers (ccoleman@redhat.com)
- Add a generic injectable test client (ccoleman@redhat.com)
- UPSTREAM: Support a pluggable fake (ccoleman@redhat.com)
- Upgrade from etcd 0.4.6 -> 2.0.9 (ccoleman@redhat.com)
- bump(github.com/coreos/etcd):02697ca725e5c790cc1f9d0918ff22fad84cb4c5
  (ccoleman@redhat.com)
- Godeps.json formatting is wrong (ccoleman@redhat.com)
- probe delay (pweil@redhat.com)
- UPSTREAM: Don't use command pipes for exec/port forward (agoldste@redhat.com)
- stop swallowing errors (deads@redhat.com)
- allow everyone get,list access on the image group in openshift
  (deads@redhat.com)
- Fix loose links in README (kargakis@users.noreply.github.com)
- Adjust help template to latest version of Cobra (contact@fabianofranz.com)
- bump(github.com/inconshreveable/mousetrap):
  76626ae9c91c4f2a10f34cad8ce83ea42c93bb75C (contact@fabianofranz.com)
- bump(github.com/spf13/cobra): b78326bb16338c597567474a3ff35d76b75b804e
  (contact@fabianofranz.com)
- bump(github.com/spf13/pflag): 18d831e92d67eafd1b0db8af9ffddbd04f7ae1f4
  (contact@fabianofranz.com)
- UPSTREAM: make .Stream handle error status codes (deads@redhat.com)
- Test switching contexts with osc project (deads@redhat.com)
- set context namespace in generated .kubeconfig (deads@redhat.com)
- Add image streams to the types handled by web console. (cewong@redhat.com)
- perform initial commit to write config (pweil@redhat.com)
- OpenShift auth handler for v2 docker registry (rpenta@redhat.com)
- UPSTREAM: add context to ManifestService methods (rpenta@redhat.com)
- OAuth secret config (jliggitt@redhat.com)
- Customize messenger styling fix bug Bug 1203949 to correct sidebar display in
  ie and resized logo to fix ie issue (sgoodwin@redhat.com)
- Fix 'tito release' (sdodson@redhat.com)
- Project life-cycle updates (decarr@redhat.com)
- Fix nil ImageStreamGetter (agoldste@redhat.com)
- Image stream validations (agoldste@redhat.com)
- Enable namespace exists and namespace lifecycle admission controllers
  (decarr@redhat.com)
- More uniform use of %%{name} macro (sdodson@redhat.com)
- Add /etc/openshift to rpm packaging (sdodson@redhat.com)
- Updated #1525 leftovers in sample-app (maszulik@redhat.com)
- Bug 1206109: Handle specified tags that don't exist in the specified image
  repository (kargakis@users.noreply.github.com)
- Register lower and camelCase for v1beta1 (decarr@redhat.com)
- The build-logs command needs a cluster admin to run, make it clear in README
  (contact@fabianofranz.com)
- print builds as part of buildconfig description (bparees@redhat.com)
- only validate start args when NOT using config (deads@redhat.com)
- Validate CSRF in external oauth flow (jliggitt@redhat.com)
- Move labeling functions to util package (kargakis@users.noreply.github.com)
- Plumb CA and client cert options into basic auth IDP (jliggitt@redhat.com)
- add buildconfig reference field to builds (bparees@redhat.com)
- support subresources (deads@redhat.com)
- UPSTREAM: support subresources in api info resolver (deads@redhat.com)
- Move hostname detection warning to runtime (jliggitt@redhat.com)
- Make osc.exe work on Windows (jliggitt@redhat.com)
- add delays when handling retries so we don't tight loop (bparees@redhat.com)
- UPSTREAM: add a blocking accept method to RateLimiter
  https://github.com/GoogleCloudPlatform/kubernetes/pull/6314
  (bparees@redhat.com)
- Revert to handle error without glog.Fatal (nakayamakenjiro@gmail.com)
- display pretty strings for policy rule extensions (deads@redhat.com)
- remove dead parameters from openshift start (deads@redhat.com)
- UPSTREAM: Do not log errors where the event already exists
  (ccoleman@redhat.com)
- Implement an `osc status` command that groups resources by their
  relationships (ccoleman@redhat.com)
- Replace hostname -f with unmae -n (nakayamakenjiro@gmail.com)
- bump(github.com/gonum/graph):f6ac2b0f80f5a28ee70af78ce415393b37bcd6c1
  (ccoleman@redhat.com)
- Wrap proxy command (kargakis@users.noreply.github.com)
- go vet test (kargakis@users.noreply.github.com)
- Update config arg in Readme to be after command (ccoleman@redhat.com)
- Fix broken cli commands in README (ccoleman@redhat.com)
- Add description for --master option of openshift-master start
  (nakayamakenjiro@gmail.com)
- Use imageConfig in node (jliggitt@redhat.com)
- Output config errors better (jliggitt@redhat.com)
- Integrating help and usage templates in all commands
  (contact@fabianofranz.com)
- UPSTREAM Client must specify a resource version on finalize
  (decarr@redhat.com)
- Fix OAuth redirect (jliggitt@redhat.com)
- Show error on login redirect without token (jliggitt@redhat.com)
- Deprecate ImageRepository, add ImageStream (agoldste@redhat.com)
- UPSTREAM: Pass ctx to Validate, ValidateUpdate (agoldste@redhat.com)
- Issue 1529 - fix regression in help templates (contact@fabianofranz.com)
- fix typo (pweil@redhat.com)
- Remove the use of checkErr in our codebase (ccoleman@redhat.com)
- Add compile dependency on Kubernetes namespace controller (decarr@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes/pkg/namespace:8d94c43e705824f2
  3791b66ad5de4ea095d5bb32) (decarr@redhat.com)
- Adjust default log levels for web console and log errors when the local
  storage user store is unavailable (jforrest@redhat.com)
- Update sample app README to use login and project commands
  (contact@fabianofranz.com)
- Updated sample-app output to match current state of work
  (maszulik@redhat.com)
- Test PushSecretName via extended tests (mfojtik@redhat.com)
- Separate e2e-user config file in end to end (jliggitt@redhat.com)
- Uncommenting test for headless services (abhgupta@redhat.com)
- Replacing "None" for service PortalIP with constant (abhgupta@redhat.com)
- return updated build+buildconfig objects on update (bparees@redhat.com)
- Changing projects with empty namespace should succeed (ccoleman@redhat.com)
- add db images to sample repos (bparees@redhat.com)
- new-app should treat image repositories as more specific than docker images
  (ccoleman@redhat.com)
- UPSTREAM: Encode binary assets in ASCII only (jliggitt@redhat.com)
- Restore asset tests on Jenkins (jliggitt@redhat.com)
- Rewrite deployment ImageRepo handling (ironcladlou@gmail.com)
- Send a birthcry event when openshift node starts (pmorie@gmail.com)
- Temporarily remove asset build failures from Jenkins (jliggitt@redhat.com)
- Set unix LF EOL for shell scripts (itconsense@gmail.com)
- Updated STI binary (maszulik@redhat.com)
- Tweak OAuth config (jliggitt@redhat.com)
- Verify identity reference (jliggitt@redhat.com)
- Fix node yaml config serialization, unify config reading helper methods
  (jliggitt@redhat.com)
- Use struct literal to build a new pipeline
  (kargakis@users.noreply.github.com)
- bump(github.com/openshift/source-to-
  image):957c66bdbe15daca7b3af41f2c311af160473796 (maszulik@redhat.com)
- Remove osin example (kargakis@users.noreply.github.com)
- bump(golang.org/x/oauth2):c4932a9b59a60daa02a28db1bb7be39d6ec2e542
  (kargakis@users.noreply.github.com)
- Remove duplicate oauth2 library (kargakis@users.noreply.github.com)
- Update vagrant cluster commands (jliggitt@redhat.com)
- Add helper for p12 cert creation (jliggitt@redhat.com)
- Update vagrant cert wiring (jliggitt@redhat.com)
- Fix build logs with authenticated node (jliggitt@redhat.com)
- Serve node/etcd over https (jliggitt@redhat.com)
- Use the Fake cAdvisor interface on Macs (ccoleman@redhat.com)
- resolve from references when creating builds
  https://bugzilla.redhat.com/show_bug.cgi?id=1206052 (bparees@redhat.com)
- fix ResetBefore* methods (pweil@redhat.com)
- Add a forced version tagger for --use-version (sdodson@redhat.com)
- Teach our tito tagger to use vX.Y.Z tags (sdodson@redhat.com)
- Reset rpm specfile version to 0.0.1, add RPM build docs to HACKING.md
  (sdodson@redhat.com)
- UPSTREAM: Fixing accidental hardcoding of priority function weight
  (abhgupta@redhat.com)
- UPSTREAM: Removing EqualPriority from the list of default priorities
  (abhgupta@redhat.com)
- UPSTREAM: Remove pods from the assumed pod list when they are deleted
  (abhgupta@redhat.com)
- UPSTREAM: Updating priority function weight based on specified configuration
  (abhgupta@redhat.com)
- Fix switching between contexts that don't have a namespace explicit
  (contact@fabianofranz.com)
- osc login must check if cert data were provided through flags before saving
  (contact@fabianofranz.com)
- Make test-end-to-end use osc login|project (contact@fabianofranz.com)
- UPSTREAM: fix godep hash from bad restore (pweil@redhat.com)
- Add deprecation warnings for OAUTH envvars (jliggitt@redhat.com)
- expose oauth config in config (deads@redhat.com)
- print from repo info for sti builds (bparees@redhat.com)
- rebase refactoring (pweil@redhat.com)
- UPSTREAM: eliminate fallback to root command when another command is
  explicitly requested (deads@redhat.com)
- UPSTREAM: Tone down logging in Kubelet for cAdvisor being dead
  (ccoleman@redhat.com)
- UPSTREAM: Make setSelfLink not bail out (ccoleman@redhat.com)
- UPSTREAM: need to make sure --help flags is registered before calling pflag
  (contact@fabianofranz.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: Disable systemd activation for DNS (ccoleman@redhat.com)
- UPSTREAM: Handle missing resolv.conf (ccoleman@redhat.com)
- UPSTREAM: Remove cadvisor_mock.go (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):f057a25b5d37a496c1ce25fbe1dc1
  b1971266240 (pweil@redhat.com)
- Bug 1206109 - build-chain: Set tags correctly
  (kargakis@users.noreply.github.com)
- new-app: Avoid extra declaration (kargakis@users.noreply.github.com)
- Moved LabelSelector and LabelFilter to their own bower component
  (jforrest@redhat.com)
- Wrap describe command (kargakis@users.noreply.github.com)
- Add extra tests for DNS and prepare for Headless services
  (ccoleman@redhat.com)
- DRYed test cases: clarified recursion check (somalley@redhat.com)
- Support headless services via DNS, fix base queries (ccoleman@redhat.com)
- add tag info to buildparameter output (bparees@redhat.com)
- Console now on /console (ccoleman@redhat.com)
- Move common template labels out of the objects description field
  (ccoleman@redhat.com)
- Make docker push quiet in builders (maszulik@redhat.com)
- Handle unexpected server errors more thoroughly in RequestToken
  (ccoleman@redhat.com)
- Issue 1200: use single quotes when printing usage for string flags
  (contact@fabianofranz.com)
- Comments (jliggitt@redhat.com)
- Lock down *min dependencies (jliggitt@redhat.com)
- Split identity and user objects (jliggitt@redhat.com)
- add how to disable security to the readme (deads@redhat.com)
- UPSTREAM: Fix namespace on delete (jliggitt@redhat.com)
- UPSTREAM: Ensure no namespace on create/update root scope types
  (jliggitt@redhat.com)
- relativize paths for master config (deads@redhat.com)
- clean up admin commands (deads@redhat.com)
- Fix panic when Source is not specified in CustomBuild (mfojtik@redhat.com)
- new-app: Fix typo (kargakis@users.noreply.github.com)
- Make 'osc project' use the provided io.Writer (d4rkn35t0@gmail.com)
- Remove hard-coded padding (jliggitt@redhat.com)
- Make service dependencies considerably more strict (sdodson@redhat.com)
- Show warning on terminating projects and disable Create button
  (jforrest@redhat.com)
- Test build-chain in hack/test-cmd (kargakis@users.noreply.github.com)
- Bug 1206419 - Handle empty namespace slice plus message fix
  (kargakis@users.noreply.github.com)
- Adding the the kubernetes and (future) openshift services to the list of
  Master server names (bleanhar@redhat.com)
- Fixed problems with deployment tests (maszulik@redhat.com)
- Move build generation logic to new endpoints (maszulik@redhat.com)
- Copying Build Labels into build Pod. (maszulik@redhat.com)
- Issue #333, #528 - add number to builds (maszulik@redhat.com)
- Issue #408 - Remove PodName from Build object (maszulik@redhat.com)
- add-user became add-role-to-user (ccoleman@redhat.com)
- Move to upstream list/watch (decarr@redhat.com)
- show buildconfig in describe output (bparees@redhat.com)
- Update all references to the console on port 8444 (jforrest@redhat.com)
- Implement scaffolding to purge project content on deletion
  (decarr@redhat.com)
- Asset changes needed to support a non / context root.  Global redirect to
  asset server or dump of api paths when / is requested. (jforrest@redhat.com)
- Initial changes to support console being served from same port as API or as
  its own server on a separate port (jliggitt@redhat.com)
- Drop From field validation check (kargakis@users.noreply.github.com)
- Make overwrite-policy require confirmation (ccoleman@redhat.com)
- Add an official 'openshift admin' command (ccoleman@redhat.com)
- UPSTREAM: eliminate fallback to root command when another command is
  explicitly requested (deads@redhat.com)
- Add unit tests for PushSecretName (mfojtik@redhat.com)
- Bug 1206109 - Default empty tag slice to 'latest'
  (kargakis@users.noreply.github.com)
- Fix typo (pmorie@gmail.com)
- Specifying the correct kubeconfig file for the minions in a cluster
  (abhgupta@redhat.com)
- fix missing serialization tag (deads@redhat.com)
- master and node config files should not contain backsteps (deads@redhat.com)
- Add a client cache and remove log.Fatal behavior from session ended
  (ccoleman@redhat.com)
- UPSTREAM: Tone down logging in Kubelet for cAdvisor being dead
  (ccoleman@redhat.com)
- hack/test-cmd.sh is flaky on macs (ccoleman@redhat.com)
- build-chain: Fix default namespace setup (kargakis@users.noreply.github.com)
- Removing --master flag from the openshift-node service (abhgupta@redhat.com)
- Inherit LOGLEVEL in Build pods from OpenShift (mfojtik@redhat.com)
- Require to have 'dockercfg' Secret data for PushSecretName
  (mfojtik@redhat.com)
- return a forbidden api status object (deads@redhat.com)
- tidy up MasterConfig getter location (deads@redhat.com)
- Expand validation and status spec (ironcladlou@gmail.com)
- Allow to specify PushSecretName in BuildConfig Output (mfojtik@redhat.com)
- Issue 1349 - osc project supports switching by context name
  (contact@fabianofranz.com)
- Expose project status from underlying namespace (decarr@redhat.com)
- Test pod describe in hack/test-cmd.sh (ccoleman@redhat.com)
- Improve the general message flow for login (ccoleman@redhat.com)
- add missing json def (pweil@redhat.com)
- reaper: Use NOHANG pattern instead of waiting for all children.
  (mrunalp@gmail.com)
- Exposing the scheduler config file option (abhgupta@redhat.com)
- eliminate bad defaults in create-kubeconfig (deads@redhat.com)
- Added image repository reference From field to STIBuildStrategy
  (yinotaurus@gmail.com)
- Revert "Added image repository reference From field to STIBuildStrategy"
  (ccoleman@redhat.com)
- create-node-config command (deads@redhat.com)
- Remove old geard docs (pmorie@gmail.com)
- Added image repository reference From field to STIBuildStrategy
  (yinotaurus@gmail.com)
- Bug 1196138 add newline char for: openshift ex router and registry, output
  (sspeiche@redhat.com)
- Introduce deployment hook proposal (ironcladlou@gmail.com)
- delegate to kube method for unknown resource kinds (deads@redhat.com)
- Output build dependencies of a specific image repository
  (kargakis@users.noreply.github.com)
- add rule to allow self-subject access reviews (deads@redhat.com)
- go vet pkg (kargakis@users.noreply.github.com)
- bump(github.com/awalterschulze/gographviz):20d1f693416d9be045340150094aa42035
  a41c9e (kargakis@users.noreply.github.com)
- Remove GOFLAGS arguments from Makefile (ccoleman@redhat.com)
- Force OPENSHIFT_PROFILE to be tested (ccoleman@redhat.com)
- Fix web profiling (ccoleman@redhat.com)
- ImageStreamImage/ImageRepositoryTag virtual rsrcs (agoldste@redhat.com)
- handle case where we have no build start time (bparees@redhat.com)
- add validation calls when we delegate cert commands (deads@redhat.com)
- pass master and public-master urls to create-all-certs (deads@redhat.com)
- make test-cmd more reliable on travis by pre-minting certs (deads@redhat.com)
- Use semantic deep equal for comparison (ccoleman@redhat.com)
- Refactor 12 (ccoleman@redhat.com)
- Fixed buildlogs (maszulik@redhat.com)
- Add info messages for end-to-end (ccoleman@redhat.com)
- Convert travis to make check-test (ccoleman@redhat.com)
- Refactor 11 (ccoleman@redhat.com)
- Kubelet health check fails when not sent to hostname (ccoleman@redhat.com)
- Ensure integration tests run when Docker is not available
  (ccoleman@redhat.com)
- Add check-test in between check and test (ccoleman@redhat.com)
- Remove debug logging from image controller (ccoleman@redhat.com)
- Refactor 10 (ccoleman@redhat.com)
- Refactor 9 (ccoleman@redhat.com)
- Refactor 8 (ccoleman@redhat.com)
- Refactor 7 (ccoleman@redhat.com)
- Refactor 6 (ccoleman@redhat.com)
- Refactor 5 (ccoleman@redhat.com)
- Refactor 4 (ccoleman@redhat.com)
- Refactor 3 (ccoleman@redhat.com)
- Refactor 2 (ccoleman@redhat.com)
- Refactor 1 (ccoleman@redhat.com)
- UPSTREAM: Remove global map from healthz (ccoleman@redhat.com)
- UPSTREAM: Lazily init systemd for code that includes cadvisor but doesn't use
  it (ccoleman@redhat.com)
- UPSTREAM: Make setSelfLink not bail out (ccoleman@redhat.com)
- UPSTREAM: need to make sure --help flags is registered before calling pflag
  (contact@fabianofranz.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: Disable systemd activation for DNS (ccoleman@redhat.com)
- UPSTREAM: Handle missing resolv.conf (ccoleman@redhat.com)
- UPSTREAM: Remove cadvisor_mock.go (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):c5f73516b677434d9cce7d07e460b
  b712c85e00b (ccoleman@redhat.com)
- Fix how OPENSHIFT_INSECURE is parsed (agoldste@redhat.com)
- Unset KUBECONFIG prior to hack/test-cmd.sh (ccoleman@redhat.com)
- Add build duration to web console (jforrest@redhat.com)
- Group all build extended tests into one file (mfojtik@redhat.com)
- Unify 'testutil' as package name in tests (mfojtik@redhat.com)
- Add test-extended.sh into Makefile (mfojtik@redhat.com)
- Add v2 registry (agoldste@redhat.com)
- UPSTREAM: use docker's ParseRepositoryTag when pulling images
  (agoldste@redhat.com)
- bump(docker/docker):c1639a7e4e4667e25dd8c39eeccb30b8c8fc6357
  (agoldste@redhat.com)
- bump(docker/distribution):70560cceaf3ca9f99bfb2d6e84312e05c323df8b
  (agoldste@redhat.com)
- bump(Sirupsen/logrus):2cea0f0d141f56fae06df5b813ec4119d1c8ccbd
  (agoldste@redhat.com)
- Pre-push ruby image for extended tests (mfojtik@redhat.com)
- handle trailing slashes (deads@redhat.com)
- Rework ui presentation and markup for builds view. Inclusion of noscript
  messages. Fix flex mixin which had ie 10 issue (sgoodwin@redhat.com)
- describe canceled build duration (bparees@redhat.com)
- Copy ImageRepository annotations to image (agoldste@redhat.com)
- add create-client command (deads@redhat.com)
- add identities for router and registry (deads@redhat.com)
- make login test avoid default kubeconfig chain (deads@redhat.com)
- Fix typo in extended docker test (mfojtik@redhat.com)
- Add dockerImageRepository to sample custom builder image repo
  (cewong@redhat.com)
- Removed copies of util.DefaultClientConfig (contact@fabianofranz.com)
- Fix panic during timeout (ironcladlou@gmail.com)
- Rebasing upstream to allow any number of kubeconfig files
  (contact@fabianofranz.com)
- UPSTREAM: allow any number of kubeconfig files (contact@fabianofranz.com)
- Reworked integration tests and added extended tests (mfojtik@redhat.com)
- Add ./hack/test-extended.sh (mfojtik@redhat.com)
- bump(github.com/matttproud/golang_protobuf_extensions/ext):ba7d65ac66e9da93a7
  14ca18f6d1bc7a0c09100c (kargakis@users.noreply.github.com)
- auto-provision policy bindings for bootstrapping (deads@redhat.com)
- properly handle missing policy document (deads@redhat.com)
- Issue 1348 - add support to expose persistent flags in help
  (contact@fabianofranz.com)
- Query the sample app during e2e to make sure MySQL responds
  (nagy.martin@gmail.com)
- Make console logging be enabled/disabled with log levels and scoped loggers
  (jforrest@redhat.com)
- use bootstrap policy constants for namespace and role default
  (deads@redhat.com)
- Set master IP correctly when starting kubernetes (jliggitt@redhat.com)
- added test case for empty name argument (somalley@redhat.com)
- examples, docs: describe user creation thoroughly (ttomecek@redhat.com)
- separate out bootstrap policy (deads@redhat.com)
- Remove docker IP from certs (jliggitt@redhat.com)
- Issue 1356 - setup should either save cert file or data
  (contact@fabianofranz.com)
- add completion time field to builds (bparees@redhat.com)
- Fix create-server-cert --signer-signer-{cert,key,serial} stutter
  (sdodson@redhat.com)
- Use new openshift/mysql-55-centos7 image for sample-app
  (nagy.martin@gmail.com)
- Change BindAddrArg to ListenArg (jliggitt@redhat.com)
- Fix grammar in README (cewong@redhat.com)
- Restore ability to run in http (jliggitt@redhat.com)
- Group node certs under a single directory (jliggitt@redhat.com)
- Initial config validation (jliggitt@redhat.com)
- Bug 1202672 - handle osc project without argument and no namespace set
  (contact@fabianofranz.com)
- UPSTREAM: remove exec ARGS log message (agoldste@redhat.com)
- Call sdNotify as soon as we've started OpenShift API server or node
  (sdodson@redhat.com)
- Make file references in config relative to config files (jliggitt@redhat.com)
- Preserve tag when v1 pull by id is possible (agoldste@redhat.com)
- Change how tags and status events are recorded (ccoleman@redhat.com)
- Use the dockerImageReference tag when pushed (ccoleman@redhat.com)
- Add an initial importer for Image Repositories (ccoleman@redhat.com)
- Add osc exec and port-forward commands (agoldste@redhat.com)
- Issue1317 - Added error logging to webhook controller (maszulik@redhat.com)
- Bug 1202686 - fixes forbidden error detection (contact@fabianofranz.com)
- add serializeable start config (deads@redhat.com)
- Error handling for web console, adds notification service and limits
  websocket re-connection retries (jforrest@redhat.com)
- Remove unwanted ng-if check from template catalog (jforrest@redhat.com)
- Minor message improvement (contact@fabianofranz.com)
- Generation command tests (cewong@redhat.com)
- Project is not required for a successful login (contact@fabianofranz.com)
- Introducing client login and setup - 'osc login' (contact@fabianofranz.com)
- Introducing client projects switching - 'osc project'
  (contact@fabianofranz.com)
- UPSTREAM: loader allows multiple sets of loading rules
  (contact@fabianofranz.com)
- Temporary fix to bump timeout to 300s (sdodson@redhat.com)
- Speed up installation of etcd (mfojtik@redhat.com)
- Handle wildcard resolution of services (ccoleman@redhat.com)
- Remove commented imports (kargakis@users.noreply.github.com)
- Make tests for the Docker parser more robust
  (kargakis@users.noreply.github.com)
- Allow test of only master to start successfully (ccoleman@redhat.com)
- Remove excessive logging (ccoleman@redhat.com)
- Tease apart separate concerns in RetryController (ccoleman@redhat.com)
- UPSTREAM: Don't hang when registering zero nodes (ccoleman@redhat.com)
- UPSTREAM: Temporarily relax annotations further (ccoleman@redhat.com)
- Always use port 8053 in integration tests (ccoleman@redhat.com)
- Add DockerImageReference type (agoldste@redhat.com)
- cancel-build: Use BuildLogs client method (kargakis@users.noreply.github.com)
- Removed extra tools imports (soltysh@gmail.com)
- Consolidate image reference generation/lookup (agoldste@redhat.com)
- path based ACLs (pweil@redhat.com)
- Add additional items to vm-provision-full (ccoleman@redhat.com)
- Switch default route dns suffix to "router.default.local" (smitram@gmail.com)
- Fixes to route allocator plugin PR as per @smarterclayton comments.
  (smitram@gmail.com)
- Add simple shard allocator plugin to autogenerate host names for routes based
  on service and namespace and hook it into the route processing [GOFM].
  (smitram@gmail.com)
- Various image updates (agoldste@redhat.com)
- fix start-build follow to stop following eventually (deads@redhat.com)
- Need more detail for contributing to v3 web console, started an architecture
  section (jforrest@redhat.com)
- Add more visual separation between builds, add copy to clipboard for webhook
  URLs (jforrest@redhat.com)
- integration test (deads@redhat.com)
- comments 2 (deads@redhat.com)
- check if template exists (bparees@redhat.com)
- Fix temporary platform builder image names for generation tools
  (cewong@redhat.com)
- Provide both a host and guest profile (sdodson@redhat.com)
- comments 1 (deads@redhat.com)
- allow bootstrap policy to span namespaces (deads@redhat.com)
- Fix bindata for rework page structure to use flexbox so that sidebar columns
  extend (jforrest@redhat.com)
- Bug 1200346 - need to convert quota values including SI prefixes for
  comparisions (jforrest@redhat.com)
- role and rolebinding printers and describers (deads@redhat.com)
- add role and rolebinding gets and lists (deads@redhat.com)
- Bug 1200684: Retrieve logs from failed builds
  (kargakis@users.noreply.github.com)
- add detail to forbidden message (deads@redhat.com)
- Rework page structure to use flexbox so that sidebar columns extend without
  dynamically setting height Adjustments to project-nav, primarily the label-
  selector so that it doesn't wrap and tighten up the look.
  (sgoodwin@redhat.com)
- Adds reaping capability to openshift. (mrunalp@gmail.com)
- Allow OpenShift to start on an airplane (ccoleman@redhat.com)
- UPSTREAM: Handle missing resolv.conf (ccoleman@redhat.com)
- Remove self closing tags (jliggitt@redhat.com)
- added notes for Vagrant users in sample-app README doc (somalley@redhat.com)
- Allow stored templates to be referenced from osc process (mfojtik@redhat.com)
- DNS default check should not be in server.Config (ccoleman@redhat.com)
- Move glog.Fatal to error propagation (jliggitt@redhat.com)
- Add cert validation options to requestheader (jliggitt@redhat.com)
- Make sure we don't swallow errors from inner Convert calls
  (maszulik@redhat.com)
- Bug 119409 - fix source URI generated by new-app (cewong@redhat.com)
- Management Console - Create from template (cewong@redhat.com)
- remove test-integration.sh from make test.  Resolves #1255 (pweil@redhat.com)
- Fixed URLs for webhooks presented in osc describe (maszulik@redhat.com)
- Add DNS support to OpenShift (ccoleman@redhat.com)
- UPSTREAM: Disable systemd activation for DNS (ccoleman@redhat.com)
- bump(github.com/skynetservices/skydns):f18bd625a71b5d013b6e6288d1c7ec8796a801
  88 (ccoleman@redhat.com)
- Make it easy to export certs to curl (ccoleman@redhat.com)
- Address some cli usage msg inconsistencies
  (kargakis@users.noreply.github.com)
- Remove use of Docker registry code (ccoleman@redhat.com)
- Remove dockerutils (ccoleman@redhat.com)
- UPSTREAM: docker/utils does not need to access autogen (ccoleman@redhat.com)
- Remove fake docker autogen package (ccoleman@redhat.com)
- create the buildconfig before creating the first imagerepo
  (bparees@redhat.com)
- Only build images during build-cross (ironcladlou@gmail.com)
- add redirect to list of approved verbs (deads@redhat.com)
- only resolve roles for bindings that matter (deads@redhat.com)
- Implement logs streaming option when starting a build
  (kargakis@users.noreply.github.com)
- Turn on quota related admission control plug-ins (decarr@redhat.com)
- use master ip address so that minions can reach master in multi-node setup.
  (pweil@redhat.com)
- allow current-user subjectaccessreview (deads@redhat.com)
- Use Docker parser when manipulating Dockerfiles
  (kargakis@users.noreply.github.com)
- Fix broken --parameters switch for process (mfojtik@redhat.com)
- Add test to exercise invalid parameter in Template (mfojtik@redhat.com)
- Return error when Template generator failed to generate parameter value
  (mfojtik@redhat.com)
- Fix escaping and value (dmcphers@redhat.com)
- Make sure image, namespace, and tag match (jliggitt@redhat.com)
- retry build errors (bparees@redhat.com)
- Fix new-app generation from local source (cewong@redhat.com)
- add namespace to internal route keys (pweil@redhat.com)
- Add templates to list of authorized resources (cewong@redhat.com)
- add export KUBECONFIG to osc create example
  (jeff.mccormick@crunchydatasolutions.com)
- switch access review users and groups to stringsets (deads@redhat.com)
- add subject access review integration tests (deads@redhat.com)
- Add BuildLogs method on Client (kargakis@users.noreply.github.com)
- Switch services to notify (sdodson@redhat.com)
- Add systemd notification on service startup completion (sdodson@redhat.com)
- bump(github.com/coreos/go-systemd): 2d21675230a81a503f4363f4aa3490af06d52bb8
  (sdodson@redhat.com)
- Revert "add annotations to image repos" (bparees@redhat.com)
- Bump sti-image-builder to STI v0.2 (sdodson@redhat.com)
- prevent changes to rolebinding.RoleRef (deads@redhat.com)
- Removed hack/config-go.sh from HACKING.md, it's not used anymore.
  (maszulik@redhat.com)
- Bug 1191960 - Remove --master from usage text for ex generate
  (cewong@redhat.com)
- Update Jenkins example with auth identity (jliggitt@redhat.com)
- fix nodelist defaulting (deads@redhat.com)
- Remove extra error check (kargakis@users.noreply.github.com)
- add annotations to image repos (bparees@redhat.com)
- fix osc create example to include cert dir kubconfig parameter
  (jeff.mccormick@crunchydatasolutions.com)
- add routes to services (pweil@redhat.com)
- exit with error if no tests are found (bparees@redhat.com)
- Add default template label to sample app templates (cewong@redhat.com)
- Fix router integration test (jliggitt@redhat.com)
- Add version command for all binaries/symlinks
  (kargakis@users.noreply.github.com)
- Updating ruby-20 links and image name so they point to new repo and image
  (j.hadvig@gmail.com)
- Better output for integration tests (ccoleman@redhat.com)
- Add RootResourceAccessReview to replace use of empty namespace
  (ccoleman@redhat.com)
- Better output for integration tests (ccoleman@redhat.com)
- UPSTREAM: Validate TCPSocket handler correctly (ccoleman@redhat.com)
- UPSTREAM: Relax constraints on container status while fetching container logs
  (vishnuk@google.com)
- Remove references to old volume source, handle endpoints change
  (ccoleman@redhat.com)
- UPSTREAM: Make setSelfLink not bail out (ccoleman@redhat.com)
- UPSTREAM: special command "help" must be aware of context
  (contact@fabianofranz.com)
- UPSTREAM: need to make sure --help flags is registered before calling pflag
  (contact@fabianofranz.com)
- UPSTREAM: Disable auto-pull when tag is "latest" (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: Add 'release' field to raven-go (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):6241a211c8f35a6147aa3a0236f68
  0ffa8e11037 (ccoleman@redhat.com)
- bump(github.com/docker/docker):7d2188f9955d3f2002ff8c2e566ef84121de5217
  (kargakis@users.noreply.github.com)
- Wrap some commands to display OpenShift-specific usage msg
  (kargakis@users.noreply.github.com)
- support multiple go versions (bparees@redhat.com)
- fix up the jenkins example (bparees@redhat.com)
- extend the wait time for the project authorization cache (deads@redhat.com)
- Refactor deploy controllers to use RetryController (ironcladlou@gmail.com)
- Specify UI bind address in integration tests (jliggitt@redhat.com)
- reconnect --image (deads@redhat.com)
- Add htpasswd file param (jliggitt@redhat.com)
- Prevent challenging client from looping (jliggitt@redhat.com)
- Simplify auto-grant (jliggitt@redhat.com)
- use rpm instead of build haproxy from source (tdawson@redhat.com)
- fix nodelist access for kube master (deads@redhat.com)
- enforce authorization (deads@redhat.com)
- Put BuildConfig labels into metadata for sample-app (mfojtik@redhat.com)
- Revert "Support multiple Dockerfiles with custom-docker-builder"
  (bparees@redhat.com)
- Match project name validation to namespace name validation
  (jliggitt@redhat.com)
- Make "new-project --admin" reuse "add-user" (jliggitt@redhat.com)
- Add test to make sure osc can list new projects (jliggitt@redhat.com)
- Explicitly set --kubeconfig when starting node (sdodson@redhat.com)
- let project admins use resource access review (deads@redhat.com)
- Fix Used vs Max quota comparison in web console (jforrest@redhat.com)
- add context namespacing filter (deads@redhat.com)
- Re-enable project auth cache, add UI integration test (jliggitt@redhat.com)
- Output more details on pod details page in web console (jforrest@redhat.com)
- Allow multiple tags to refer to the same image (agoldste@redhat.com)
- Add controller retry support scaffolding (ironcladlou@gmail.com)
- UPSTREAM: Support AddIfNotPresent function (ironcladlou@gmail.com)
- Fix TLS EOF errors in log at start (jliggitt@redhat.com)
- Ensure create of master policy namespace happens after policy will allow it
  (jliggitt@redhat.com)
- Rework --kubeconfig handler, misc tweaks (jliggitt@redhat.com)
- make start.config immutable (deads@redhat.com)
- Fixed contextDir conversion after moving it from DockerBuildStrategy to
  BuildSource (maszulik@redhat.com)
- Make builder image naming consistent between build strategy describe
  (maszulik@redhat.com)
- Add verify-jsonformat to Travis (mfojtik@redhat.com)
- Fix formatting and errors in JSON files (mfojtik@redhat.com)
- Added ./hack/verify-jsonformat.sh (mfojtik@redhat.com)
- Support multiple Dockerfiles with custom-docker-builder
  (cole.mickens@gmail.com)
- Set global timer to autoupdate relative timestamps in the UI
  (jforrest@redhat.com)
- remove use_local env (bparees@redhat.com)
- Builds page - group builds by build config and show more details for build
  configs (jforrest@redhat.com)
- make build output optional (bparees@redhat.com)
- use ruby-20-centos7 in generated buildconfig (bparees@redhat.com)
- Use --from-build flag only for re-running builds
  (kargakis@users.noreply.github.com)
- Changed image names for ImageRepository objects, since it was using two
  exactly the same in different tests (maszulik@redhat.com)
- add liveness probe to router (pweil@redhat.com)
- Fix docs (kargakis@users.noreply.github.com)
- Rename 'Clean' to 'Incremental' in STI builder (mfojtik@redhat.com)
- Changed Info->Infof to have the variable printed (maszulik@redhat.com)
- Add optional e2e UI tests (jforrest@redhat.com)
- bump(github.com/openshift/source-to-
  image):c0c154efcba27ea5693c428bfe28560c220b4850 (mfojtik@redhat.com)
- Make cli examples consistent across OpenShift
  (kargakis@users.noreply.github.com)
- Validate usernames don't contain problematic URL sequences
  (jliggitt@redhat.com)
- Use a versioned printer for rollback configs (ironcladlou@gmail.com)
- Fix broken deployer pod GenerateName reference (ironcladlou@gmail.com)
- update must gather for policy (deads@redhat.com)
- Generate: handle image with multiple ports in EXPOSE statement
  (cewong@redhat.com)
- Update command parameter and help text to refer to single port
  (cewong@redhat.com)
- update readme to take advantage of authorization (deads@redhat.com)
- Make Clients API consistent (kargakis@users.noreply.github.com)
- Add htpasswd SHA/MD5 support (jliggitt@redhat.com)
- route definition requires name in metadata (akram.benaissi@free.fr)
- Rename BaseImage -> Image for DockerBuildStrategy to be consistent with
  STIBuilderStrategy about field naming (maszulik@redhat.com)
- Generate master and public-master .kubeconfig contexts (jliggitt@redhat.com)
- Add options to clear authorization headers for basic/bearer auth
  (jliggitt@redhat.com)
- better build names (bparees@redhat.com)
- pretty up policy describer (deads@redhat.com)
- UPSTREAM: get the keys from a string map (deads@redhat.com)
- create policy cache (deads@redhat.com)
- Add 'deny' password authenticator (jliggitt@redhat.com)
- Fix case (dmcphers@redhat.com)
- Add a command to install / check a registry (ccoleman@redhat.com)
- refactor authorization for sanity (deads@redhat.com)
- Card devexp_426 - Force clean builds by default for STI (maszulik@redhat.com)
- Better management of the systemd services (marek.goldmann@gmail.com)
- Fix loop period to stop pegging CPU, add project-spawner (decarr@redhat.com)
- List projects enforces authorization (decarr@redhat.com)
- fix formatting (bparees@redhat.com)
- Bug 1194487 - Fix generate command repository detection (cewong@redhat.com)
- Integration tests need to run in separate processes (ccoleman@redhat.com)
- Bug 1190578 - Should prompt clear error when generate an application list
  code in a non-source code repository. (cewong@redhat.com)
- copy build labels from buildconfig (bparees@redhat.com)
- Update test cases and docs to use `openshift ex router` (ccoleman@redhat.com)
- prevent privilege escalation (deads@redhat.com)
- Add a router command to install / check the routers (ccoleman@redhat.com)
- UPSTREAM: Expose converting client.Config files to Data (ccoleman@redhat.com)
- Remove cors headers from proxied connections (jliggitt@redhat.com)
- Strip auth headers before proxying, add auth headers on upgrade requests
  (jliggitt@redhat.com)
- Strip access_token param from requests in auth layer (jliggitt@redhat.com)
- Bug 1190576: Improve error message when trying to use non-existent reference
  (cewong@redhat.com)
- bump(github.com/openshift/source-to-
  image):ad5adc054311686baf316cd8bf91c4d42ae1bd4e (bparees@redhat.com)
- Improve help for creating / being added to new projects (jliggitt@redhat.com)
- Fix dangling commas in example json files (cewong@redhat.com)
- Add labels to templates (cewong@redhat.com)
- Vagrantfile: default libvirt box now with actual openshift
  (lmeyer@redhat.com)
- document sti images (bparees@redhat.com)
- Update docs (jliggitt@redhat.com)
- add namespaces to authorization rules (deads@redhat.com)
- Inline bootstrapped certs in client .kubeconfig files (jliggitt@redhat.com)
- UPSTREAM: Let .kubeconfig populate ca/cert/key data and basic-auth
  username/password in client configs (jliggitt@redhat.com)
- authorize non-resource urls (deads@redhat.com)
- use multiline in regex matching (bparees@redhat.com)
- Handle empty label selectors in web console (jforrest@redhat.com)
- Remove dead links from cli doc (kargakis@users.noreply.github.com)
- Capture errors from BuildParameters conversion (mfojtik@redhat.com)
- Fix integration (mfojtik@redhat.com)
- Move ContextDir under BuildSource (mfojtik@redhat.com)
- Add support for ContextDir in STI build (mfojtik@redhat.com)
- Fix Origin code to incorporate changes in STI (mfojtik@redhat.com)
- bump(github.com/openshift/source-to-image):
  1338bff33b5c46acc02840f88a9b576a1b1fa404 (mfojtik@redhat.com)
- bump(github.com/fsouza/go-
  dockerclient):e1e2cc5b83662b894c6871db875c37eb3725a045 (mfojtik@redhat.com)
- UPSTREAM: Surface load errors when reading .kubeconfig files
  (jliggitt@redhat.com)
- Handle k8s edge cases in the web console overview (jforrest@redhat.com)
- Give our local built docker images unique ids, and push that id
  (ccoleman@redhat.com)
- UPSTREAM: move setSelfLink logging to v(5) (deads@redhat.com)
- make useLocalImages the default and remove configurability
  (bparees@redhat.com)
- Fix build-in-docker.sh, use $(), not ${} (nagy.martin@gmail.com)
- validate route name and host (pweil@redhat.com)
- make sure rolebinding names are unique (deads@redhat.com)
- Use git fetch && reset if the given repo was cloned already
  (ppalaga@redhat.com)
- Replacing old openshift/nodejs-0-10-centos with new
  openshift/nodejs-010-centos7 (j.hadvig@gmail.com)
- Replace hardcoded-library-path (nakayamakenjiro@gmail.com)
- Fixing typos (dmcphers@redhat.com)
- Project is Kubernetes Namespace (decarr@redhat.com)
- Refactor deploy package for error handling support (ironcladlou@gmail.com)
- ignore selflinking error (deads@redhat.com)
- Implement a Template REST endpoint using the generic store
  (ccoleman@redhat.com)
- sync policy doc to reality (deads@redhat.com)
- Turn on resource quota manager to collect usage stats (decarr@redhat.com)
- Improve release tar naming (ironcladlou@gmail.com)
- Explicit build (ccoleman@redhat.com)
- Platform independent image builds (ironcladlou@gmail.com)
- bump(github.com/GoogleCloudPlatform/kubernetes/plugin/pkg/admission:c977a4586
  42b4dbd8c3ad9cfc9eecafc85fb6183) (decarr@redhat.com)
- Add compile dependency for Kubernetes admission control plugins
  (decarr@redhat.com)
- switch to kubernetes authorization info (deads@redhat.com)
- UPSTREAM: expose info resolver (deads@redhat.com)
- Remove GOPATH from build-in-docker.sh script (mfojtik@redhat.com)
- Unify all client Factories into one location (ccoleman@redhat.com)
- Move coverage output processing to the end (dmcphers@redhat.com)
- Switch to using request context mapper (jliggitt@redhat.com)
- router websocket support (pweil@redhat.com)
- add new-project command (deads@redhat.com)
- Add fixtures to test edge cases in the web console (jforrest@redhat.com)
- Fix htmlmin linebreak issue (jliggitt@redhat.com)
- Provide useful message when CERT_DIR is not set in install-registry.sh
  (mfojtik@redhat.com)
- Switch namespaced URL paths from ns/ to namespaces/ (jforrest@redhat.com)
- UPSTREAM: Distinguish between NamespaceAll and NamespaceDefault
  (ccoleman@redhat.com)
- use origin-base for base image (bparees@redhat.com)
- e2e without root fails because certs can't be viewed by wait_for_url
  (ccoleman@redhat.com)
- Tolerate Docker not being present when using all-in-one (ccoleman@redhat.com)
- Update registries to remove async channel (ccoleman@redhat.com)
- Compile time changes (ccoleman@redhat.com)
- UPSTREAM: Fix cross-namespace queries (ccoleman@redhat.com)
- UPSTREAM: Allow kubelet to run without Docker (ccoleman@redhat.com)
- UPSTREAM: Allow SetList to work against api.List (ccoleman@redhat.com)
- UPSTREAM: Disable auto-pull when tag is "latest" (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: Add 'release' field to raven-go (ccoleman@redhat.com)
- UPSTREAM: special command "help" must be aware of context
  (contact@fabianofranz.com)
- UPSTREAM: need to make sure --help flags is registered before calling pflag
  (contact@fabianofranz.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):c977a458642b4dbd8c3ad9cfc9eec
  afc85fb6183 (ccoleman@redhat.com)
- Stop referencing kubecfg now that it is deleted upstream
  (ccoleman@redhat.com)
- Fix several typos (rhcarvalho@gmail.com)
- Note on using docker with --insecure-registry
  (kargakis@users.noreply.github.com)
- Use p12-encoded certs on OS X (jliggitt@redhat.com)
- Initialize image by using struct literal (kargakis@users.noreply.github.com)
- *AccessReviews (deads@redhat.com)
- pass authorizer/attributebuilder pair into master (deads@redhat.com)
- Update the custom tagger and builder to provide OpenShift ldflags
  (sdodson@redhat.com)
- put templates in correct dir for install registry script (bparees@redhat.com)
- UPSTREAM: properly handle mergo map versus value rules: 4416
  (deads@redhat.com)
- Add missing Requires (nakayamakenjiro@gmail.com)
- Explain why Stop is called like that (michaliskargakis@gmail.com)
- Allow setting final logout uri (jliggitt@redhat.com)
- tolerate missing roles (deads@redhat.com)
- update in-container steps to setup registry properly (bparees@redhat.com)
- Making race an option for sh scripts (dmcphers@redhat.com)
- Fixing test coverage reporting (dmcphers@redhat.com)
- Generate client configs for nodes, provider-qualify and add groups to certs
  (jliggitt@redhat.com)
- add resourceName to policy (deads@redhat.com)
- Use LabelSelector in overview to associate pods to a service
  (jforrest@redhat.com)
- Issue 865: Fixed build integration tests. (maszulik@redhat.com)
- Validate image repository (michaliskargakis@gmail.com)
- Fix off-by-1 error (jliggitt@redhat.com)
- Support namespace in path for requesting k8s api from web console
  (jforrest@redhat.com)
- Bug 1191824 - Fixing typo (bleanhar@redhat.com)
- Require network when starting openshift-master (jolamb@redhat.com)
- Add project settings page and show quota and limit ranges for the project
  (jforrest@redhat.com)
- Attempt to manipulate images path conditionally (sdodson@redhat.com)
- Change ORIGIN_OAUTH_* env vars to OPENSHIFT_OAUTH_* (jliggitt@redhat.com)
- Bug 1191354 - must save username to .kubeconfig correctly
  (contact@fabianofranz.com)
- Use kubernetes user.Info interface (jliggitt@redhat.com)
- add policy watches (deads@redhat.com)
- Update the web console to request k8s api on v1beta3 (jforrest@redhat.com)
- Use Warningf instead of Warning so formatting works (nagy.martin@gmail.com)
- Bug 1190095 - useless entry "nameserver <nil>" is in docker container
  resolv.conf (bleanhar@redhat.com)
- deploymentconfigs permission typo (deads@redhat.com)
- Removed all Google copyrights leftovers (maszulik@redhat.com)
- e2e formatting (deads@redhat.com)
- tighten bootstrap policy (deads@redhat.com)
- Change references from alpha to beta release (sdodson@redhat.com)
- Default session secret to unknowable value (jliggitt@redhat.com)
- Make token lifetimes configurable (jliggitt@redhat.com)
- Allow denying a prompted OAuth grant (jliggitt@redhat.com)
- Make user header configurable (jliggitt@redhat.com)
- remove deny and negations (deads@redhat.com)
- Use chown for build-in-docker.sh output binaries (nagy.martin@gmail.com)
- Make sure vagrant development environment works well with new docker-io
  (marek.goldmann@gmail.com)
- move cleanup to its own section (bparees@redhat.com)
- Comment on redirecting to login on 0 codes (jliggitt@redhat.com)
- Add better instructions around using vagrant (dmcphers@redhat.com)
- Prevent browsers from prompting to send bogus client certs
  (jliggitt@redhat.com)
- add edge terminated route to sample app (pweil@redhat.com)
- make more intelligent kubeconfig merge (deads@redhat.com)
- Register used mime types (jliggitt@redhat.com)
- use tags from imagerepos when constructing new builds (bparees@redhat.com)
- Update example project json (jliggitt@redhat.com)
- Check SELinux labels when building in docker (nagy.martin@gmail.com)
- Various idiomatic fixes throughout the repo (michaliskargakis@gmail.com)
- Check for unspecified port once (michaliskargakis@gmail.com)
- Generate shorter tags when building release tars (ccoleman@redhat.com)
- Update start help (ccoleman@redhat.com)
- Tweak the flag for --images to indicate applies to master and node
  (ccoleman@redhat.com)
- Improve the default osc help page (ccoleman@redhat.com)
- Display more information when an app is automatically created
  (ccoleman@redhat.com)
- make remove-group from role check all bindings (deads@redhat.com)
- Improve error handling and logging for builds (cewong@redhat.com)
- UPSTREAM: Use name from server when displaying create/update
  (ccoleman@redhat.com)
- Correlate deployed pods with their deployments (ironcladlou@gmail.com)
- Remove comments from minified HTML (jliggitt@redhat.com)
- Preserve newlines in html (jliggitt@redhat.com)
- Add upgrade-aware HTTP proxy (agoldste@redhat.com)
- Handle multiple builder matches in generate command (cewong@redhat.com)
- OAuth api printers (jliggitt@redhat.com)
- Set user fullname correctly, initialize identity mappings fully
  (jliggitt@redhat.com)
- Set KUBECONFIG path for openshift-node (sdodson@redhat.com)
- Sort ports for service generation and select first port (cewong@redhat.com)
- Enable `osc new-app` and simplify some of the rough edges for launch
  (ccoleman@redhat.com)
- Command for displaying global options is "osc options" in help
  (contact@fabianofranz.com)
- Delete token on logout (jliggitt@redhat.com)
- Syntax consistency between help templates (contact@fabianofranz.com)
- Fixes base command reference (osc || openshift cli) in help
  (contact@fabianofranz.com)
- RPMs: Fix upgrades for the tuned profile (sdodson@redhat.com)
- Better footer messages in help (contact@fabianofranz.com)
- Fix help line breaks (contact@fabianofranz.com)
- Remove the usage from the list of available commands in help
  (contact@fabianofranz.com)
- modify .kubeconfig (deads@redhat.com)
- Basic structure for osc login (contact@fabianofranz.com)
- fix scripts http url to https (bparees@redhat.com)
- Start node with --kubeconfig should use master host from config file
  (jforrest@redhat.com)
- Bug 1189390 - fix project selector so it gets re-rendered after project list
  changes (jforrest@redhat.com)
- Switch to localStorage (jliggitt@redhat.com)
- Fix image change trigger imageRepo matching (ironcladlou@gmail.com)
- Show latest deployment in deploy config describe (ironcladlou@gmail.com)
- Update documentation to use 'osc create' consistently (mfojtik@redhat.com)
- Tighten header styles inside tiles (jliggitt@redhat.com)
- Only warn when chcon fails (ccoleman@redhat.com)
- Restore logic to disregard resources in pod diff (ironcladlou@gmail.com)
- UPSTREAM: Register nodes that already exist statically (ccoleman@redhat.com)
- Only allow session auth to be used for a single auth flow
  (jliggitt@redhat.com)
- Remove aliases and options command from cli template
  (contact@fabianofranz.com)
- make ovs-simple from openshift-sdn the default networking solution for
  vagrant (rchopra@redhat.com)
- Use certs in vagrant mutli node environment. (mrunalp@gmail.com)
- Nuke the default usage section from client templates
  (contact@fabianofranz.com)
- Introduces "osc options" to list global options (contact@fabianofranz.com)
- Custom template for cli and osc, hide global options
  (contact@fabianofranz.com)
- fix service select for frontend (bparees@redhat.com)
- Ignore .pyc files (sdodson@redhat.com)
- OpenShift should set a client UserAgent on all calls (ccoleman@redhat.com)
- Add OAuth login to console (jliggitt@redhat.com)
- Set a default user agent on all client.Client calls (ccoleman@redhat.com)
- remove use of osc namespace command (bparees@redhat.com)
- create template file for image repos (bparees@redhat.com)
- add skip build flag support for test target (pweil@redhat.com)
- Remove references to openshift/kubernetes (dmcphers@redhat.com)
- use Status.DockerImageRepository instead of DockerImageRepository
  (bparees@redhat.com)
- Reorganize command line code and move app-gen under experimental
  (cewong@redhat.com)
- Slightly increase the wait for hack/test-cmd.sh (ccoleman@redhat.com)
- WIP - osc new-app with argument inference (ccoleman@redhat.com)
- [WIP] Simple generation flow for an application based on source
  (cewong@redhat.com)
- Simple source->build->deploy generation (ccoleman@redhat.com)
- remove guestbook link (bparees@redhat.com)
- Add missing step when testing k8s rebase (jhonce@redhat.com)
- Bug 1188933 - Missing es5-dom-shim causes CustomEvent polyfill to fail in IE
  (jforrest@redhat.com)
- Resource round tripping has been fixed and new fields added to pod
  (ccoleman@redhat.com)
- Master takes IP instead of string (ccoleman@redhat.com)
- Use RESTMapper scopes for registering resources (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: Disable auto-pull when tag is "latest" (ccoleman@redhat.com)
- UPSTREAM: spf13/cobra help display separate groups of flags
  (contact@fabianofranz.com)
- UPSTREAM: Add 'release' field to raven-go (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):72ad4f12bd7408a6f75e6a0bf37b3
  440e165bdf4 (ccoleman@redhat.com)
- hack/end-to-end should terminate jobs (ccoleman@redhat.com)
- Set volume dir SELinux context if possible (agoldste@redhat.com)
- Typo on master.go around pullIfNotPresent (ccoleman@redhat.com)
- Update HACKING.md with the release push instructions (ccoleman@redhat.com)
- Bash is the worst programming language ever invented (ccoleman@redhat.com)
- Restore CORS outside of go-restful (ccoleman@redhat.com)
- use start-build instead of curl (bparees@redhat.com)
- Add CONTEXT_DIR support for sti-image-builder image (mfojtik@redhat.com)
- Generate openshift service on provision (dmcphers@redhat.com)
- Expose two new flags on master --images and --latest-images
  (ccoleman@redhat.com)
- Create an openshift/origin-pod image (ccoleman@redhat.com)
- check for error on missing docker file (bparees@redhat.com)
- remove guestbook example (bparees@redhat.com)
- Refactor css, variablize more values and restructure label filter markup
  (sgoodwin@redhat.com)
- Adding tests for help consistency to test-cmd.sh (contact@fabianofranz.com)
- UPSTREAM: special command "help" must be aware of context
  (contact@fabianofranz.com)
- better description of output to field (bparees@redhat.com)
- experimental policy cli (deads@redhat.com)
- UPSTREAM: need to make sure --help flags is registered before calling pflag
  (contact@fabianofranz.com)
- move kubernetes capabilities to server start (patrick.hemmer@gmail.com)
- Add --check option to run golint and gofmt in ./hack/build-in-docker.sh
  (mfojtik@redhat.com)
- Add retry logic to recreate deployment strategy (ironcladlou@gmail.com)
- Very simple authorizing proxy for Kubernetes (ccoleman@redhat.com)
- Unify authorization logic into a more structured form (ccoleman@redhat.com)
- User registry should transform server errors (ccoleman@redhat.com)
- UPSTREAM: Handle case insensitive node names and squash logging
  (ccoleman@redhat.com)
- UPSTREAM: Use new resource builder in kubectl update #3805
  (nagy.martin@gmail.com)
- remove unnecessary rest methods (deads@redhat.com)
- UPSTREAM: add flag to manage $KUBECONFIG files: #4053, bugzilla 1188208
  (deads@redhat.com)
- Add ./hack/build-in-docker.sh script (mfojtik@redhat.com)
- Fix Go version checking in verify-gofmt (mfojtik@redhat.com)
- Use $http (jliggitt@redhat.com)
- sample-app docs: update for TLS, namespace, context (lmeyer@redhat.com)
- Removed "Additional Help Topics" section from help template
  (contact@fabianofranz.com)
- Use our own templates to cli help and usage (contact@fabianofranz.com)
- UPSTREAM: spf13/cobra help display separate groups of flags
  (contact@fabianofranz.com)
- add missing reencrypt validations (pweil@redhat.com)
- Label filtering widget in the web console, styles by @sg00dwin
  (jforrest@redhat.com)
- remove unnecessary labels from sample imagerepos (bparees@redhat.com)
- Add shortcuts for build configs and deployment configs (ccoleman@redhat.com)
- Remove kubecfg, expose kubectl in its place (ccoleman@redhat.com)
- bump(github.com/docker/docker):211513156dc1ace48e630b4bf4ea0fcfdc8d9abf
  (cewong@redhat.com)
- Update project display name for sample app (decarr@redhat.com)
- UPSTREAM: typos (contact@fabianofranz.com)
- ignore local .kubeconfig (deads@redhat.com)
- Improve /oauth/token/request page (jliggitt@redhat.com)
- Compile haproxy with generic CPU instructions (sdodson@redhat.com)
- Fix multi minion setup (dmcphers@redhat.com)
- policy authorizer (deads@redhat.com)
- policy client (deads@redhat.com)
- policy storage (deads@redhat.com)
- policy types (deads@redhat.com)
- Fix the Vagrant network setup (lhuard@amadeus.com)
- Remove empty log files and use a slightly different process kill method
  (ccoleman@redhat.com)
- Refactor to match upstream master changes (ccoleman@redhat.com)
- Better debug output in deployment_config_controller (ccoleman@redhat.com)
- Adapt to upstream changes for cache.Store (ccoleman@redhat.com)
- UPSTREAM: Relax validation around annotations (ccoleman@redhat.com)
- UPSTREAM: Support GetByKey so EventStore can de-dup (ccoleman@redhat.com)
- UPSTREAM: Add 'release' field to raven-go (ccoleman@redhat.com)
- UPSTREAM: Allow namespace short to be set (ccoleman@redhat.com)
- UPSTREAM: api registration right on mux makes it invisible to container
  (contact@fabianofranz.com)
- UPSTREAM: Disable auto-pull when tag is "latest" (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):e335e2d3e26a9a58d3b189ccf41ce
  b3770d1bfa9 (ccoleman@redhat.com)
- Escape helper echo in rebase-kube (ccoleman@redhat.com)
- only kill and remove k8s managed containers (bparees@redhat.com)
- Gofmt whitespace flaw (ccoleman@redhat.com)
- Helper function for rebase output (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- UPSTREAM: Disable auto-pull when tag is "latest" (ccoleman@redhat.com)
- Godeps: update tags to be accurate (ccoleman@redhat.com)
- Properly version Kubernetes and OpenShift binaries (ccoleman@redhat.com)
- Connect the node to the master via and a built in client
  (ccoleman@redhat.com)
- Rebase fixes (ccoleman@redhat.com)
- Fix flaky travis by limiting parallel builds (ccoleman@redhat.com)
- UPSTREAM: api registration right on mux makes it invisible to container
  (contact@fabianofranz.com)
- UPSTREAM: Allow namespace short to be set (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):e0acd75629ec29bde764bcde29367
  146ae8b389b (jhonce@redhat.com)
- pkill on test-end-to-end.sh must be sudo (ccoleman@redhat.com)
- Set user UID in session (jliggitt@redhat.com)
- Implement deployment rollback CLI support (ironcladlou@gmail.com)
- Make file references relative in generated .kubeconfig files
  (jliggitt@redhat.com)
- Add ability to retrieve userIdentityMapping (jliggitt@redhat.com)
- Add "Oauth" prefix to oauth types (jliggitt@redhat.com)
- Register internal OAuth API objects correctly (jliggitt@redhat.com)
- Allow bower to run as root (dmcphers@redhat.com)
- Vagrantfile: improve providers and usability/readability (lmeyer@redhat.com)
- UPSTREAM: resolve relative paths in .kubeconfig (deads@redhat.com)
- Pin haproxy to 1.5.10 (sdodson@redhat.com)
- 'osc' should be symlinked in the openshift/origin Docker image
  (ccoleman@redhat.com)
- Split master and node packaging (sdodson@redhat.com)
- create test project for e2e (deads@redhat.com)
- Fix the Vagrant network setup (lhuard@amadeus.com)
- stop "OpenShift will terminate as soon as a panic occurs" from spamming
  during e2e (deads@redhat.com)
- Add asset server hostname to cert, generate cert without ports
  (jliggitt@redhat.com)
- Integration tests should let master load its own API (ccoleman@redhat.com)
- Build openshift-web-console oauth client (jliggitt@redhat.com)
- Externalize and doc auth config (jliggitt@redhat.com)
- Auto grant, make oauth sessions short, handle session decode failures
  (jliggitt@redhat.com)
- Prettify token display page (jliggitt@redhat.com)
- Add login template (jliggitt@redhat.com)
- Rename fedora image (dmcphers@redhat.com)
- refactor build interfaces (bparees@redhat.com)
- Allow to customize env variables for STI Build strategy (mfojtik@redhat.com)
- Don't cache the generated config.js or it won't pick up changes in startup
  options (jforrest@redhat.com)
- Makes 'config' set of commands experimental (contact@fabianofranz.com)
- Fix guestbook example to not collide with 'frontend' service
  (mfojtik@redhat.com)
- Convert Config to kapi.List{} and fix Template to use runtime.Object{}
  (mfojtik@redhat.com)
- UPSTREAM(ae3f10): Ensure the ptr is pointing to reflect.Slice in ExtractList
  (mfojtik@redhat.com)
- UPSTREAM(e7df8a): Fix ExtractList to support extraction from generic
  api.List{} (mfojtik@redhat.com)
- osc binary not present for Mac or Windows, windows needs .exe
  (ccoleman@redhat.com)
- Exposes 'osc config' to manage .kubeconfig files (contact@fabianofranz.com)
- Skip client cert gen if it exists (jliggitt@redhat.com)
- Skip server cert gen if exists and is valid (jliggitt@redhat.com)
- Copy openshift binary in the tar (ccoleman@redhat.com)
- Switch default instance size (dmcphers@redhat.com)
- Set public kubernetes master when starting kube (jliggitt@redhat.com)
- Allow images to be tagged in hack/push-release.sh (ccoleman@redhat.com)
- add server arg to osc command to support remote masters (pweil@redhat.com)
- Add option to unionauth to fail on error, fail on invalid or expired bearer
  tokens (jliggitt@redhat.com)
- Update bindata.go (decarr@redhat.com)
- Update ui code to not use project.metadata.namespace (decarr@redhat.com)
- Align project with upstream resources that exist outside of namespace
  (decarr@redhat.com)
- fix public-ip for node-sdn (rchopra@redhat.com)
- Fix bindata.go for the less partials split (jforrest@redhat.com)
- Change box url and name back (dmcphers@redhat.com)
- router TLS (pweil@redhat.com)
- Make insert key configurable (dmcphers@redhat.com)
- Make the provider configs optional (dmcphers@redhat.com)
- Splitting .less into partials and refactor of code. Including openshift-icon
  font set for now. (sgoodwin@redhat.com)
- bump(github.com/smarterclayton/go-
  dockerregistryclient):3b6185cb3ac3811057e317dcff91f36eef17b8b0
  (ccoleman@redhat.com)
- kill openshift process during e2e (deads@redhat.com)
- resolve osapi endpoint to be configured as upstream to resolve 406
  (jcantril@redhat.com)
- Config Generator should not return raw errors via the REST API
  (ccoleman@redhat.com)
- Fix vagrant single vm environment (pmorie@gmail.com)
- Enable authentication, add x509 cert auth, anonymous auth
  (jliggitt@redhat.com)
- Separate OAuth and API muxes, pass authenticator into master
  (jliggitt@redhat.com)
- Add x509 authenticator (jliggitt@redhat.com)
- Add groups to userinfo (jliggitt@redhat.com)
- Allow panics to be reported to Sentry (ccoleman@redhat.com)
- UPSTREAM: Allow panics and unhandled errors to be reported to external
  targets (ccoleman@redhat.com)
- UPSTREAM: Add 'release' field to raven-go (ccoleman@redhat.com)
- bump(github.com/getsentry/raven-go):3fd636ed242c26c0f55bc9ee1fe47e1d6d2d77f7
  (ccoleman@redhat.com)
- Add missing error assignments (michaliskargakis@gmail.com)
- Add profiling tools to the OpenShift binary (ccoleman@redhat.com)
- Add instructions to ignore vboxnet interfaces on the host.
  (mrunalp@gmail.com)
- Move registry install function to a reusable spot (ccoleman@redhat.com)
- Remove unused api target from Makefile comments (vvitek@redhat.com)
- add dns recommendations (bparees@redhat.com)
- Fix bug #686 (pmorie@gmail.com)
- Lock webcomponents version (jliggitt@redhat.com)
- bump(github.com/pkg/profile):c795610ec6e479e5795f7852db65ea15073674a6
  (ccoleman@redhat.com)
- Use correct client config to run token cmd (jliggitt@redhat.com)
- Update routing readme and script to set up TLS (jliggitt@redhat.com)
- Separate asset bind and asset public addr (jliggitt@redhat.com)
- provide an environment switch to choose ovs-simple as the overlay network for
  the cluster (rchopra@redhat.com)
- start: provide + use flags for public API addresses (lmeyer@redhat.com)
- No need to redoc k8s in origin (dmcphers@redhat.com)
- Review comments 2 - Pass Codec through and return error on setBuildEnv
  (ccoleman@redhat.com)
- Disable race detection on test-integration because of #731
  (ccoleman@redhat.com)
- Crash on Panic when ENV var set (ccoleman@redhat.com)
- asset server: change bind addr (lmeyer@redhat.com)
- delete large log files before archiving to jenkins (bparees@redhat.com)
- Bug: Build logs could be accessed only when the pod phase was running
  (j.hadvig@gmail.com)
- packaging: put runtime data to /var/lib/origin (ttomecek@redhat.com)
- packaging: remove invalid options in /etc/sysconf/os (ttomecek@redhat.com)
- WIP - Template updates (ccoleman@redhat.com)
- More flexibility to test-cmd and test-end-to-end (ccoleman@redhat.com)
- Remove the need to load deployments from config_generator
  (ccoleman@redhat.com)
- Allow more goroutines to exit during test cases with RunUntil
  (ccoleman@redhat.com)
- Return the most recently updated deployment config after PUT
  (ccoleman@redhat.com)
- Cleanup integration tests (ccoleman@redhat.com)
- Add "from" object reference to both ImageChangeTriggers (ccoleman@redhat.com)
- Support service variable substitution in docker registry variable
  (ccoleman@redhat.com)
- Use Status.DockerImageRepository from CLI (ccoleman@redhat.com)
- Check for an ImageRepositoryMapping with metadata/name before DIR
  (ccoleman@redhat.com)
- Review comments (ccoleman@redhat.com)
- When creating build, lookup "to" field if specified (ccoleman@redhat.com)
- Define "to" and "dockerImageReference" as new fields on BuildOutput
  (ccoleman@redhat.com)
- UPSTREAM: Add RunUntil(stopCh) to reflector and poller to allow termination
  (ccoleman@redhat.com)
- UPSTREAM: Expose validation.ValidateLabels for reuse (ccoleman@redhat.com)
- Disable other e2e tests (ccoleman@redhat.com)
- UPSTREAM: Use ExtractObj instead of ExtractList in Kubelet
  (ccoleman@redhat.com)
- Introduce deployment rollback API (ironcladlou@gmail.com)
- design policy (deads@redhat.com)
- Enable privileged capabilities in apiserver (ironcladlou@gmail.com)
- Wireframes of label filter interface states event-based user actions
  (sgoodwin@redhat.com)
- run custom, docker builds in e2e (bparees@redhat.com)
- Updating HACKING doc with more detailed information about Kubernetes rebases
  (contact@fabianofranz.com)
- Remove hard-coded resourceVersion values from build watches
  (maszulik@redhat.com)
- Make vagrant run in http for now (jliggitt@redhat.com)
- Default --master scheme to match --listen (jliggitt@redhat.com)
- Rebuild to pick up new webcomponents (jliggitt@redhat.com)
- Fix internal token request with TLS (jliggitt@redhat.com)
- Remove flag hard-coding (pmorie@gmail.com)
- Send events from the master (ccoleman@redhat.com)
- Don't hard-code resourceVersion in watches (ironcladlou@gmail.com)
- Enable TLS (jliggitt@redhat.com)
- UPSTREAM: Allow changing global default server hostname (jliggitt@redhat.com)
- Exclude .git and node_modules from test search (ironcladlou@gmail.com)
- UPSTREAM: Use CAFile even when cert/key is not specified, allow client config
  to take cert data directly (jliggitt@redhat.com)
- Typo in deployment controller factory (pmorie@gmail.com)
- Remove yaml from all object types (mfojtik@redhat.com)
- Router doc json cleanup (pmorie@gmail.com)
- Make OSC use non-interactive auth loading, fix flag binding
  (jliggitt@redhat.com)
- UPSTREAM: make kubectl factory flag binding optional (jliggitt@redhat.com)
- Fix docker build with context directory (cewong@redhat.com)
- docs: Filling in some initial model descriptions (lmeyer@redhat.com)
- docs: *_model.adoc => .md (lmeyer@redhat.com)
- Make hack/build-go.sh create symlinks for openshift (pmorie@gmail.com)
- UPSTREAM: bump(github.com/jteeuwen/go-bindata):
  f94581bd91620d0ccd9c22bb1d2de13f6a605857 (jliggitt@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- Refactor to match changes upstream (mfojtik@redhat.com)
- Refactor to match changes upstream (contact@fabianofranz.com)
- UPSTREAM: api registration right on mux makes it invisible to container
  (contact@fabianofranz.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):21b661ecf3038dc50f75d345276c9
  cf460af9df2 (contact@fabianofranz.com)
- In case of failure, wait and restart the openshift-node service
  (marek.goldmann@gmail.com)
- Pull in hawtio-core-navigation and build console nav around it. Styles and
  theming by @sg00dwin (jforrest@redhat.com)
- fix namespacing so sample works again (bparees@redhat.com)
- Fix gofmt detection (jliggitt@redhat.com)
- add missing quotes to privileged (bparees@redhat.com)
- Require docker-io 1.3.2 or later. Remove -devel FIXME (sdodson@redhat.com)
- Support `GET /imageRepositoryTags/<name>:<tag>` (ccoleman@redhat.com)
- Properly version Docker image metadata sent to the API (ccoleman@redhat.com)
- UPSTREAM: Expose TypeAccessor for objects without metadata
  (ccoleman@redhat.com)
- Update end-to-end to use new registry pattern (ccoleman@redhat.com)
- Depend on docker-io (sdodson@redhat.com)
- Tolerate missing build logs in cancel-build (jliggitt@redhat.com)
- Constants are mismatched on BuildTriggerType (ccoleman@redhat.com)
- Move systemd unit and sysconfig files to rel-eng (sdodson@redhat.com)
- ImageRepository lookup should check the OpenShift for <namespace>/<name>
  (ccoleman@redhat.com)
- UPSTREAM: Disable auto-pull when tag is "latest" (ccoleman@redhat.com)
- Initial pass at getting tito set up for release engineering purposes
  (sdodson@redhat.com)
- Update sample app README now that cors-allowed-origins option isn't required
  for embedded web console (jforrest@redhat.com)
- Move specification for api version for web console into console code.  Add
  127.0.0.1 to default cors list. (jforrest@redhat.com)
- Web console talks to master over configured master host/port and embedded web
  console allowed by default in CORS list (jforrest@redhat.com)
- Bug 1176815 - Improve error reporting for build-log (mfojtik@redhat.com)
- Update README with simpler commands (ccoleman@redhat.com)
- Minor whitespace cleanup (ccoleman@redhat.com)
- Ensure tests shut themselves down, and fix race in imagechange test
  (ccoleman@redhat.com)
- Add Delete methods to various Image objects (ccoleman@redhat.com)
- Update the Makefile to run all tests (ccoleman@redhat.com)
- One last path fix (matthicksj@gmail.com)
- Fixing openshift path (matthicksj@gmail.com)
- Updating to use Makefile and updating path (matthicksj@gmail.com)
- use privileged containers for builds and docker registry (bparees@redhat.com)
- docs: place for k8s/os model descriptions (lmeyer@redhat.com)
- deep copy when creating build from buildconfig (bparees@redhat.com)
- Push the new STI images into configured output imageRepository
  (mfojtik@redhat.com)
- Add the hawtio-extension-service as a dependency (jforrest@redhat.com)
- Fixed bug: the master was advertising its internal IP when running the dev
  cluster through Vagrant (marko.luksa@gmail.com)
- ignore tag duplicaiton with multiple runs of e2e tests (akostadi@redhat.com)
- make sure errors don't abort tear down (akostadi@redhat.com)
- add image change trigger example to json (bparees@redhat.com)
- correct end-to-end test executable name in HACKING doc (akostadi@redhat.com)
- Fixed SELinux and firewalld commands for temporary disabling.
  (hripps@redhat.com)
- Modified with changes from review 1 (hripps@redhat.com)
- Delete built images after pushing them to registry (cewong@redhat.com)
- Added info about necessary SELinux & firewalld setup (hripps@redhat.com)
- git is also required, otherwise `go get` does not work (akostadi@redhat.com)
- Do not tag with GIT ref when the SOURCE_REF is not set (sti-image-builder)
  (mfojtik@redhat.com)
- Fixed unpacking of sti in sti-image-builder (mfojtik@redhat.com)
- introduce image change build trigger logic (bparees@redhat.com)
- force the docker registry ip to be constant (bparees@redhat.com)
- Refactor data service to better handle resourceVersion, unsubscribe, context
  specific callback lists, etc... (jforrest@redhat.com)
- Added STI image builder image (mfojtik@redhat.com)
- Rewrite and re-scope deployment documentation (ironcladlou@gmail.com)
- update readme to work with web console (bparees@redhat.com)
- Double error print in the OpenShift command (ccoleman@redhat.com)
- Implement deployments without Deployment (ironcladlou@gmail.com)
- Add generic webhook payload to versioned types (cewong@redhat.com)
- Updated STI builder according to latest STI version (maszulik@redhat.com)
- bump(github.com/openshift/source-to-
  image/pkg/sti):5813879841b75b7eb88169d3265a0560fdf50b12 (maszulik@redhat.com)
- correct awk command to get correct endpoint (jialiu@redhat.com)
- correct awk command to get correct endpoint (jialiu@redhat.com)
- Fixing sti url (dmcphers@redhat.com)
- Fixing typos (dmcphers@redhat.com)
- added setup documentation when using the docker container and the sample app
  (erikmjacobs@gmail.com)
- tweaked getting started readme (erikmjacobs@gmail.com)
- Pull in the hawtio-core framework into the console (jforrest@redhat.com)
- Updated STI builder according to latest STI version (maszulik@redhat.com)
- bump(github.com/openshift/source-to-
  image/pkg/sti):48cf2e985b571ddc67cfb84a59a339be38b98a81 (maszulik@redhat.com)
- Make grunt hostname/port configurable (ironcladlou@gmail.com)
- Vagrantfile: accommodate empty lines in ~/.awscred (jolamb@redhat.com)
- ssl_fc_has_sni is meant to work post ssl termination, use req_ssl_sni to
  directly lookup the extacted sni from the map. (rchopra@redhat.com)
- Added --parameters and --value options for kubectl#process command
  (mfojtik@redhat.com)
- OPENSHIFT_NUM_MINIONS env var was not honored (marko.luksa@gmail.com)
- add instructions for insecure registry config (bparees@redhat.com)
- Update README.md (scitronpousty@gmail.com)
- Specifically add github.com/docker/docker/pkg/units (ccoleman@redhat.com)
- Refactor to match upstream (ccoleman@redhat.com)
- UPSTREAM: Disable UIs for Kubernetes and etcd (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):6624b64f440a0f10a8d9ca401c3b1
  40f1bf2f945 (ccoleman@redhat.com)
- Cache control assets with ETag based on commit (jforrest@redhat.com)
- Kube make clean doesn't work without Docker (ccoleman@redhat.com)
- Update cli.md (jasonkuhrt@me.com)
- Issue 253 - Added STI scripts location as part of the STI strategy
  (maszulik@redhat.com)
- fix template test fixture (rajatchopra@gmail.com)
- fix template : redis-master label missing. issue#573 (rajatchopra@gmail.com)
- Enable html5 mode in the console (jforrest@redhat.com)
- Improve example validation and add template fixtures for example data
  (ccoleman@redhat.com)
- Allow resources posted to /templateConfigs to omit name (ccoleman@redhat.com)
- Template parameter processing shouldn't return errors for unrecognized types
  (ccoleman@redhat.com)
- Fix errors in guestbook template.json (ccoleman@redhat.com)
- Return typed errors from template config processing (ccoleman@redhat.com)
- Set uid, creation timestamp using standard utility from kube
  (decarr@redhat.com)
- Remove debug statement from master.go (ccoleman@redhat.com)
- Templates don't round trip (ccoleman@redhat.com)
- fix interface typo (bparees@redhat.com)
- Ensure namespace will be serialized in proper location when moving to path
  param (decarr@redhat.com)
- Update bindata to match upstream dependencies (jforrest@redhat.com)
- bump(github.com/spf13/cobra):e1e66f7b4e667751cf530ddb6e72b79d6eeb0235
  (maszulik@redhat.com)
- UPSTREAM: kubectl delete command: adding labelSelector (vvitek@redhat.com)
- Proposal for capabilities (jforrest@redhat.com)
- Update nav with labels (sgoodwin@redhat.com)
- Incorrect path argument for Golint (j.hadvig@gmail.com)
- Update bindata to match an updated dependency (jforrest@redhat.com)
- Reintroduced Vagrant version sensitivity (hripps@redhat.com)
- Updated Vagrantfile to reflect config processing changes as of Vagrant 1.7.1
  (hripps@redhat.com)
- Clean up (j.hadvig@gmail.com)
- V3 console navigation structure and interaction (sgoodwin@redhat.com)
- Remove API docs and replace with link to Swagger UI (ccoleman@redhat.com)
- Support the swagger API from OpenShift master (ccoleman@redhat.com)
- UPSTREAM: Take HandlerContainer as input to master to allow extension
  (ccoleman@redhat.com)
- Fix 'openshift cli' longDesc string arg reference (vvitek@redhat.com)
- Router refactor (pmorie@gmail.com)
- fix #551, make the service ip range private (deads@redhat.com)
- Cancel new builds. Update client logic. (maria.nita.dn@gmail.com)
- Cleanup OpenShift CLI (ccoleman@redhat.com)
- test-cmd should use raw 'osc' calls (ccoleman@redhat.com)
- Make test-end-to-end more readable (ccoleman@redhat.com)
- Golint is broken on Mac (ccoleman@redhat.com)
- tweaks to handle new kubernetes, kick travis again (deads@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):3910b2d6e18759b3a9a6920c7f3d0
  ccd122df7f9 (deads@redhat.com)
- Move from go 1.4rc2 to 1.4 release (jordan@liggitt.net)
- helper script to fix registry ip (bparees@redhat.com)
- Rename STIBuildStrategy.BuildImage to Image (mfojtik@redhat.com)
- Refactoring router.go to handle errors. Improving code coverage - Add port
  forwarding from 8080 to localhost:8080 on VirtualBox - Refactoring router.go
  to handle errors. Improving code coverage. - Adding port forwarding from 80
  to localhost:1080 on VirtualBox, and comments on how to test locally -
  Applying refactor change to controller/test/test_router.go - Fixing
  identation - Fixing unit tests - Organizing imports - Merge (akram@free.fr)
- Fix project description in example and console to work as an annotation
  (jforrest@redhat.com)
- fix auth packages, kick travis yet again (deads@redhat.com)
- add cli challenge interaction, kick travis again (deads@redhat.com)
- Added documentation for custom build (mfojtik@redhat.com)
- cancel-build fails if no pod was assigned (deads@redhat.com)
- Initial addition of CustomBuild type (mfojtik@redhat.com)
- Improve error reporting (vvitek@redhat.com)
- add instructions to edit registry service ip (bparees@redhat.com)
- Add go1.4 to travis (jliggitt@redhat.com)
- EventQueue should provide events for replaced state (pmorie@gmail.com)
- Exit install-assets.sh when the command fails (mfojtik@redhat.com)
- make openshift run on new kubernetes (deads@redhat.com)
- UPSTREAM: go-restful, fix race conditions https://github.com/emicklei/go-
  restful/pull/168 (deads@redhat.com)
- UPSTREAM: Add util.Until (ccoleman@redhat.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):b614f22935df36f8c1d6bd3c5c9fe
  850e79fd729 (deads@redhat.com)
- Add a Status field on ImageRepository (ccoleman@redhat.com)
- Various Go style fixes (mfojtik@redhat.com)
- increase retries to account for slow systems (bparees@redhat.com)
- Add command to cancel build     - Add flag to print build logs  - Add flag to
  restart build     - Test command (maria.nita.dn@gmail.com)
- Add PodManager to build resource, to handle pod delete and create
  (maria.nita.dn@gmail.com)
- Add resource flag and status for cancelling build (maria.nita.dn@gmail.com)
- always dump build log to build.log (bparees@redhat.com)
- Router sharding proposal 2/2 (pmorie@gmail.com)
- Router sharding proposal 1/2 (pweil@redhat.com)
- Simplify webhook URL display (cewong@redhat.com)
- Add strategy and revision output to Build describer (cewong@redhat.com)
- Marks 'openshift kube' as deprecated (contact@fabianofranz.com)
- Removes 'openshift kubectl' in favor of 'openshift cli', 'kubectl' set as an
  alias (contact@fabianofranz.com)
- Exposes 'openshift cli', removing the osc binary for now
  (contact@fabianofranz.com)
- Basic structure for the end-user client command (osc)
  (contact@fabianofranz.com)
- Install assets more quietly (mfojtik@redhat.com)
- Add '-m' option to verify-golint to check just modified files
  (mfojtik@redhat.com)
- Bug 1170545 - Error about deployment not found (j.hadvig@gmail.com)
- ALL_CAPS to CamelCase (j.hadvig@gmail.com)
- Array declaration change (j.hadvig@gmail.com)
- receiver name should not be an underscore (j.hadvig@gmail.com)
- Reciever name consistency (j.hadvig@gmail.com)
- Removing underscore from method name (j.hadvig@gmail.com)
- Use DeploymentStrategy instead of recreate.DeploymentStrategy
  (j.hadvig@gmail.com)
- replacing 'var += 1' with 'var++' (j.hadvig@gmail.com)
- error strings should not end with punctuation (j.hadvig@gmail.com)
- Fix variable names (j.hadvig@gmail.com)
- Fix panic in webhook printing (mfojtik@redhat.com)
- Refactor printing of values in kubectl describe (mfojtik@redhat.com)
- Add missing Update, Create and Delete methods to Project client
  (mfojtik@redhat.com)
- Remove namespace from Project client and Describer (mfojtik@redhat.com)
- fix service spec camel case (pweil@redhat.com)
- Fix #286: Fix Config with nil Labels (vvitek@redhat.com)
- bump(github.com/openshift/source-to-image):
  1075509c5833e58fda33f03ce07307d7193d74f4 (maszulik@redhat.com)
- Simplify code to get rid variable shadowing (maszulik@redhat.com)
- replace build trigger with build command (bparees@redhat.com)
- Fix failed tests (mfojtik@redhat.com)
- getUrl -> getURL (mfojtik@redhat.com)
- Rename grant.GrantFormRenderer to grant.FormRenderer (mfojtik@redhat.com)
- Fix variable names (Url -> URL, client_id -> clientID, etc...)
  (mfojtik@redhat.com)
- Replace ALL_CAPS in basicauth_test with camel case (mfojtik@redhat.com)
- Use 'template.Processor' instead of 'template.TemplateProcessor'
  (mfojtik@redhat.com)
- Replace errors.New(fmt.Sprintf(...)) with fmt.Errorf(...)
  (mfojtik@redhat.com)
- Get rid of else from an if block when it contains return (mfojtik@redhat.com)
- Ascii should be ASCII (mfojtik@redhat.com)
- webhookUrl should be webhookURL (mfojtik@redhat.com)
- NoDefaultIP should be ErrNoDefaultIP (mfojtik@redhat.com)
- Fixed godoc in server/start (mfojtik@redhat.com)
- Remove else from env() func (mfojtik@redhat.com)
- Fixed godoc for origin/auth package (mfojtik@redhat.com)
- Fixed missing godoc in cmd/infra package (mfojtik@redhat.com)
- Added missing godoc and obsolete notice (mfojtik@redhat.com)
- Added missing godoc (mfojtik@redhat.com)
- Fixed if block that ends with a return in serialization test
  (mfojtik@redhat.com)
- Added godoc for multimapper constant (mfojtik@redhat.com)
- Rename haproxy.HaproxyRouter to haproxy.Router (mfojtik@redhat.com)
- Added Project describer (mfojtik@redhat.com)
- Added client for Project (mfojtik@redhat.com)
- Replace Description with Annotations in Project (mfojtik@redhat.com)
- Fixed wrong User() and UserIdentityMappings in Fake client
  (mfojtik@redhat.com)
- Added kubectl Describer for Origin objects (mfojtik@redhat.com)
- Rename config.mergeMaps() as util.MergeInto() (vvitek@redhat.com)
- UPSTREAM: Add Labels and Annotations to MetadataAccessor (vvitek@redhat.com)
- UPSTREAM: meta_test should not depend on runtime.TypeMeta (vvitek@redhat.com)
- update to use new openshift jenkins image tag (bparees@redhat.com)
- allow unbound skip_image_cleanup variable (bparees@redhat.com)
- Porting manual build-trigger to kubectl (j.hadvig@gmail.com)
- Gzip assets (jliggitt@redhat.com)
- Add dependency on github.com/daaku/go.httpgzip
  (3f59977b58c61991f5ed3670bbd141937d808b06) (jliggitt@redhat.com)
- Simplify asset test, keep line breaks in css and js (jliggitt@redhat.com)
- Change AddRoute signature to use ep structs, factor out functions for
  testability, add unit tests for said functions (pweil@redhat.com)
- add jenkins sample (bparees@redhat.com)
- Fixup the gofmt'ed bindata.go file (jforrest@redhat.com)
- UPSTREAM: Fixes #458 - retrieval of Docker container stats from cadvisor
  (jimmidyson@gmail.com)
- bump(github.com/google/cadvisor): 89088df70eca64cf9d6b9a23a3d2bc21a30916d6
  (jimmidyson@gmail.com)
- Stop deployment controllers during integration tests (ccoleman@redhat.com)
- UPSTREAM: Add util.Until (ccoleman@redhat.com)
- Prepare for nested commands (ccoleman@redhat.com)
- bump(github.com/spf13/cobra): b825817fc0fc59fc1657bc8202204a04ae3d679d
  (ccoleman@redhat.com)
- Added docs/cli.md describing the kubectl interface (mfojtik@redhat.com)
- Fixed typos, mixing comments and removed unused method (maszulik@redhat.com)
- Fix documentation to use kubectl instead of kubecfg (mfojtik@redhat.com)
- Replace kubecfg with kubectl in e2e test (mfojtik@redhat.com)
- Fix incorrect namespace for origin kubectl commands (mfojtik@redhat.com)
- Fixed typo in kubectl build-log (mfojtik@redhat.com)
- Cleanup godoc / tests for router, event queue (pmorie@gmail.com)
- Add SKIP_IMAGE_CLEANUP env variable for E2E test (mfojtik@redhat.com)
- Fixed test-service.json fixture to be v1beta2 (mfojtik@redhat.com)
- Switch test-cmd.sh to use kubectl instead of kubecfg (mfojtik@redhat.com)
- Use ResourceFromFile to get namespace and data (mfojtik@redhat.com)
- Refactor router controller unit tests (pmorie@gmail.com)
- link debugging guide from other docs (bparees@redhat.com)
- Correct urlVars field name (j.hadvig@gmail.com)
- UPSTREAM: Fix pluralization in RESTMapper when kind ends with 'y' (#2569)
  (mfojtik@redhat.com)
- Define printer for Origin objects in kubectl (mfojtik@redhat.com)
- Added TODOs and NOTE into Config#Apply (mfojtik@redhat.com)
- Added 'openshift kubectl build-logs' command (mfojtik@redhat.com)
- Added 'openshift kubectl process' command (mfojtik@redhat.com)
- Added 'openshift kubectl apply' command (mfojtik@redhat.com)
- Initial import for pkg/cmd/kubectl into origin (mfojtik@redhat.com)
- Added MultiRESTMapper into pkg/api/meta (mfojtik@redhat.com)
- create a troubleshooting guide (bparees@redhat.com)
- print invalid responses (bparees@redhat.com)
- Added ./hack/verify-golint.sh command (mfojtik@redhat.com)
- Make install-assets.sh work outside TRAVIS (jliggitt@redhat.com)
- Initial implementation of a project's overview in the web console
  (jforrest@redhat.com)
- Add hack script for pythia tool (decarr@redhat.com)
- Add EventQueue and refactor LBManager to use client/cache (pmorie@gmail.com)
- bump(github.com/jteeuwen/go-bindata):f94581bd91620d0ccd9c22bb1d2de13f6a605857
  (jforrest@redhat.com)
- Include required fields on AccessToken type, always serialize Items fields
  (jliggitt@redhat.com)
- Manual build trigger (j.hadvig@gmail.com)
- Rework client.Interface to match upstream (maszulik@redhat.com)
- vagrant-libvirt support (inecas@redhat.com)
- Fix vagrant rsync (inecas@redhat.com)
- Remove omitempty annotation from Items property in list types
  (cewong@redhat.com)
- Add build namespace to built image environment (cewong@redhat.com)
- Use upstream ParseWatchResourceVersion (agoldste@redhat.com)
- ImageRepository fixes (agoldste@redhat.com)
- Add auth-proxy-test (deads@redhat.com)
- Manual build launch (cewong@redhat.com)
- Add watch method for build configs (cewong@redhat.com)
- Adding port forwarding from 80 to localhost:1080 on VirtualBox, fixing indent
  and comments on how to test locally (akram@free.fr)
- Ref mailing list (ccoleman@redhat.com)
- bump(github.com/openshift/source-to-image)
  81ea479a67c279351661653c2a40f9428d4e259b (bparees@redhat.com)
- update registery ip references to reflect new default services
  (bparees@redhat.com)
- Change Identity.Name to Identity.UserName (jliggitt@redhat.com)
- Correlate Pods to Deployments during Recreate (ironcladlou@gmail.com)
- add union auth request handler (deads@redhat.com)
- Go builds are under /local (decarr@redhat.com)
- Fix project example after rebase (decarr@redhat.com)
- update readme to use generic webhook (bparees@redhat.com)
- add endpoint for displaying token (deads@redhat.com)
- Fix error message in generic webhook (cewong@redhat.com)
- Make auth interfaces more flexible (jliggitt@redhat.com)
- update registry config to be more self-sufficient (bparees@redhat.com)
- Fix Build API JSON tags for BuildStrategy (cewong@redhat.com)
- Fix deployment image change trigger bug (ironcladlou@gmail.com)
- fix checking for nil body on generic webhook invocation (bparees@redhat.com)
- minor change to install script to allow passing id. Moved router readme to
  docs. Updated readme for HA setup and documented DNS RR. (pweil@redhat.com)
- Fix ID -> Name in printers (pmorie@gmail.com)
- Kube rebase (3/3) (soltysh@gmail.com)
- Kube rebase (2/3) (mfojtik@redhat.com)
- Kube rebase (1/3) (contact@fabianofranz.com)
- bump(github.com/GoogleCloudPlatform/kubernetes):
  97cb1fa2df8b57be5ceaae290e02872f291b7b7e (contact@fabianofranz.com)
- Update to use uncompressed bindata for easier diffs (jforrest@redhat.com)
- bump(github.com/jteeuwen/go-bindata):bbd0c6e271208dce66d8fda4bc536453cd27fc4a
  (jforrest@redhat.com)
- Fixing typos (dmcphers@redhat.com)
- Log streaming logic update (j.hadvig@gmail.com)
- Add --net=host option for simplicity in Docker steps. (ccoleman@redhat.com)
- Docker run command was wrong (ccoleman@redhat.com)
- Refactor build config to use triggers (cewong@redhat.com)
- Add NoCache flag to docker builds (cewong@redhat.com)
- bump(github.com/openshift/source-to-image)
  53a27ab4cc8c6abfe84904a6503490bbf0bf7abb (bparees@redhat.com)
- Fix API references (cewong@redhat.com)
- router e2e integration (pweil@redhat.com)
- Deployment proposal: add detail to image spec (pmorie@gmail.com)
- Strengthen deploy int test assertions (ironcladlou@gmail.com)
- [BZ1163618] Add missing user agent to error message (jcantril@redhat.com)
- Clean up and add tests to the Recreate strategy (ironcladlou@gmail.com)
- Better sudoer seding (dmcphers@redhat.com)
- Use constants for deployment annotations (ironcladlou@gmail.com)
- add user identity mapping provisioning (deads@redhat.com)
- Fix build watch resource kind (cewong@redhat.com)
- Update deployment API examples and docs (ironcladlou@gmail.com)
- Fix naming of openshift/origin-deployer image (ironcladlou@gmail.com)
- Implement deployments with pods (ironcladlou@gmail.com)
- comments round 1 (deads@redhat.com)
- gofmt (pweil@redhat.com)
- test case and remove newline from glog statements (pweil@redhat.com)
- Do not delete the entire structure when just an alias is removed. bz1157388
  (rchopra@redhat.com)
- Godoc fix (j.hadvig@gmail.com)
- typo fixed (deads@redhat.com)
- Remove obsolete API examples (maria.nita.dn@gmail.com)
- Add command to run gofmt for bad formatted Go files (maria.nita.dn@gmail.com)
- Check all expected files have an existent JSON file. Update list of expected
  files (maria.nita.dn@gmail.com)
- Generate API doc for new examples (maria.nita.dn@gmail.com)
- Validate API examples. Rename files (maria.nita.dn@gmail.com)
- Switch back to gp2 volumes (dmcphers@redhat.com)
- Fix typos (dmcphers@redhat.com)
- add token option to clientcmd (deads@redhat.com)
- Fix WORKDIR typo in Dockerfile (ironcladlou@gmail.com)
- Fix typo (dmcphers@redhat.com)
- use token from command line (deads@redhat.com)
- update openshift path (bparees@users.noreply.github.com)
- Remove extra binaries (ccoleman@redhat.com)
- Move standalone commands into the pkg/cmd pattern (ccoleman@redhat.com)
- Add utility functions for commands that connect to a master
  (ccoleman@redhat.com)
- Move start logic into its own method and return errors. (ccoleman@redhat.com)
- router readme and install script (pweil@redhat.com)
- Fixing typo in URL (abhgupta@redhat.com)
- Use a standard working dir for Docker images (ccoleman@redhat.com)
- OpenShift in a container README (ccoleman@redhat.com)
- Minor changes to test artifacts (pmorie@gmail.com)
- WIP: deployments proposal (pmorie@gmail.com)
- Enhance deployment list and watch APIs (ironcladlou@gmail.com)
- bump(github.com/openshift/source-to-image)
  add9ff4973d949b4c82fb6a217e6919bb6e6be23 (cewong@redhat.com)
- Add grant approval, scope.Add, tests (jliggitt@redhat.com)
- Add a flag to support clean STI builds to the STIBuildStrategy
  (cewong@redhat.com)
- Convert builder images to use go (cewong@redhat.com)
- Fix deployment pod template comparison (cewong@redhat.com)
- rework sample to use STI build type (bparees@redhat.com)
- [DEVEXP 391] Add generic webhook to trigger builds manually
  (jcantril@redhat.com)
- Document test-go.sh, add option to show coverage for all tests
  (jliggitt@redhat.com)
- Make deploymentConfigs with config change triggers deploy automatically when
  created (pmorie@gmail.com)
- Generate html coverage info (jliggitt@redhat.com)
- Mention commit message format for bumping Godeps (vvitek@redhat.com)
- make use of common mock objects (deads@redhat.com)
- Updated pre-pulled images (soltysh@gmail.com)
- Fixed buildLogs (soltysh@gmail.com)
- Reorganize the template pkg, make it match upstream patterns
  (vvitek@redhat.com)
- More flaky test fixes (agoldste@redhat.com)
- UPSTREAM: Support PUT returning 201 on Create, kick travis
  (ccoleman@redhat.com)
- kubernetes cherry-pick 2074 and 2140 (deads@redhat.com)
- gofmt etcd_test.go and fix broken route test after change to argument type
  (pweil@redhat.com)
- unit test for route watches (pweil@redhat.com)
- fix issues with route watches returning 404 and 500 errors (pweil@redhat.com)

* Mon Jan 26 2015 Scott Dodson <sdodson@redhat.com> 0.2-3
- Update to 21fb40637c4e3507cca1fcab6c4d56b06950a149
- Split packaging of openshift-master and openshift-node

* Mon Jan 19 2015 Scott Dodson <sdodson@redhat.com> 0.2-2
- new package built with tito

* Fri Jan 09 2015 Adam Miller <admiller@redhat.com> - 0.2-2
- Add symlink for osc command line tooling (merged in from jhonce@redhat.com)

* Wed Jan 07 2015 Adam Miller <admiller@redhat.com> - 0.2-1
- Update to latest upstream release
- Restructured some of the golang deps  build setup for restructuring done
  upstream

* Thu Oct 23 2014 Adam Miller <admiller@redhat.com> - 0-0.0.9.git562842e
- Add new patches from jhonce for systemd units

* Mon Oct 20 2014 Adam Miller <admiller@redhat.com> - 0-0.0.8.git562842e
- Update to latest master snapshot

* Wed Oct 15 2014 Adam Miller <admiller@redhat.com> - 0-0.0.7.git7872f0f
- Update to latest master snapshot

* Fri Oct 03 2014 Adam Miller <admiller@redhat.com> - 0-0.0.6.gite4d4ecf
- Update to latest Alpha nightly build tag 20141003

* Wed Oct 01 2014 Adam Miller <admiller@redhat.com> - 0-0.0.5.git6d9f1a9
- Switch to consistent naming, patch by jhonce

* Tue Sep 30 2014 Adam Miller <admiller@redhat.com> - 0-0.0.4.git6d9f1a9
- Add systemd and sysconfig entries from jhonce

* Tue Sep 23 2014 Adam Miller <admiller@redhat.com> - 0-0.0.3.git6d9f1a9
- Update to latest upstream.

* Mon Sep 15 2014 Adam Miller <admiller@redhat.com> - 0-0.0.2.git2647df5
- Update to latest upstream.

* Thu Aug 14 2014 Adam Miller <admiller@redhat.com> - 0-0.0.1.gitc3839b8
- First package
