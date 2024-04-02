"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws
import base64
import pulumi_gcp as gcp
import json


# Load configurations
config = pulumi.Config("pulumi_python")
aws_config = pulumi.Config("aws")
gcp_config = pulumi.Config("gcp")

# Get the AWS profile from the config
aws_profile = aws_config.require("profile")

# Get AWS region from configuration
aws_region = aws_config.require("region")

# Get the GCP project Id from the config
gcp_projectId = gcp_config.require("project")

# Get GCP region from configuration
gcp_region = gcp_config.require("region")

# Configure AWS provider with the specified region
aws_provider = aws.Provider("aws_provider", region=aws_region, profile=aws_profile)

# Configure GCP provider with the specified region
gcp_provider = gcp.Provider("gcp_provider", project=gcp_projectId, region=gcp_region)

vpcName = config.require("vpcName")
vpcCidrBlock = config.require("vpcCidrBlock")
internetGatewayName = config.require("internetGatewayName")
publicRtName = config.require("publicRtName")
privateRtName = config.require("privateRtName")
publicSubnet = config.require("publicSubnet")
privateSubnet = config.require("privateSubnet")
publicCidrBlock = config.require("publicCidrBlock")
subnetMask = config.require("subnetMask")
myParameterGroupName = config.require("myParameterGroupName")
dbSubnetGrpName = config.require("dbSubnetGrpName")
engine = config.require("engine")
engineVersion = config.require("engineVersion")
identifier = config.require("identifier")
instanceClass = config.require("instanceClass")
dbName = config.require("dbName")
storageType = config.require("storageType")
allocatedStorage = config.require("allocatedStorage")
dbUsername= config.require_secret("dbUsername")
dbPassword = config.require_secret("dbPassword")
amiId = config.require("amiId")
keyPair = config.require("keyPair")
ec2Name = config.require("ec2Name")
domainName = config.require("domainName")
hosted_zone_id = config.require("hosted_zone_id")
applicationPort = config.require("applicationPort")
listenerPort = config.require("listenerPort")
maxSize = config.require("maxSize")
minSize = config.require("minSize")
cap = config.require("cap")
coolDown = config.require("coolDown")
period = config.require("period")
upThreshold = config.require("upThreshold")
downThreshold = config.require("downThreshold")
snsTopicName = config.require("snsTopicName")
bucketAccountId = config.require("bucketAccountId")
bucketDisplayName = config.require("bucketDisplayName")
gcpBucketName = config.require("gcpBucketName")
location = config.require("location")
mailgunApiKey = config.require_secret("mailgunApiKey")
mailgunDomain = config.require("mailgunDomain")
DynamoDbTableName = config.require("DynamoDbTableName")
lambdaFilePath = config.require("lambdaFilePath")


# Create a Google Service Account
bucket_service_account = gcp.serviceaccount.Account("myBucketAccount",
    account_id=bucketAccountId,
    display_name=bucketDisplayName
    )

# Assign the Service Account Admin role to the newly created service account
service_account_admin_binding = gcp.projects.IAMBinding("serviceAccountAdminBinding",
    members=[pulumi.Output.concat("serviceAccount:", bucket_service_account.email)],
    role="roles/iam.serviceAccountAdmin",
    project=gcp_projectId)

# Create a Google Cloud Storage Bucket
bucket = gcp.storage.Bucket("myBucket",
    name=gcpBucketName,
    location=location,
    force_destroy=True)

# Create access key for the bucket service account
bucket_service_account_key = gcp.serviceaccount.Key("bucketAccessKey",
    service_account_id=bucket_service_account.name,
    public_key_type="TYPE_X509_PEM_FILE")

# Create a new VPC for the current AWS region.
vpc = aws.ec2.Vpc(vpcName,
                  cidr_block=vpcCidrBlock,
                  tags= {"Name": vpcName})


#fetching the available az's
available_azs = aws.get_availability_zones(state="available")

# limit the az's to 3
azs = available_azs.names[:3]

def calculate_subnet_cidr_block(vpc_cidr_block: str, subnet_index: int) -> str:
    cidr_parts = vpc_cidr_block.split('/')
    ip_parts = list(map(int, cidr_parts[0].split('.')))
    
    # Increment the third octet based on the subnet index
    ip_parts[2] += subnet_index

    if ip_parts[2] > 255:
        # Handle this case accordingly; in this example, we're throwing an error
        raise ValueError('Exceeded the maximum number of subnets for the given VPC CIDR block')

    subnet_ip = '.'.join(map(str, ip_parts))
    return f"{subnet_ip}/{subnetMask}"

