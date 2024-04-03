## Infrastructure Provisioning with Pulumi (Python)

**This project uses Pulumi for infrastructure provisioning on AWS and GCP. Follow the steps below to set up your environment and deploy the infrastructure**.

## Prerequisites

<ul>
<li> Ensure you have [Pulumi](https://www.pulumi.com/docs/get-started/) installed on your machine.</li>

<li>Create AWS and GCP accounts, and have both the AWS CLI and GCP CLI installed and configured with your respective credentials.</li>
</ul>

## Setup and Installation

**Step 1** : Clone the Repository
```bash
git clone git@github.com:DeepakSawalka/iac_pulumi_python.git
```
**Step 2** : Create Virtual Environment inside the folder
```bash
python3 -m venv .venv
```
**Step 3** : Activate Virtual Environment in cmd.exe 
```bash
.\venv\Scripts\activate
```
**Step 4** : Install dependencies from requirements.txt file
```bash
pip install -r requirements.txt
```
## Deploying Infrastructure

**Step 1** : Initialize a New Pulumi Project 
```bash
pulumi new *< project-name >*
```
This command will prompt you to enter a project name and stack name. The stack corresponds to your deployment environment (e.g., dev, test, or prod).

**Step 2** : Create new Stack (if working with multiple environments)
```bash
pulumi stack init *< stack-name >*
```
**Step 3** : Configure your Stack 
```bash
pulumi config set < key > < value > [--path] [--plaintext] [--secret]
```
<ul>
<li> <key> : The configuration key to set. This usually follows the format < namespace >:< configName >.
< value >: The value to assign to the key.</li>
<li>--path: Specifies that the key should be treated as a path to a property in a map or list to set.</li>
<li>--plaintext: Stores the value as plaintext (this is the default behavior).</li>
<li>--secret: Stores the value as a secret.</li> 
</ul>