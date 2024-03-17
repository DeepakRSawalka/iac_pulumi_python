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
cidrBlock = config.require("cidrBlock")
subnetMask = config.require("subnetMask")


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
            cidr_block=cidrBlock,
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


pulumi.export("vpcId", vpc.id)
pulumi.export("publicSubnetIds", pulumi.Output.all(*public_subnet_ids))
pulumi.export("privateSubnetIds", pulumi.Output.all(*private_subnet_ids))
pulumi.export("internetgatewayId", internet_gateway.id)
pulumi.export("publicroutetableId",public_route_table.id)
pulumi.export("privateroutetableId",private_route_table.id)
