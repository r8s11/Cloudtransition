# Lead Cloud DevOps Engineer Roadmap — Regeneron (R46267)

> **This is the deep curriculum reference.** For the active calendar and weekly pace, see **[year-plan-2026-2027.md](year-plan-2026-2027.md)**, which schedules these phases against SNHU 8-week terms at ~5 hrs/week through end of 2027. The 24-week / 20-hr-week framing below is the original aggressive plan — kept intact for the curriculum content (books, courses, labs, capstone), but the actual pace is now stretched across ~16 months alongside school and part-time work.

A curriculum mapped directly to the Regeneron job requirements, using O'Reilly and No Starch Press books as primary texts, LinkedIn Learning courses for structured video learning, and curated YouTube channels for visual reinforcement and lab walkthroughs. Your homelab Docker Compose / ELK / Linux foundations from the *arr stack work mean this skips zero-to-hero filler and goes straight to production-grade depth.

---

## How to use this roadmap

- **Pace.** Originally sized for 20 hrs/week over 24 weeks. Now stretched to ~5 hrs/week alongside SNHU coursework, with lab work concentrated in term breaks. See [year-plan-2026-2027.md](year-plan-2026-2027.md) for the term-by-term schedule.
- **Books first, videos second.** Each phase has a primary book (deep reading), a supporting book (skim/reference), LinkedIn Learning courses (structured paths, often with completion certificates that appear on your LinkedIn profile), and YouTube channels (visual + free).
- **Build alongside reading — but break labs into term-break sprints.** Every phase ends with a hands-on lab in your AWS Free Tier account that produces an artifact for your portfolio. Reading happens during SNHU terms; labs happen during the ~1-week gaps between terms (or when SNHU coursework is light).
- **LinkedIn Learning certificates show up on your profile**, which a Regeneron recruiter will see when they look at you. That's a free signal — finish courses, accept the certificate, let it appear.
- **Capstone in Phase 7 is what you'll talk about in the Regeneron interview.** Build it on GitHub. Link it on your resume. Target completion: end of 2027.
- **Free-tier costs:** budget ~$15–25/month for stuff outside free tier (NAT gateways, EKS control plane $0.10/hr). Tear down resources nightly with `terraform destroy`.

**On LinkedIn Learning access:** NYPL and Brooklyn Public Library both offer free LinkedIn Learning to cardholders. Your VR&E counselor or veteran benefits office may also cover a paid subscription. Don't pay out of pocket if you can avoid it.

---

## Phase 1 — Linux + AWS Core (C-3 2026 reading + summer break labs)

**Maps to JD:** *"systems administration of Linux servers; Ubuntu workstations, Patching, backup, upgrades, and PAM authentication; EC2, EBS, S3, ELB, RDS"*

### Books

**Primary — *How Linux Works, 3rd Edition* by Brian Ward (No Starch Press, 2021)**
The reference text for Linux internals — boot process, systemd, the kernel, devices, networking, filesystems, LVM, cgroups, containers. New 3rd-edition coverage of LVM, virtualization, and containers is exactly what cloud engineers need. Read cover to cover. Chapters 4 (disks/filesystems), 7 (system configuration), 9 (networking), 13 (user environments), and 17 (virtualization/containers) are highest-leverage.

**Supporting — *The Linux Command Line, 2nd Edition* by William Shotts (No Starch Press)**
Reference for shell idioms. Drill into `find`, `xargs`, process substitution, `awk`, and shell scripting (Part IV). Patching/backup/upgrade automation lives here.

