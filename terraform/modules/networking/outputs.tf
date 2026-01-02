#------------------------------------------------------------------------------
# Networking Module - Outputs
#------------------------------------------------------------------------------

output "vpc_id" {
  value       = aws_vpc.main.id
  description = "ID of the VPC"
}

output "public_subnet_ids" {
  value       = [aws_subnet.public_a.id, aws_subnet.public_b.id]
  description = "List of public subnet IDs"
}

output "security_group_id" {
  value       = aws_security_group.vpc_connector.id
  description = "ID of the VPC connector security group"
}