public_subnet_ids = []
private_subnet_ids = []

for i, az in enumerate(azs):
    # Create a public subnet
    public_subnet = aws.ec2.Subnet(f"{publicSubnet}-{i}",
        vpc_id=vpc.id,
        cidr_block=calculate_subnet_cidr_block(vpcCidrBlock,i),
        availability_zone=az,
        map_public_ip_on_launch=True,
        tags= {"Name": f"{publicSubnet}-{i}"}
    )
    public_subnet_ids.append(public_subnet.id)

    # Create a private subnet 
    private_subnet = aws.ec2.Subnet(f"{privateSubnet}-{i}",
        vpc_id=vpc.id,
        cidr_block=calculate_subnet_cidr_block(vpcCidrBlock,i+3),
        availability_zone=az,
        tags= {"Name": f"{privateSubnet}-{i}"}
    )

    private_subnet_ids.append(private_subnet.id)

internet_gateway = aws.ec2.InternetGateway(internetGatewayName,
    vpc_id=vpc.id,
    tags= {"Name": internetGatewayName}
)

public_route_table = aws.ec2.RouteTable(publicRtName,
    vpc_id=vpc.id,
    routes=[
        aws.ec2.RouteTableRouteArgs(
            cidr_block=publicCidrBlock,
            gateway_id=internet_gateway.id,
        ),
    ],
    tags= {"Name": publicRtName}
)

for i, subnet_id in enumerate(public_subnet_ids):
    aws.ec2.RouteTableAssociation(f"{publicRtName}-{i}",
        route_table_id=public_route_table.id,
        subnet_id=subnet_id
    )

private_route_table = aws.ec2.RouteTable(privateRtName,
    vpc_id=vpc.id,
    tags= {"Name": privateRtName}
)

for i, subnet_id in enumerate(private_subnet_ids):
    aws.ec2.RouteTableAssociation(f"{privateRtName}-{i}",
        route_table_id=private_route_table.id,
        subnet_id=subnet_id
    )

# Create an SNS topic
sns_topic = aws.sns.Topic("myTopic", name=snsTopicName)

sns_topic_arn = pulumi.Output.all(aws_region, bucketAccountId, snsTopicName).apply(
    lambda args: f"arn:aws:sns:{args[0]}:{args[1]}:{args[2]}"
)

# Define a Lambda role with an AssumeRolePolicy
lambda_role = aws.iam.Role("lambdaRole",
    assume_role_policy=json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com",
            },
        }],
    })
)

# Attach the basic execution role policy to the Lambda role
aws.iam.RolePolicyAttachment("lambdaBasicExecutionRoleAttachment",
    role=lambda_role,
    policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
)

# Attach the Amazon SNS full access policy to the Lambda role
aws.iam.RolePolicyAttachment("lambdaSnsFullAccessPolicyAttachment",
    role=lambda_role,
    policy_arn="arn:aws:iam::aws:policy/AmazonSNSFullAccess"
)

# Define a DynamoDB table
dynamodb_table = aws.dynamodb.Table("myDynamoDbTable",
    name=DynamoDbTableName,
    attributes=[aws.dynamodb.TableAttributeArgs(
        name="id",
        type="S"
    )],
    hash_key="id",
    billing_mode="PAY_PER_REQUEST"
)