**Supporting — *Efficient Linux at the Command Line* by Daniel J. Barrett (O'Reilly, 2022)**
Shorter and complements Shotts. Pipelines, command substitution, terminal multiplexing — productivity multipliers.

### LinkedIn Learning
- ***Become a Linux System Administrator*** — full learning path by Grant McWilliams, Scott Simpson, and Kevin Dankwardt. ~30 hours. Covers installation, file systems, users/groups, networking, services, package management, scripting. The single best LinkedIn structured path for the Linux side of this JD.
- ***Linux: System Maintenance*** — patching, backups, kernel upgrades. Maps directly to the JD's "Patching, backup, upgrades" line.
- ***Linux Authentication: PAM*** — short focused course on PAM. Required reading for the JD. Make sure you can explain PAM stack ordering and `pam_unix` vs `pam_sss` vs `pam_google_authenticator` in an interview.
- ***Amazon Web Services: Foundations*** and ***Learning Amazon Web Services (AWS) for Developers*** — pair these to cover EC2, EBS, S3, ELB, RDS at survey level.

### YouTube
- **Stephane Maarek** — *AWS Certified Solutions Architect Associate (SAA-C03)* full course. The most efficient survey of AWS core services in existence.
- **AWS official channel** — *This is My Architecture* series. Short, real-world reference architectures.

### Lab (end of Phase 1)
1. Launch an Ubuntu 22.04 EC2 instance with an EBS volume, attach an additional gp3 volume, format with ext4, set up an LVM volume group, mount, and snapshot.
2. Configure unattended-upgrades, set up SSH key-only auth, install and configure PAM with Google Authenticator MFA for SSH.
3. Spin up an RDS Postgres instance, an Application Load Balancer in front of two EC2 instances running Nginx, write a bash script that nightly snapshots EBS + dumps RDS to S3.

---

## Phase 2 — Docker + Container Fundamentals (C-4 → C-5 2026)

**Maps to JD:** *"Containers and orchestration services such as docker, ECS, ECR…"*

### Books

**Primary — *Docker: Up & Running, 3rd Edition* by Sean P. Kane and Karl Matthias (O'Reilly, 2023)**
Production-focused. Image layering, BuildKit, multi-stage builds, healthchecks, secrets, security, runtime internals (containerd, runc). Container security chapter is gold for a regulated environment like a pharma research center.

**Supporting — *Container Security* by Liz Rice (O'Reilly)**
Short and dense. Read the chapters on image scanning, namespaces, capabilities, and seccomp. Comes up in every cloud DevOps interview.

### LinkedIn Learning
- ***Learning Docker*** by Arthur Ulfeldt — fundamentals and the container model.
- ***Docker Essential Training: 1 Installation and Configuration*** / ***2 Image Creation, Management, and Registries*** / ***3 Network and Data Management*** — three-part series, comprehensive and aligned with Docker Certified Associate exam objectives.
- ***Docker on AWS*** by Brandon Rich — wires Docker concepts to ECS, ECR, and Fargate. Maps directly to the JD's specific service list.

### YouTube
- **Bret Fisher** — *Docker Mastery* live streams and Docker Tips series. Bret runs Docker Captain office hours; the Q&A clips are pure gold.
- **TechWorld with Nana** — *Docker Tutorial for Beginners* (2-hour single video). Even as review, the diagrams are some of the clearest visual explanations of layers and networks anywhere.

### Lab (end of Phase 2)
1. Take one of your *arr stack services and rewrite the Dockerfile as a multi-stage build that produces an image under 100MB.
2. Push images to ECR, scan with Trivy, sign with cosign.
3. Migrate one Compose service (e.g., Sonarr or Jellyfin) to AWS ECS on Fargate behind an ALB. Wire up CloudWatch logs.

---

## Phase 3 — Kubernetes + EKS (C-6 2026 → C-1 2027)

**Maps to JD:** *"EKS… Fargate"* and *"Lead effort to containerize various applications and tools and implement container orchestration"*

This is where Lead-level candidates separate from mid-level. EKS is what Regeneron will lean on you for.

### Books

**Primary — *Kubernetes: Up and Running, 3rd Edition* by Brendan Burns, Joe Beda, Kelsey Hightower, Lachlan Evenson (O'Reilly, 2022)**
Authors invented Kubernetes. Pods, deployments, services, ingress, RBAC, secrets, network policy, custom resources, operators. The 3rd edition's policy/governance and security-context chapters are critical for biotech regulatory environments.

**Supporting — *Cloud Native DevOps with Kubernetes, 2nd Edition* by John Arundel and Justin Domingus (O'Reilly)**
The "real-world ops" companion. Helm, GitOps, observability, autoscaling, cost.

**Reference — *Kubernetes Patterns* by Bilgin Ibryam and Roland Huß (O'Reilly)**
Sidecar, ambassador, adapter, init containers, operator. Need this language fluently in interviews.

### LinkedIn Learning
- ***Learning Kubernetes*** by Karthik Gaekwad — 4.8/5 with 4,000+ ratings. The canonical introduction. Karthik works on Kubernetes professionally; treat this as required.
- ***Kubernetes: Native Tools*** — kubectl deep dive, Minikube, kubeadm, kops.
- ***Kubernetes: Microservices*** — Helm, Jaeger, breaking a monolith into services on K8s.
- ***Running Kubernetes on AWS (EKS)*** — directly maps to JD's named technology. EKS clusters, scaling workers, EC2 vs Fargate node selection, EKS networking, EBS CSI, monitoring EKS deployments.
- ***Master Cloud-Native Infrastructure with Kubernetes*** learning path — combines several courses above; finish this and the certificate is a strong LinkedIn signal.

### YouTube
- **TechWorld with Nana** — *Kubernetes Tutorial for Beginners* (full 4-hour course). The single best free Kubernetes overview anywhere.
- **Anton Putra** — production-grade EKS, Karpenter, EBS CSI driver tutorials. Senior-engineer level.
- **Viktor Farcic / DevOps Toolkit** — tool comparisons and opinionated takes. Watch his ArgoCD vs Flux and Karpenter vs Cluster Autoscaler videos.
- **CNCF official channel** — KubeCon talks. Pick 2–3 from the most recent KubeCon to see where the field is going.

### Lab (end of Phase 3)
1. Stand up an EKS cluster with `eksctl`, deploy a sample microservices app (Google's "online boutique" demo).
2. Configure IRSA (IAM Roles for Service Accounts), set up the AWS Load Balancer Controller, deploy with Ingress + ACM TLS.
3. Mix Fargate and managed node groups in the same cluster. Document when you'd choose each.
4. Write a Confluence-style runbook: "How to deploy a new app to our EKS cluster" — this is the SOP work the JD calls out.

---

## Phase 4 — Infrastructure as Code (C-2 → C-3 2027)

**Maps to JD:** *"CloudFormation scripts to automate the server deployment and configuration… Drive automation of operations and management of infrastructure as code"*

JD specifically names CloudFormation, but in 2026 most shops use Terraform with CloudFormation as legacy. Learn both.

### Books

**Primary — *Terraform: Up and Running, 3rd Edition* by Yevgeniy Brikman (O'Reilly, 2022)**
Definitive Terraform book. Modules, state management, workspaces, secret management (new chapter), testing infrastructure code, multi-account/multi-region patterns. Chapter 9 (testing Terraform with Terratest) is what separates senior from lead candidates.

**Primary — *Infrastructure as Code, 3rd Edition* by Kief Morris (O'Reilly, 2024)**
Tool-agnostic principles — drift, idempotency, blast radius, environment promotion, testing pyramids for infra. Required reading before you write any production Terraform you'll have to maintain.

**Reference — *AWS CloudFormation User Guide* (free, AWS docs)**
Read User Guide chapters on intrinsic functions, nested stacks, change sets, drift detection, and StackSets.

### LinkedIn Learning
- ***Infrastructure as Code with Terraform*** — full learning path. Bundles *Learning Terraform* (Josh Samuelson) and *Advanced Terraform* (David Swersky). Covers Terraform CLI, HCL, modules, state, remote backends, GitHub + Terraform Cloud CI/CD pipeline. Both courses pair Terraform directly with AWS, which matches your target.
- ***Learning Terraform*** by Josh Samuelson — beginner-friendly, AWS-focused.
- ***Advanced Terraform*** by David Swersky — variables, looping, custom modules, remote state backends, multi-environment patterns, end-to-end CI/CD example.
- ***DevOps Foundations: Infrastructure as Code*** — tool-agnostic IaC concepts; nice complement to Kief Morris's book.
- ***AWS for DevOps: CloudFormation, Service Catalog, and AMIs*** — for the CloudFormation half of the JD requirement. Includes deploying CloudFormation from GitHub via CodePipeline.

### YouTube
- **Anton Putra** — Terraform AWS series, including state backend setup with S3 + DynamoDB locking.
- **DevOps Directive** — *Complete Terraform Course (BEGINNER to PRO)*. Single best free Terraform video.
- **Be A Better Dev (Daniel Henderson)** — CloudFormation tutorials including StackSets and CDK comparisons.

### Lab (end of Phase 4)
1. Rebuild your entire Phase 1–3 lab as Terraform code: VPC, EKS cluster, RDS, ALB, S3, IAM, IRSA. Modularize.
2. Write the same VPC + EC2 + RDS stack as a CloudFormation template. Note the differences in your README — this is interview material.
3. Configure remote state (S3 + DynamoDB), workspaces for dev/staging/prod, and a basic Terratest test that asserts the ALB returns 200.

---

## Phase 5 — Monitoring, Metrics, Logging (C-4 2027)

**Maps to JD:** *"Deploy and lead monitoring, metrics, and logging capabilities on cloud engineering platforms"*

You already have ELK + Grafana running at home, so this phase formalizes what you know and adds Prometheus + observability theory.

### Books

**Primary — *Prometheus: Up & Running, 2nd Edition* by Brian Brazil (O'Reilly, 2023)**
Brazil is on the Prometheus core team. PromQL, recording/alerting rules, exporters, federation, long-term storage. This is what you'll wire into EKS.

**Primary — *Observability Engineering* by Charity Majors, Liz Fong-Jones, George Miranda (O'Reilly, 2022)**
Concepts > tools. Why metrics, logs, and traces are not interchangeable. High-cardinality data. SLOs and error budgets. Interview-ready vocabulary.

**Reference — *Site Reliability Engineering* (Google's free O'Reilly book at sre.google/books)**
Chapters on monitoring, alerting philosophy ("4 golden signals"), SLO/SLI definitions, postmortems. Free online; print is also an O'Reilly title.

### LinkedIn Learning
- ***DevOps Foundations: Monitoring and Observability*** — concepts course, lighter than the books but a fast structured intro.
- ***DevOps Foundations: Site Reliability Engineering*** by Ernest Mueller and James Wickett — release engineering, change management, incident management, retrospectives, SLAs/SLOs. Direct map to the "leadership for cloud DevOps engineers" line in the JD.
- ***Graphite and Grafana: Visualizing Application Performance*** — Grafana fundamentals.
- ***Learning the Elastic Stack*** — ELK refresher. Covers Kibana, Logstash, and Elasticsearch in a structured way (you've used these but not formally studied them).

> **Note:** LinkedIn Learning's Prometheus catalog is thinner than the O'Reilly book. If you want video coverage equivalent to the book, supplement with Anton Putra's Prometheus playlist on YouTube (free) or a one-off Udemy course like *Mastering Prometheus and Grafana*.

### YouTube
- **Grafana official channel** — GrafanaCON talks and Loki/Tempo/Mimir walkthroughs.
- **Anton Putra** — Prometheus + Grafana production setup videos.
- **KubeCon talks on observability** — search "KubeCon observability" sorted by recent.

### Lab (end of Phase 5)
1. Deploy `kube-prometheus-stack` Helm chart to your EKS cluster. Configure alerts for pod restart loops, node disk pressure, and ALB 5xx rate.
2. Add OpenTelemetry instrumentation to one of your demo services, ship traces to AWS X-Ray and to a self-hosted Tempo. Compare.
3. Write three SLOs (availability, latency, error rate) for one of your services with documented error budgets.

---

## Phase 6 — Web Servers (C-5 2027)

**Maps to JD:** *"Web server administration – Tomcat, Apache, and Nginx"*

This section of the JD gets undersold. Many DevOps candidates have never actually tuned a Tomcat heap or written an Nginx upstream config. Be the candidate who has.

### Books

**Primary — *NGINX Cookbook, 2nd Edition* by Derek DeJonghe (O'Reilly, 2022)**
Recipe format makes this fast. Reverse proxy, load balancing algorithms, caching, rate limiting, mTLS, NGINX as Kubernetes Ingress controller.

**Reference — Apache HTTP Server documentation (free)** — focus on `mod_rewrite`, `mod_proxy`, MPM tuning, and `.htaccess` vs server-config patterns.

**Reference — Apache Tomcat documentation (free)** — focus on `server.xml`, connectors (NIO/APR), `JAVA_OPTS` heap tuning, valves, and clustering. The JD likely means Tomcat as part of the Java application stack used by Regeneron's bioinformatics tools.

### LinkedIn Learning
- ***NGINX Essential Training*** — installation, configuration syntax, virtual hosts, reverse proxy, load balancing. Directly maps to JD requirement.
- ***Learning Apache Web Server*** / ***Apache Web Server: Administration*** — installation, virtual hosts, modules, tuning. Older course but still accurate for Apache 2.4.
- ***Tomcat Essential Training*** — basic Tomcat administration. LinkedIn's Tomcat coverage is thinner than the others; supplement with Apache's official docs.
- ***Web Servers and APIs using Java*** — context for how Tomcat fits into a Java EE bioinformatics application stack, which is likely what Regeneron's scientists run.

### YouTube
- **Jeff Geerling** — Ansible-based playbooks for Apache/Tomcat hardening. Practical, sysadmin-flavored.
- **Hussein Nasser** — backend networking deep dives. Connection pooling, keepalive, HTTP/2 vs HTTP/3 — fluency at interview level.

### Lab (end of Phase 6)
1. Deploy Tomcat on EC2 running a sample Java WAR. Tune the connector for ~5,000 concurrent connections, set Xmx/Xms appropriately, configure access logs to ship to CloudWatch.
2. Stand up Nginx as a reverse proxy in front of three Tomcat instances with health checks, sticky sessions, and gzip. Benchmark with `wrk`.
3. Repeat the same proxy setup using Apache HTTPD with `mod_proxy_balancer`. Document tradeoffs.

---

## Phase 7 — Capstone Project (C-5 → C-6 2027)

The artifact you'll show in the Regeneron interview. JD explicitly mentions *"Develop solutions to parallelize the legacy/standalone jobs and run them on distributed computational platforms"* — Regeneron is a genomics company, so think bioinformatics pipelines.

### Build: "Genomics-style batch pipeline on AWS"

1. **Infra** — Terraform-managed VPC, EKS cluster (with Fargate profile for batch), S3 buckets for input/output, IAM via IRSA, RDS Postgres for job metadata.
2. **Pipeline** — A "fan-out" workflow: input file in S3 → SQS → Karpenter-spawned worker pods on EKS each run a stub bioinformatics tool (containerized BLAST or samtools call against a sample dataset) → results back to S3.
3. **Orchestration** — Argo Workflows on EKS, or AWS Batch with Fargate. Compare both in your README.
4. **Observability** — Prometheus, Grafana, Loki, AWS X-Ray. SLO dashboard.
5. **CI/CD** — GitHub Actions: lint Terraform → plan → apply on merge → build container → push ECR → deploy via ArgoCD.
6. **Security** — Trivy scans in CI, Falco runtime monitoring on EKS, AWS GuardDuty enabled, all secrets in AWS Secrets Manager pulled via IRSA.
7. **Runbook** — Markdown SOP for "How to onboard a new analysis tool to the platform." This *is* the work the JD describes.

Push it all to GitHub. Long README with architecture diagram (draw.io or Excalidraw). Resume bullet:

> *"Production-style genomics batch pipeline on AWS EKS with full IaC, observability, and CI/CD — 100% Terraform-managed."*

---

## LinkedIn Learning macro paths (parallel to phases)

Two large pre-built paths are worth completing for the LinkedIn profile certificates alone:

- ***Become a DevOps Engineer*** — 25-course, ~50-hour comprehensive path. Touches everything: DevOps foundations, Ansible, Docker, Jenkins, ELK, Nagios, Grafana, SRE, Kubernetes (× 3 courses), DevSecOps, microservices, cloud-native. Treat this as a parallel rail you complete over weeks 1–24, not a sequential prereq. Finish for the badge.
- ***AWS Certified Solutions Architect Associate (SAA-C03) Cert Prep*** — pair with Stephane Maarek's Udemy course. Sit the exam after Phase 1.

---

## Always-on YouTube channels (subscribe, don't binge)

| Channel | Why |
|---|---|
| **TechWorld with Nana** | Best diagrams in the business. Conceptual clarity on K8s, Docker, CI/CD. |
| **Anton Putra** | Production-grade AWS + K8s tutorials. Lead-engineer level. |
| **Bret Fisher** | Docker/Kubernetes live streams. Real Q&A from working engineers. |
| **DevOps Toolkit (Viktor Farcic)** | Tool comparisons and opinionated reviews. |
| **Jeff Geerling** | Ansible, homelab, sysadmin sensibility. |
| **Stephane Maarek** | AWS certification courses. Reference-grade. |
| **Hussein Nasser** | Backend networking and database internals. |
| **CNCF** | KubeCon talks. Stay current. |
| **AWS official** | re:Invent talks and *This is My Architecture*. |

---

## Certifications to stack (parallel to roadmap)

JD doesn't require certs, but they give external validation while you study. LinkedIn Learning has prep courses for all of these:

- **AWS Solutions Architect Associate (SAA-C03)** — sit at end of Phase 1.
- **AWS DevOps Engineer Professional (DOP-C02)** — sit at end of Phase 5.
- **Certified Kubernetes Administrator (CKA)** — sit at end of Phase 3. Hands-on exam.
- **HashiCorp Terraform Associate** — sit at end of Phase 4.

---

## Veteran benefit reminder

VR&E (Chapter 31) and the Post-9/11 GI Bill can both reimburse certification exams (CKA, AWS, HashiCorp). Talk to MOVA if you haven't filed for cert reimbursement before — it's a real benefit most reservists don't use.

---

## Consolidated reference list

### No Starch Press
- *How Linux Works, 3rd Edition* — Brian Ward
- *The Linux Command Line, 2nd Edition* — William Shotts

### O'Reilly
- *Efficient Linux at the Command Line* — Daniel J. Barrett
- *Docker: Up & Running, 3rd Edition* — Sean P. Kane, Karl Matthias
- *Container Security* — Liz Rice
- *Kubernetes: Up and Running, 3rd Edition* — Burns, Beda, Hightower, Evenson
- *Cloud Native DevOps with Kubernetes, 2nd Edition* — Arundel, Domingus
- *Kubernetes Patterns* — Ibryam, Huß
- *Terraform: Up and Running, 3rd Edition* — Yevgeniy Brikman
- *Infrastructure as Code, 3rd Edition* — Kief Morris
- *Prometheus: Up & Running, 2nd Edition* — Brian Brazil
- *Observability Engineering* — Majors, Fong-Jones, Miranda
- *Site Reliability Engineering* — Google (free at sre.google/books)
- *NGINX Cookbook, 2nd Edition* — Derek DeJonghe

### LinkedIn Learning courses (by phase)

**Phase 1 — Linux + AWS Core**
- Become a Linux System Administrator (learning path)
- Linux: System Maintenance
- Linux Authentication: PAM
- Amazon Web Services: Foundations
- Learning Amazon Web Services (AWS) for Developers

**Phase 2 — Docker**
- Learning Docker
- Docker Essential Training: 1, 2, and 3
- Docker on AWS

**Phase 3 — Kubernetes + EKS**
- Learning Kubernetes (Karthik Gaekwad)
- Kubernetes: Native Tools
- Kubernetes: Microservices
- Running Kubernetes on AWS (EKS)
- Master Cloud-Native Infrastructure with Kubernetes (path)

**Phase 4 — IaC**
- Infrastructure as Code with Terraform (learning path)
- Learning Terraform (Josh Samuelson)
- Advanced Terraform (David Swersky)
- DevOps Foundations: Infrastructure as Code
- AWS for DevOps: CloudFormation, Service Catalog, and AMIs

**Phase 5 — Monitoring**
- DevOps Foundations: Monitoring and Observability
- DevOps Foundations: Site Reliability Engineering
- Graphite and Grafana: Visualizing Application Performance
- Learning the Elastic Stack

**Phase 6 — Web Servers**
- NGINX Essential Training
- Apache Web Server: Administration
- Tomcat Essential Training
- Web Servers and APIs using Java

**Macro paths**
- Become a DevOps Engineer (25-course path)
- AWS Certified Solutions Architect Associate Cert Prep
- AWS Certified DevOps Engineer Professional Cert Prep

---

## Budget note

If pay out-of-pocket: an O'Reilly Online Learning subscription (~$49/mo) gives access to every O'Reilly title above plus video courses. ACM membership ($99/year) bundles a discounted O'Reilly subscription. NYPL and Brooklyn Public Library cards give free O'Reilly Online and free LinkedIn Learning. Stack the library access with a VR&E or GI Bill cert reimbursement and the entire roadmap can run at near zero cost.

Very respectfully,
Roadmap built for R46267.
