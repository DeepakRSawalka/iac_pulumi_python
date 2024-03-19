"""An AWS Python Pulumi program"""

import pulumi
import pulumi_aws as aws

# Load configurations
config = pulumi.Config("pulumi_python")
aws_config = pulumi.Config("aws")

# Get the AWS profile from the config
aws_profile = aws_config.require("profile")

# Get AWS region from configuration
region = aws_config.require("region")

# Configure AWS provider with the specified region
provider = aws.Provider("provider", region=region, profile=aws_profile)

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

appSecurityGroup = aws.ec2.SecurityGroup("app-sg",
    vpc_id=vpc.id,
    description="Application Security Group",
    ingress=[
        # Allow SSH (22) traffic 
        {
            "protocol": "tcp",
            "from_port": 22,
            "to_port": 22,
            "cidr_blocks": [publicCidrBlock]
        },
        # Allow HTTP (80) traffic
        {
            "protocol": "tcp",
            "from_port": 80,
            "to_port": 80,
            "cidr_blocks": [publicCidrBlock]
        },
        # Allow HTTPS (443) traffic 
        {
            "protocol": "tcp",
            "from_port": 443,
            "to_port": 443,
            "cidr_blocks": [publicCidrBlock]
        },
        # Replace 5000 with the port your application runs on
        {
            "protocol": "tcp",
            "from_port": 5000,
            "to_port": 5000,
            "cidr_blocks": [publicCidrBlock]
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
            "security_groups": [appSecurityGroup]  # Reference to app security group ID
        },
        # If you also want to allow PostgreSQL (5432), add another rule here
        {
            "protocol": "tcp",
            "from_port": 5432,
            "to_port": 5432,
            "security_groups": [appSecurityGroup]  # Reference to app security group ID
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
    family="PostgreSOL 16.1",
    description="Custom parameter group for PostgreSOL 16.1",
    parameters=[
        {
            "name": "max_connections",
            "value": "100"
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

user_data = pulumi.Output.all(db_instance.endpoint, dbUsername, dbPassword, dbName).apply(
    lambda args: f"""#!/bin/bash
ENV_FILE="/home/admin/webapp/.env"

# Create or overwrite the environment file with the environment variables
echo "DBHOST={args[0].split(':')[0]}" > $ENV_FILE
echo "DBPORT={args[0].split(':')[1]}" >> $ENV_FILE
echo "DBUSER={args[1]}" >> $ENV_FILE
echo "DBPASS={args[2]}" >> $ENV_FILE
echo "DATABASE={args[3]}" >> $ENV_FILE
echo "PORT=5000" >> $ENV_FILE
echo "CSV_PATH=/home/admin/webapp/users.csv" >> $ENV_FILE

# We change the owner and group of the file if needed
sudo chown admin:admin $ENV_FILE

# Adjust the permissions of the environment file
sudo chmod 600 $ENV_FILE
"""
)

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
    user_data=user_data,
    opts=pulumi.ResourceOptions(depends_on=public_subnet_ids)
)


pulumi.export("vpcId", vpc.id)
pulumi.export("publicSubnetIds", pulumi.Output.all(*public_subnet_ids))
pulumi.export("privateSubnetIds", pulumi.Output.all(*private_subnet_ids))
pulumi.export("internetgatewayId", internet_gateway.id)
pulumi.export("publicroutetableId",public_route_table.id)
pulumi.export("privateroutetableId",private_route_table.id)
pulumi.export("appSecurityGroup",appSecurityGroup.id)
pulumi.export("appSecurityGroup",appSecurityGroup.id)
pulumi.export("rdsSecurityGroup",rdsSecurityGroup.id)
pulumi.export("ec2PublicIP",ec2_instance.public_ip)