# Create a policy for DynamoDB operations
dynamodb_policy = aws.iam.Policy("dynamoDbPolicy",
    description="A policy for DynamoDB operations",
    policy=dynamodb_table.arn.apply(lambda arn: json.dumps({
        "Version": "2012-10-17",
        "Statement": [{
            "Action": [
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Effect": "Allow",
            "Resource": arn,
        }],
    }))
)

# Attach the DynamoDB policy to the Lambda role
aws.iam.RolePolicyAttachment("lambdaDynamoDbPolicyAttachment",
    role=lambda_role,
    policy_arn=dynamodb_policy.arn
)

# Define your Lambda function
lambda_function = aws.lambda_.Function("myLambdaFunction",
    runtime=aws.lambda_.Runtime.PYTHON3D11,
    code=pulumi.FileArchive(lambdaFilePath),  
    handler="main.handler",
    role=lambda_role.arn,
    environment=aws.lambda_.FunctionEnvironmentArgs(
        variables={
            "GOOGLE_CREDENTIALS": bucket_service_account_key.private_key.apply(
                lambda key: key.encode('utf-8').decode('utf-8')  
            ),
            "GCS_BUCKET_NAME": gcpBucketName,
            "MAILGUN_API_KEY": mailgunApiKey,
            "MAILGUN_DOMAIN": mailgunDomain,
            "DYNAMODB_TABLE": DynamoDbTableName,
            "REGION": aws_region
        },
    ),
)

# Create an SNS topic subscription for the Lambda function
lambda_subscription = aws.sns.TopicSubscription("myLambdaSubscription",
    topic=sns_topic.arn,
    protocol="lambda",
    endpoint=lambda_function.arn,
)

# Grant permission to SNS to invoke the Lambda function
lambda_permission = aws.lambda_.Permission("myLambdaPermission",
    action="lambda:InvokeFunction",
    function=lambda_function.name,
    principal="sns.amazonaws.com",
    source_arn=sns_topic.arn,
)

# Attach the roles/storage.objectCreator role to the service account for the bucket
bucket_iam_binding = gcp.storage.BucketIAMBinding("myBucketIamBinding",
    bucket=gcpBucketName,
    role="roles/storage.objectCreator",
    members=[pulumi.Output.concat("serviceAccount:", pulumi.Output.secret(bucket_service_account.email))]) 

lbSecurityGroup = aws.ec2.SecurityGroup("lb-sg",
    vpc_id=vpc.id,
    description="Load Balancer Security Group",
    ingress=[
        {
            "protocol": "tcp",
            "from_port": 80,
            "to_port": 80,
            "cidr_blocks": [publicCidrBlock]
        },
        {
            "protocol": "tcp",
            "from_port": 443,
            "to_port": 443,
            "cidr_blocks": [publicCidrBlock]
        },
    ],
    egress=[
        # Allow all outgoing traffic from the load balancer
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": [publicCidrBlock]
        },
    ])


appSecurityGroup = aws.ec2.SecurityGroup("app-sg",
    vpc_id=vpc.id,
    description="Application Security Group",
    ingress=[
        # Allow SSH (22) traffic 
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "security_groups": [lbSecurityGroup.id]
        },
        
        {
            "protocol": "tcp",
            "from_port": applicationPort,
            "to_port": applicationPort,
            "security_groups": [lbSecurityGroup.id]
        },
    ],
    egress=[
        # Allow all outgoing traffic
        {
            "protocol": "-1",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": [publicCidrBlock]
        },
    ],
)

rdsSecurityGroup = aws.ec2.SecurityGroup("rds-sg",
    vpc_id=vpc.id,
    description="RDS Security Group",
    ingress=[
        # Allow PostgreSQL (5432) traffic from the application security group
        {
            "protocol": "tcp",
            "from_port": 5432,
            "to_port": 5432,
            "security_groups": [appSecurityGroup.id]  
        }
    ],
    egress=[
        # Restrict all outgoing internet traffic
        {
            "protocol": "tcp",
            "from_port": 0,
            "to_port": 0,
            "cidr_blocks": [publicCidrBlock]
        }
    ]
)

dbParameterGroup = aws.rds.ParameterGroup(myParameterGroupName,
    family="Postgres16",
    description="Custom parameter group for PostgreSOL 16.1",
    parameters=[
        {
            "name": "max_connections",
            "value": "100",
            "applyMethod": "pending-reboot" 
        }
    ]
)

# Creating a DB subnet group
dbSubnetGroup = aws.rds.SubnetGroup(dbSubnetGrpName,
    subnet_ids=private_subnet_ids,  
    tags={
        "Name": dbSubnetGrpName,
    }
)

# Create an RDS instance with PostgreSQL
db_instance = aws.rds.Instance("mydbinstance",
    instance_class=instanceClass,
    db_subnet_group_name=dbSubnetGroup.name,
    parameter_group_name=dbParameterGroup.name,
    engine=engine,
    engine_version=engineVersion,
    allocated_storage=allocatedStorage,
    storage_type=storageType,
    username= dbUsername,
    password= dbPassword,
    skip_final_snapshot=True,
    vpc_security_group_ids=[rdsSecurityGroup.id],  
    publicly_accessible=False,
    identifier=identifier,
    db_name=dbName
)


