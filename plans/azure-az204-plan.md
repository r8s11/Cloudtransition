# Azure & AZ-204 Certification Plan

> From Azure basics to certified Azure Developer Associate

**Timeline:** Weeks 3-22
**Exam:** Week 22
**Time Commitment:** 6-8 hours/week
**Study Hours:** 60-80 hours total
**Goal:** Pass AZ-204 exam (700/1000 minimum)

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Exam Domains](#exam-domains)
3. [Week-by-Week Study Plan](#week-by-week-study-plan)
4. [Hands-On Labs](#hands-on-labs)
5. [Resources](#resources)
6. [Practice Exams Strategy](#practice-exams-strategy)
7. [Exam Day Tips](#exam-day-tips)

---

## 🎯 Overview

### What You'll Learn

- Azure compute solutions (App Service, Functions, Containers)
- Azure storage solutions (Blob, Cosmos DB, Azure SQL)
- Azure security implementation (Azure AD, Key Vault, Managed Identity)
- Monitoring and troubleshooting (Application Insights)
- Azure service integration (API Management, Event Grid, Service Bus)

### Prerequisites

- Azure free account ($200 credit)
- Basic programming knowledge (Python preferred)
- Understanding of REST APIs
- Familiarity with cloud concepts

---

## 📊 Exam Domains

### 1. Develop Azure Compute Solutions (25-30%)

**Topics:**

- Azure App Service Web Apps
- Azure Functions
- Azure Container Instances (ACI)
- Azure Container Apps
- Azure Kubernetes Service (AKS)

**Key Skills:**

```bash
# Create App Service
az webapp create --name myapp --resource-group myRG --plan myPlan

# Deploy to App Service
az webapp deployment source config-zip --src app.zip --name myapp --resource-group myRG

# Create Azure Function
func init MyFunctionProj --python
func new --name HttpTrigger --template "HTTP trigger"
```

### 2. Develop for Azure Storage (15-20%)

**Topics:**

- Azure Blob Storage
- Azure Cosmos DB
- Azure SQL Database

**Key Skills:**

```python
# Blob Storage with Python SDK
from azure.storage.blob import BlobServiceClient

blob_service = BlobServiceClient.from_connection_string(conn_str)
container = blob_service.get_container_client("mycontainer")
blob = container.get_blob_client("myfile.txt")
blob.upload_blob(data)
```

```python
# Cosmos DB with Python SDK
from azure.cosmos import CosmosClient

client = CosmosClient(endpoint, key)
database = client.get_database_client("mydb")
container = database.get_container_client("mycontainer")
container.create_item(body={"id": "1", "name": "item1"})
```

### 3. Implement Azure Security (15-20%)

**Topics:**

- Azure Active Directory (Entra ID)
- Azure Key Vault
- Managed Identities
- Secure data solutions

**Key Skills:**

```python
# Key Vault with Python SDK
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://myvault.vault.azure.net", credential=credential)
secret = client.get_secret("my-secret")
print(secret.value)
```

### 4. Monitor, Troubleshoot, and Optimize (5-10%)

**Topics:**

- Application Insights
- Azure Monitor
- Caching solutions (Azure Cache for Redis)

**Key Skills:**

```python
# Application Insights with OpenCensus
from opencensus.ext.azure.log_exporter import AzureLogHandler
import logging

logger = logging.getLogger(__name__)
logger.addHandler(AzureLogHandler(connection_string='InstrumentationKey=xxx'))
logger.warning("Custom log message")
```

### 5. Connect to and Consume Azure Services (20-25%)

**Topics:**

- API Management
- Event Grid
- Azure Service Bus
- Azure Queue Storage

**Key Skills:**

```python
# Service Bus with Python SDK
from azure.servicebus import ServiceBusClient, ServiceBusMessage

client = ServiceBusClient.from_connection_string(conn_str)
sender = client.get_queue_sender(queue_name="myqueue")
sender.send_messages(ServiceBusMessage("Hello, World!"))
```

---

## 📅 Week-by-Week Study Plan

### Weeks 3-6: Compute Solutions (10 hours)

**Topics:**

- [ ] Azure App Service deep dive
- [ ] Deployment slots and staging
- [ ] Azure Functions triggers and bindings
- [ ] Durable Functions
- [ ] Container Instances vs Container Apps

**Microsoft Learn Paths:**

- "Create serverless applications"
- "Deploy a website to Azure with Azure App Service"

**Hands-On:**

```bash
# Create Function App
az functionapp create --name myfunc --storage-account mystorage \
    --consumption-plan-location eastus --resource-group myRG \
    --runtime python --runtime-version 3.14 --functions-version 4

# Deploy function
func azure functionapp publish myfunc
```

**Practice Project:** Deploy Task Manager to App Service with deployment slots

---

### Weeks 7-10: Storage Solutions (8 hours)

**Topics:**

- [ ] Blob Storage tiers (Hot, Cool, Archive)
- [ ] Blob lifecycle management
- [ ] Cosmos DB partitioning and consistency levels
- [ ] Azure SQL Database DTU vs vCore

**Microsoft Learn Paths:**

- "Store data in Azure"
- "Work with NoSQL data in Azure Cosmos DB"

**Hands-On:**

```python
# Cosmos DB query with partition key
items = container.query_items(
    query="SELECT * FROM c WHERE c.category = @category",
    parameters=[{"name": "@category", "value": "electronics"}],
    partition_key="electronics"
)
```

**Practice Project:** Add Blob Storage for file uploads in IT Asset Management

---

### Weeks 11-14: Security Implementation (8 hours)

**Topics:**

- [ ] Microsoft Entra ID (Azure AD) authentication
- [ ] OAuth 2.0 and OpenID Connect
- [ ] Managed Identities (system vs user assigned)
- [ ] Key Vault access policies and RBAC
- [ ] Secure App Configuration

**Microsoft Learn Paths:**

- "Secure your cloud data"
- "Implement Azure Key Vault"

**Hands-On:**

```bash
# Create Key Vault
az keyvault create --name myvault --resource-group myRG --location eastus

# Add secret
az keyvault secret set --vault-name myvault --name "DatabasePassword" --value "SuperSecret123"

# Enable managed identity for App Service
az webapp identity assign --name myapp --resource-group myRG
```

**Practice Project:** Migrate secrets to Key Vault with Managed Identity

---

### Weeks 15-16: Monitoring & Service Integration (6 hours)

**Topics:**

- [ ] Application Insights setup and configuration
- [ ] Custom metrics and events
- [ ] API Management policies
- [ ] Event Grid subscriptions
- [ ] Service Bus queues and topics

**Microsoft Learn Paths:**

- "Monitor the usage, performance, and availability"
- "Enable reliable messaging for Big Data applications"

**Hands-On:**

```python
# Custom telemetry
from applicationinsights import TelemetryClient

tc = TelemetryClient('instrumentation-key')
tc.track_event('UserLoggedIn', {'user_id': '123'})
tc.track_metric('ResponseTime', 0.5)
tc.flush()
```

---

### Weeks 17-18: First Practice Exam (8 hours)

**Goals:**

- [ ] Complete full practice exam
- [ ] Score 75%+ target
- [ ] Identify weak areas
- [ ] Review incorrect answers

**Strategy:**

1. Take practice exam under timed conditions
2. Review EVERY question (correct and incorrect)
3. Create flashcards for weak areas
4. Map weak areas to Microsoft Learn modules

---

### Weeks 19-20: Intensive Review (10 hours)

**Goals:**

- [ ] Focus on weak domains
- [ ] Second practice exam (85%+ target)
- [ ] Hands-on labs for weak areas
- [ ] Review official documentation

**Daily Schedule:**

- Morning: 1 hour study weak areas
- Evening: 1 hour hands-on practice
- Night: 30 min flashcard review

---

### Weeks 21-22: Exam Week

**Monday-Tuesday:**

- Light review only
- Focus on rest and relaxation
- Review quick reference notes

**Wednesday: Exam Day! 🎉**

- Arrive 15 minutes early
- Read questions carefully
- Flag difficult questions, return later
- PASS! ✅

---

## 🧪 Hands-On Labs

### Required Labs (Complete Before Week 9)

1. **Deploy App Service with CI/CD** - GitHub Actions to App Service
2. **Create Azure Function** - HTTP trigger with Cosmos DB binding
3. **Implement Blob Storage** - Upload, download, lifecycle policies
4. **Configure Key Vault** - Secrets with Managed Identity
5. **Set Up Application Insights** - Custom metrics and alerts
6. **Create Service Bus Queue** - Producer/consumer pattern

### Lab Environment Setup

```bash
# Create resource group for labs
az group create --name az204-labs --location eastus

# Set default resource group
az configure --defaults group=az204-labs

# Clean up after labs
az group delete --name az204-labs --yes --no-wait
```

---

## 📚 Resources

### FREE Resources

- **Microsoft Learn** - Official learning paths (40+ hours)
- **Azure Documentation** - Reference material
- **Azure Friday** - YouTube video series
- **Azure Tips and Tricks** - Quick tutorials

### Paid Resources

- **"Exam Ref AZ-204"** - Microsoft Press ($40)
- **MeasureUp Practice Exams** - Official practice tests ($99)
- **Whizlabs** - Practice exams and labs ($30)
- **Pluralsight** - Video courses (subscription)

### Recommended Study Order

1. Microsoft Learn paths (free, official)
2. Hands-on labs (build real projects)
3. Exam Ref book (deep dive)
4. Practice exams (test readiness)

---

## 📝 Practice Exams Strategy

### Weeks 17-18: First Practice Exam

- **Goal:** 75%+ score
- **Focus:** Identify knowledge gaps
- **Action:** Create targeted study plan

### Weeks 19-20: Second Practice Exam

- **Goal:** 85%+ score
- **Focus:** Validate improvement
- **Action:** Final weak area review

### Practice Exam Tips

- Simulate real exam conditions (timed, no notes)
- Review ALL answers, even correct ones
- Understand WHY each answer is correct
- Create flashcards for missed concepts

---

## 🎯 Exam Day Tips

### Before the Exam

- Get 8 hours of sleep
- Eat a good breakfast
- Arrive 15 minutes early
- Bring valid ID

### During the Exam

- Read each question completely
- Look for keywords (MOST, LEAST, FIRST)
- Eliminate obviously wrong answers
- Flag difficult questions for review
- Don't spend too long on one question

### Question Types

- **Multiple choice** - One correct answer
- **Multiple select** - Multiple correct answers
- **Drag and drop** - Order or match items
- **Case studies** - Multiple questions about a scenario

---

## ✅ Checklist

### Compute (25-30%)

- [ ] App Service configuration and deployment
- [ ] Azure Functions triggers and bindings
- [ ] Container solutions (ACI, AKS)
- [ ] Deployment slots and staging

### Storage (15-20%)

- [ ] Blob Storage operations and tiers
- [ ] Cosmos DB queries and partitioning
- [ ] Azure SQL Database connections

### Security (15-20%)

- [ ] Azure AD authentication flows
- [ ] Key Vault operations
- [ ] Managed Identities implementation

### Monitoring (5-10%)

- [ ] Application Insights configuration
- [ ] Custom metrics and logging

### Services (20-25%)

- [ ] API Management policies
- [ ] Event Grid and Service Bus
- [ ] Message queuing patterns

---

## 🏆 Success Metrics

| Milestone                      | Target      | Status |
| ------------------------------ | ----------- | ------ |
| Microsoft Learn paths complete | Weeks 15-16 | ⬜     |
| First practice exam 75%+       | Weeks 17-18 | ⬜     |
| Second practice exam 85%+      | Weeks 19-20 | ⬜     |
| All hands-on labs complete     | Weeks 19-20 | ⬜     |
| **AZ-204 CERTIFIED**           | Weeks 21-22 | ⬜     |

---

**This certification will validate your Azure skills and open doors to cloud developer roles. Stay focused, practice hands-on, and you WILL pass! 🚀**
