# DevOps Learning Plan

> From version control basics to complete CI/CD pipelines and Infrastructure as Code

**Timeline:** Weeks 1-14 (integrated throughout)
**Time Commitment:** 4-6 hours/week
**Goal:** Complete CI/CD pipelines for all projects with IaC and monitoring

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Week 1: Git Fundamentals](#week-1-git-fundamentals)
3. [Weeks 2-3: Docker & Containerization](#weeks-2-3-docker--containerization)
4. [Weeks 3-4: CI/CD Basics](#weeks-3-4-cicd-basics)
5. [Weeks 5-6: Terraform & IaC](#weeks-5-6-terraform--iac)
6. [Weeks 7-8: Monitoring & Security](#weeks-7-8-monitoring--security)
7. [Weeks 9-10: Kubernetes & AKS](#weeks-9-10-kubernetes--aks)
8. [Weeks 11-14: Advanced DevOps](#weeks-11-14-advanced-devops)
9. [Resources](#resources)
10. [Projects](#projects)

---

## 🎯 Overview

### What You'll Learn

- Git workflow and branching strategies
- Docker containerization and registries
- CI/CD pipelines with GitHub Actions and Azure Pipelines
- Infrastructure as Code with Terraform
- Container orchestration with Kubernetes
- Monitoring, logging, and observability
- DevSecOps practices

### Prerequisites

- Basic command line skills
- Programming fundamentals
- Azure account
- GitHub account

---

## Week 1: Git Fundamentals

### Topics

- [ ] Git installation and configuration
- [ ] Repository initialization and cloning
- [ ] Basic commands: add, commit, push, pull
- [ ] Branching and merging
- [ ] GitHub workflow
- [ ] Pull requests and code review

### Commands Reference

```bash
# Initial setup
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Repository basics
git init                          # Initialize new repo
git clone <url>                   # Clone existing repo
git status                        # Check current status

# Daily workflow
git add .                         # Stage all changes
git add <file>                    # Stage specific file
git commit -m "message"           # Commit with message
git push origin main              # Push to remote
git pull origin main              # Pull from remote

# Branching
git branch                        # List branches
git branch feature-name           # Create branch
git checkout feature-name         # Switch branch
git checkout -b feature-name      # Create and switch
git merge feature-name            # Merge branch

# View history
git log --oneline                 # Compact history
git diff                          # View changes
git diff --staged                 # View staged changes
```

### Best Practices

```bash
# Commit message format
# <type>: <short description>
#
# Types: feat, fix, docs, style, refactor, test, chore
# Examples:
git commit -m "feat: add user authentication"
git commit -m "fix: resolve login redirect issue"
git commit -m "docs: update API documentation"
```

### Practice

1. Create a new repository
2. Make 10+ commits with good messages
3. Create a feature branch
4. Submit a pull request
5. Merge the branch

### Project: Initialize Task Manager Repository

```bash
mkdir task-manager && cd task-manager
git init
echo "# Task Manager" > README.md
git add README.md
git commit -m "feat: initial commit"
git remote add origin <your-repo-url>
git push -u origin main
```

---

## Weeks 2-3: Docker & Containerization

### Topics

- [ ] Docker installation and basics
- [ ] Docker images and containers
- [ ] Writing Dockerfiles
- [ ] Docker Compose for multi-container apps
- [ ] Azure Container Registry (ACR)
- [ ] Best practices for production

### Docker Basics

```bash
# Image commands
docker images                     # List images
docker pull python:3.14           # Pull image
docker build -t myapp:v1 .        # Build image
docker rmi <image-id>             # Remove image

# Container commands
docker ps                         # List running containers
docker ps -a                      # List all containers
docker run -d -p 8080:80 myapp    # Run container
docker stop <container-id>        # Stop container
docker logs <container-id>        # View logs
docker exec -it <id> /bin/bash    # Enter container
```

### Dockerfile for FastAPI

```dockerfile
# Dockerfile
FROM python:3.14-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create non-root user
RUN useradd --create-home appuser
USER appuser

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Dockerfile for React (Multi-stage)

```dockerfile
# Build stage
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Docker Compose

```yaml
# docker-compose.yml
version: "3.8"

services:
  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/mydb
    depends_on:
      - db

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=mydb
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### Azure Container Registry

```bash
# Create ACR
az acr create --name myacr --resource-group myRG --sku Basic

# Login to ACR
az acr login --name myacr

# Tag and push image
docker tag myapp:v1 myacr.azurecr.io/myapp:v1
docker push myacr.azurecr.io/myapp:v1

# List images in ACR
az acr repository list --name myacr
```

### Practice

1. Containerize Task Manager backend
2. Containerize Task Manager frontend
3. Create docker-compose.yml for full stack
4. Push images to Azure Container Registry

---

## Weeks 3-4: CI/CD Basics

### Topics

- [ ] CI/CD concepts and benefits
- [ ] GitHub Actions fundamentals
- [ ] Azure Pipelines basics
- [ ] Build, test, and deploy workflows
- [ ] Deployment slots and staging
- [ ] Environment variables and secrets

### GitHub Actions Workflow

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

env:
  AZURE_WEBAPP_NAME: my-app-name
  PYTHON_VERSION: "3.11"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests
        run: pytest --cov=app tests/

      - name: Upload coverage
        uses: codecov/codecov-action@v3

  build:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build Docker image
        run: docker build -t myapp:${{ github.sha }} .

      - name: Login to ACR
        uses: azure/docker-login@v1
        with:
          login-server: ${{ secrets.ACR_LOGIN_SERVER }}
          username: ${{ secrets.ACR_USERNAME }}
          password: ${{ secrets.ACR_PASSWORD }}

      - name: Push to ACR
        run: |
          docker tag myapp:${{ github.sha }} ${{ secrets.ACR_LOGIN_SERVER }}/myapp:${{ github.sha }}
          docker push ${{ secrets.ACR_LOGIN_SERVER }}/myapp:${{ github.sha }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - name: Deploy to staging slot
        uses: azure/webapps-deploy@v2
        with:
          app-name: ${{ env.AZURE_WEBAPP_NAME }}
          slot-name: staging
          images: ${{ secrets.ACR_LOGIN_SERVER }}/myapp:${{ github.sha }}

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    environment: production
    steps:
      - name: Swap staging to production
        uses: azure/CLI@v1
        with:
          inlineScript: |
            az webapp deployment slot swap \
              --name ${{ env.AZURE_WEBAPP_NAME }} \
              --resource-group myRG \
              --slot staging \
              --target-slot production
```

### Azure Pipelines (YAML)

```yaml
# azure-pipelines.yml
trigger:
  branches:
    include:
      - main
      - develop

pool:
  vmImage: "ubuntu-latest"

variables:
  pythonVersion: "3.11"

stages:
  - stage: Test
    jobs:
      - job: RunTests
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: "$(pythonVersion)"

          - script: |
              pip install -r requirements.txt
              pip install pytest
              pytest tests/
            displayName: "Run tests"

  - stage: Build
    dependsOn: Test
    jobs:
      - job: BuildImage
        steps:
          - task: Docker@2
            inputs:
              containerRegistry: "myACR"
              repository: "myapp"
              command: "buildAndPush"
              Dockerfile: "**/Dockerfile"
              tags: "$(Build.BuildId)"

  - stage: Deploy
    dependsOn: Build
    jobs:
      - deployment: DeployToAzure
        environment: "production"
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureWebAppContainer@1
                  inputs:
                    azureSubscription: "mySubscription"
                    appName: "my-app-name"
                    containers: "myacr.azurecr.io/myapp:$(Build.BuildId)"
```

### Deployment Slots

```bash
# Create staging slot
az webapp deployment slot create --name myapp --resource-group myRG --slot staging

# Swap slots
az webapp deployment slot swap --name myapp --resource-group myRG --slot staging --target-slot production

# Configure slot-specific settings
az webapp config appsettings set --name myapp --resource-group myRG --slot staging \
    --settings ENVIRONMENT=staging
```

### Practice

1. Set up GitHub Actions for Task Manager
2. Configure build and test stages
3. Deploy to Azure App Service
4. Implement staging slot workflow

---

## Weeks 5-6: Terraform & IaC

### Topics

- [ ] Infrastructure as Code concepts
- [ ] Terraform basics and syntax
- [ ] Azure provider configuration
- [ ] State management
- [ ] Modules and best practices
- [ ] Terraform Cloud/Azure backend

### Terraform Basics

```hcl
# main.tf
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  backend "azurerm" {
    resource_group_name  = "tfstate-rg"
    storage_account_name = "tfstateaccount"
    container_name       = "tfstate"
    key                  = "terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

# Variables
variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "eastus"
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = "rg-${var.environment}"
  location = var.location

  tags = {
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# App Service Plan
resource "azurerm_service_plan" "main" {
  name                = "asp-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  os_type             = "Linux"
  sku_name            = "B1"
}

# App Service
resource "azurerm_linux_web_app" "main" {
  name                = "app-${var.environment}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.main.id

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }

  app_settings = {
    "ENVIRONMENT" = var.environment
  }
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# Outputs
output "app_url" {
  value = "https://${azurerm_linux_web_app.main.default_hostname}"
}
```

### Terraform Commands

```bash
# Initialize Terraform
terraform init

# Format code
terraform fmt

# Validate configuration
terraform validate

# Plan changes
terraform plan -out=tfplan

# Apply changes
terraform apply tfplan

# Destroy resources
terraform destroy

# Import existing resource
terraform import azurerm_resource_group.main /subscriptions/.../resourceGroups/myRG
```

### Terraform Modules

```hcl
# modules/webapp/main.tf
variable "name" {}
variable "resource_group_name" {}
variable "location" {}
variable "service_plan_id" {}

resource "azurerm_linux_web_app" "this" {
  name                = var.name
  resource_group_name = var.resource_group_name
  location            = var.location
  service_plan_id     = var.service_plan_id

  site_config {
    application_stack {
      python_version = "3.11"
    }
  }
}

output "hostname" {
  value = azurerm_linux_web_app.this.default_hostname
}

# Usage in main.tf
module "webapp" {
  source              = "./modules/webapp"
  name                = "myapp"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  service_plan_id     = azurerm_service_plan.main.id
}
```

### Complete Infrastructure Example

```hcl
# Full stack infrastructure
resource "azurerm_postgresql_flexible_server" "main" {
  name                = "psql-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  version             = "14"
  sku_name            = "B_Standard_B1ms"
  storage_mb          = 32768

  administrator_login    = "adminuser"
  administrator_password = var.db_password
}

resource "azurerm_storage_account" "main" {
  name                     = "st${var.environment}${random_string.suffix.result}"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_key_vault" "main" {
  name                = "kv-${var.environment}-${random_string.suffix.result}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tenant_id           = data.azurerm_client_config.current.tenant_id
  sku_name            = "standard"
}
```

### Practice

1. Create Terraform configuration for Task Manager
2. Implement state storage in Azure
3. Create reusable modules
4. Integrate with CI/CD pipeline

---

## Weeks 7-8: Monitoring & Security

### Topics

- [ ] Application Insights setup
- [ ] Log Analytics and KQL queries
- [ ] Azure Monitor alerts
- [ ] DevSecOps practices
- [ ] Secret management
- [ ] Security scanning in pipelines

### Application Insights

```python
# Python with OpenCensus
from opencensus.ext.azure.log_exporter import AzureLogHandler
from opencensus.ext.azure.trace_exporter import AzureExporter
from opencensus.trace.samplers import ProbabilitySampler
from opencensus.ext.flask.flask_middleware import FlaskMiddleware
import logging

# Configure logging
logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(
    connection_string='InstrumentationKey=your-key'
))

# Configure tracing for Flask/FastAPI
middleware = FlaskMiddleware(
    app,
    exporter=AzureExporter(connection_string='InstrumentationKey=your-key'),
    sampler=ProbabilitySampler(rate=1.0)
)

# Custom events and metrics
logger.info('User logged in', extra={
    'custom_dimensions': {
        'user_id': '123',
        'action': 'login'
    }
})
```

### KQL Queries

```kusto
// Request performance
requests
| where timestamp > ago(24h)
| summarize
    count(),
    avg(duration),
    percentile(duration, 95)
    by bin(timestamp, 1h)
| render timechart

// Error rate
requests
| where timestamp > ago(24h)
| summarize
    total = count(),
    failed = countif(success == false)
| extend error_rate = failed * 100.0 / total

// Slow requests
requests
| where timestamp > ago(1h)
| where duration > 1000
| project timestamp, name, duration, resultCode
| order by duration desc
| take 10

// Dependency failures
dependencies
| where timestamp > ago(24h)
| where success == false
| summarize count() by name, resultCode
| order by count_ desc
```

### Azure Monitor Alerts (Terraform)

```hcl
resource "azurerm_monitor_metric_alert" "high_cpu" {
  name                = "high-cpu-alert"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_linux_web_app.main.id]
  description         = "Alert when CPU exceeds 80%"

  criteria {
    metric_namespace = "Microsoft.Web/sites"
    metric_name      = "CpuPercentage"
    aggregation      = "Average"
    operator         = "GreaterThan"
    threshold        = 80
  }

  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }
}

resource "azurerm_monitor_action_group" "main" {
  name                = "alert-action-group"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "alerts"

  email_receiver {
    name          = "admin"
    email_address = "admin@example.com"
  }
}
```

### Security Scanning in CI/CD

```yaml
# Add to GitHub Actions
jobs:
  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      # Dependency vulnerability scan
      - name: Run Snyk
        uses: snyk/actions/python@master
        env:
          SNYK_TOKEN: ${{ secrets.SNYK_TOKEN }}

      # Static code analysis
      - name: Run Bandit
        run: |
          pip install bandit
          bandit -r app/ -f json -o bandit-report.json

      # Container scan
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          image-ref: "myapp:${{ github.sha }}"
          format: "sarif"
          output: "trivy-results.sarif"

      # Secret scanning
      - name: Run Gitleaks
        uses: gitleaks/gitleaks-action@v2
```

### Practice

1. Set up Application Insights for Task Manager
2. Create custom dashboards in Azure Portal
3. Configure alerts for errors and performance
4. Add security scanning to CI/CD pipeline

---

## Weeks 9-10: Kubernetes & AKS

### Topics

- [ ] Kubernetes concepts (Pods, Deployments, Services)
- [ ] Azure Kubernetes Service (AKS)
- [ ] Kubernetes manifests
- [ ] Helm charts basics
- [ ] Ingress and networking
- [ ] ConfigMaps and Secrets

### Kubernetes Manifests

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend
  labels:
    app: backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: backend
  template:
    metadata:
      labels:
        app: backend
    spec:
      containers:
        - name: backend
          image: myacr.azurecr.io/backend:v1
          ports:
            - containerPort: 8000
          env:
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: app-secrets
                  key: database-url
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 30
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
---
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
spec:
  selector:
    app: backend
  ports:
    - protocol: TCP
      port: 80
      targetPort: 8000
  type: ClusterIP
---
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app-ingress
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
spec:
  tls:
    - hosts:
        - myapp.example.com
      secretName: tls-secret
  rules:
    - host: myapp.example.com
      http:
        paths:
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: backend
                port:
                  number: 80
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
```

### AKS Setup

```bash
# Create AKS cluster
az aks create \
    --name myAKSCluster \
    --resource-group myRG \
    --node-count 2 \
    --node-vm-size Standard_B2s \
    --enable-managed-identity \
    --attach-acr myacr

# Get credentials
az aks get-credentials --name myAKSCluster --resource-group myRG

# Verify connection
kubectl get nodes

# Deploy application
kubectl apply -f deployment.yaml
kubectl apply -f service.yaml
kubectl apply -f ingress.yaml

# Check status
kubectl get pods
kubectl get services
kubectl logs <pod-name>
```

### kubectl Commands

```bash
# Cluster info
kubectl cluster-info
kubectl get nodes

# Workloads
kubectl get pods
kubectl get deployments
kubectl get services

# Debugging
kubectl describe pod <pod-name>
kubectl logs <pod-name>
kubectl exec -it <pod-name> -- /bin/sh

# Scaling
kubectl scale deployment backend --replicas=5

# Updates
kubectl set image deployment/backend backend=myacr.azurecr.io/backend:v2
kubectl rollout status deployment/backend
kubectl rollout undo deployment/backend
```

### Practice

1. Create AKS cluster with Terraform
2. Deploy Task Manager to AKS
3. Configure ingress with HTTPS
4. Implement rolling updates

---

## Weeks 11-14: Advanced DevOps

### Topics

- [ ] GitOps with Flux or ArgoCD
- [ ] Canary deployments
- [ ] Feature flags
- [ ] Infrastructure testing
- [ ] Cost optimization
- [ ] Multi-environment strategies

### GitOps with Flux

```yaml
# flux-system/kustomization.yaml
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: apps
  namespace: flux-system
spec:
  interval: 10m
  sourceRef:
    kind: GitRepository
    name: flux-system
  path: ./apps
  prune: true
  validation: client
```

### Feature Flags

```python
# Using Azure App Configuration
from azure.appconfiguration import AzureAppConfigurationClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = AzureAppConfigurationClient(
    base_url="https://myconfig.azconfig.io",
    credential=credential
)

# Check feature flag
feature = client.get_configuration_setting(
    key=".appconfig.featureflag/new-dashboard",
    label="production"
)

if feature.value.get("enabled"):
    # Show new dashboard
    pass
```

### Cost Optimization

```bash
# Right-sizing recommendations
az advisor recommendation list --category Cost

# Reserved instances analysis
az reservations reservation-order list

# Resource cleanup
az resource list --query "[?tags.Environment=='dev']" -o table
```

---

## 📚 Resources

### Books

- **"The Phoenix Project"** - DevOps mindset (novel)
- **"The DevOps Handbook"** - Best practices
- **"Python for DevOps"** - Automation with Python
- **"Docker Deep Dive"** - Container mastery
- **"Kubernetes: Up and Running"** - K8s fundamentals

### FREE Online Resources

- Azure DevOps Labs (hands-on)
- Docker Documentation
- Kubernetes Documentation
- Terraform Registry
- GitHub Learning Lab

### Tools

- VS Code with Docker/Kubernetes extensions
- Azure CLI
- kubectl
- Terraform
- Helm

---

## 💻 Projects

All three portfolio projects will include:

### DevOps Requirements

- [ ] Git repository with branching strategy
- [ ] Docker containerization (multi-stage builds)
- [ ] CI/CD pipeline (GitHub Actions or Azure Pipelines)
- [ ] Infrastructure as Code (Terraform)
- [ ] Monitoring and logging (Application Insights)
- [ ] Security scanning in pipeline

### Project 1: IT Asset Management

- Docker Compose for local development
- GitHub Actions CI/CD
- Deploy to Azure App Service
- Basic monitoring setup

### Project 2: Infrastructure Platform

- Terraform for all Azure resources
- AKS deployment
- Advanced monitoring and alerting
- Multi-environment (dev/staging/prod)

### Project 3: Portfolio Website

- Azure Static Web Apps
- Automated deployment from GitHub
- Custom domain with HTTPS

---

## ✅ Checklist

### Git & GitHub

- [ ] Daily commits with good messages
- [ ] Feature branches and pull requests
- [ ] Branch protection rules

### Docker

- [ ] All apps containerized
- [ ] Multi-stage builds for production
- [ ] Images pushed to ACR

### CI/CD

- [ ] Automated testing in pipeline
- [ ] Automated deployment to Azure
- [ ] Staging environment with slot swap

### Terraform

- [ ] All infrastructure as code
- [ ] State stored in Azure
- [ ] Modules for reusability

### Kubernetes

- [ ] At least one app deployed to AKS
- [ ] Proper resource limits
- [ ] Health checks configured

### Monitoring

- [ ] Application Insights configured
- [ ] Custom dashboards created
- [ ] Alerts for critical metrics

---

## 🏆 Success Metrics

| Milestone                     | Target  | Status |
| ----------------------------- | ------- | ------ |
| Git workflow established      | Week 1  | ⬜     |
| First app containerized       | Week 2  | ⬜     |
| CI/CD pipeline working        | Week 4  | ⬜     |
| Terraform for Project 1       | Week 5  | ⬜     |
| AKS deployment complete       | Week 10 | ⬜     |
| All projects with full DevOps | Week 14 | ⬜     |

---

**DevOps is about culture, automation, and continuous improvement. Build these skills, and you'll be invaluable to any team! 🚀**