def user_data(args):
    endpoint, username, password, database_name, aws_region, bucketAccountId, snsTopicName = args
    parts = endpoint.split(':')
    endpoint_host = parts[0]
    db_port = parts[1] if len(parts) > 1 else 'defaultPort'
    
    bash_script = f"""#!/bin/bash
ENV_FILE="/home/ec2-user/webapp/.env"

# Create or overwrite the environment file with the environment variables
echo "DBHOST={endpoint_host}" > $ENV_FILE
echo "DBPORT={db_port}" >> $ENV_FILE
echo "DBUSER={username}" >> $ENV_FILE
echo "DBPASS={password}" >> $ENV_FILE
echo "DATABASE={database_name}" >> $ENV_FILE
echo "PORT=5000" >> $ENV_FILE
echo "CSV_PATH=/home/ec2-user/webapp/users.csv" >> $ENV_FILE
echo "SNS_TOPIC_ARN=arn:aws:sns:{aws_region}:{bucketAccountId}:{snsTopicName}" >>$ENV_FILE
echo "AWS_REGION= {aws_region}" >> $ENV_FILE

# Optionally, you can change the owner and group of the file if needed
sudo chown ec2-user:ec2-group $ENV_FILE

# Adjust the permissions of the environment file
sudo chmod 600 $ENV_FILE

# Configure and restart the CloudWatch Agent
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -a fetch-config -m ec2 -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json -s
sudo systemctl restart amazon-cloudwatch-agent
"""
    return bash_script

user_data_script = pulumi.Output.all(db_instance.endpoint, dbUsername, dbPassword, dbName, aws_region, bucketAccountId, snsTopicName).apply(user_data)

cloud_watch_agent_server_policy = aws.iam.Policy("cloudWatchAgentServerPolicy",
    description="A policy that allows sending logs to CloudWatch and publishing to SNS topics",
    policy=pulumi.Output.all(aws_region, bucketAccountId, snsTopicName).apply(
        lambda args: json.dumps({
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "cloudwatch:PutMetricData",
                        "ec2:DescribeVolumes",
                        "ec2:DescribeTags",
                        "logs:PutLogEvents",
                        "logs:DescribeLogStreams",
                        "logs:DescribeLogGroups",
                        "logs:CreateLogStream",
                        "logs:CreateLogGroup",
                        "elasticloadbalancing:Describe*",
                        "autoscaling:DescribeAutoScalingGroups",
                        "autoscaling:DescribeAutoScalingInstances",
                        "autoscaling:DescribeLaunchConfigurations",
                        "autoscaling:DescribePolicies",
                        "sns:Publish",
                    ],
                    "Resource": "*"
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "ssm:GetParameter"
                    ],
                    "Resource": "arn:aws:ssm:*:*:parameter/AmazonCloudWatch-*"
                },
                {
                    "Effect": "Allow",
                    "Action": "sns:Publish",
                    "Resource": f"arn:aws:sns:{args[0]}:{args[1]}:{args[2]}"
                }
            ]
        })
    )
)

role = aws.iam.Role("cloudWatchAgentRole",
    assume_role_policy={
        "Version": "2012-10-17",
        "Statement": [{
            "Action": "sts:AssumeRole",
            "Principal": {
                "Service": "ec2.amazonaws.com",
            },
            "Effect": "Allow",
        }]
    })

aws.iam.RolePolicyAttachment("cloudWatchAgentRoleAttachment",
    role=role.name,
    policy_arn=cloud_watch_agent_server_policy.arn)

instance_profile = aws.iam.InstanceProfile("cloudWatchAgentInstanceProfile",
    role=role.name)

# Create an EC2 instance
ec2_instance = aws.ec2.Instance(ec2Name,
    ami=amiId,
    instance_type="t2.micro",
    vpc_security_group_ids=[appSecurityGroup.id],  
    subnet_id=pulumi.Output.from_input(public_subnet_ids[0]),  
    associate_public_ip_address=True,
    key_name=keyPair,
    disable_api_termination=False,  
    root_block_device=aws.ec2.InstanceRootBlockDeviceArgs(
        delete_on_termination=True,  # Ensure the EBS volume is deleted upon termination
        volume_size=25,  # Set the root volume size to 25 GB
        volume_type="gp2",  # Set the root volume type to General Purpose SSD (GP2)
    ),
    tags={
        "Name": ec2Name,
    },
    user_data=user_data_script,
     iam_instance_profile=instance_profile.name,
)

# Create a Load Balancer
app_load_balancer = aws.lb.LoadBalancer("appLoadBalancer",
    internal=False,
    security_groups=[lbSecurityGroup.id],
    subnets=public_subnet_ids,
    enable_deletion_protection=False)

# Create a Target Group
target_group = aws.lb.TargetGroup("targetGroup",
    port=applicationPort,
    protocol="HTTP",
    vpc_id=vpc.id,
    target_type="instance",
    health_check=aws.lb.TargetGroupHealthCheckArgs(
        enabled=True,
        path="/healthz"
    ))

# Create a Listener
listener = aws.lb.Listener("listener",
    load_balancer_arn=app_load_balancer.arn,
    port=listenerPort,
    default_actions=[aws.lb.ListenerDefaultActionArgs(
        type="forward",
        target_group_arn=target_group.arn,
    )])

# Create a Launch Template
launch_template = aws.ec2.LaunchTemplate("launch_template",
    image_id=amiId,
    instance_type="t2.micro",
    key_name=keyPair,
    network_interfaces=[aws.ec2.LaunchTemplateNetworkInterfaceArgs(
        associate_public_ip_address=True,
        security_groups=[appSecurityGroup.id],
    )],
    user_data=pulumi.Output.secret(user_data_script).apply(lambda ud: base64.b64encode(ud.encode('utf-8')).decode('utf-8')),  
    iam_instance_profile=aws.ec2.LaunchTemplateIamInstanceProfileArgs(
        name=instance_profile.name,
    ))

# Create an Auto Scaling Group
auto_scaling_group = aws.autoscaling.Group("webAppAutoScalingGroup",
    max_size=maxSize,
    min_size=minSize,
    desired_capacity=cap,
    vpc_zone_identifiers=pulumi.Output.from_input(public_subnet_ids),
    launch_template=aws.autoscaling.GroupLaunchTemplateArgs(
        id=launch_template.id,
        version="$Latest",
    ),
    tags=[{
        "key": "Name",
        "value": "web-app",
        "propagate_at_launch": True,
    }],
    default_cooldown=60,
    target_group_arns=[target_group.arn])

# Create scale up policy
scale_up_policy = aws.autoscaling.Policy("scaleUp",
    autoscaling_group_name=auto_scaling_group.name,
    cooldown=coolDown,
    adjustment_type="ChangeInCapacity",
    scaling_adjustment=1,
    metric_aggregation_type="Average",
    policy_type="SimpleScaling"
)

# Create scale down policy
scale_down_policy = aws.autoscaling.Policy("scaleDown",
    autoscaling_group_name=auto_scaling_group.name,
    cooldown=coolDown,
    adjustment_type="ChangeInCapacity",
    scaling_adjustment=-1,
    metric_aggregation_type="Average",
    policy_type="SimpleScaling"
)

# Create a CPU high CloudWatch alarm
cpu_high_alarm = aws.cloudwatch.MetricAlarm("cpuHighAlarm",
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    statistic="Average",
    period=period,
    evaluation_periods=1,
    threshold=upThreshold,
    comparison_operator="GreaterThanThreshold",
    alarm_actions=[scale_up_policy.arn],
    dimensions={"AutoScalingGroupName": auto_scaling_group.name}
)

# Create a CPU low CloudWatch alarm
cpu_low_alarm = aws.cloudwatch.MetricAlarm("cpuLowAlarm",
    metric_name="CPUUtilization",
    namespace="AWS/EC2",
    statistic="Average",
    period=period,
    evaluation_periods=1,
    threshold=downThreshold,
    comparison_operator="LessThanThreshold",
    alarm_actions=[scale_down_policy.arn],
    dimensions={"AutoScalingGroupName": auto_scaling_group.name}
)

'''
a_record = aws.route53.Record("aRecord",
    zone_id=hosted_zone_id,
    name=domainName,
    type="A",
    ttl=60,
    records=[pulumi.Output.from_input(ec2_instance.public_ip)])'''

aRecord = aws.route53.Record("aRecord",
    zone_id=hosted_zone_id,
    name=domainName,
    type="A",
    aliases=[{
        "name": app_load_balancer.dns_name,
        "zone_id": app_load_balancer.zone_id,
        "evaluate_target_health": True,
    }]
)



pulumi.export("vpcId", vpc.id)
pulumi.export("publicSubnetIds", pulumi.Output.all(*public_subnet_ids))
pulumi.export("privateSubnetIds", pulumi.Output.all(*private_subnet_ids))
pulumi.export("internetgatewayId", internet_gateway.id)
pulumi.export("publicroutetableId",public_route_table.id)
pulumi.export("privateroutetableId",private_route_table.id)
pulumi.export("appSecurityGroup",appSecurityGroup.id)
pulumi.export("rdsSecurityGroup",rdsSecurityGroup.id)
pulumi.export("ec2PublicIP",ec2_instance.public_ip)
pulumi.export("recordName",aRecord.name)
pulumi.export("recordType",aRecord.type)
# pulumi.export("recordTtl",a_record.ttl)
pulumi.export("lbSecurityGroup",lbSecurityGroup.id)
pulumi.export("snsTopicArn",sns_topic_arn)
pulumi.export("gcpBucketName",gcpBucketName)
pulumi.export("serviceAccountEmail",bucket_service_account.email)
pulumi.export("bucketServiceAccountKeyName",bucketAccountId)

