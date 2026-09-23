resource "aws_key_pair" "app" {
  key_name   = "${local.name_prefix}-app"
  public_key = var.ssh_public_key
}

resource "aws_eip" "app" {
  domain = "vpc"

  tags = {
    Name    = "${local.name_prefix}-app-eip"
    Project = var.project
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu_arm.id
  instance_type          = var.app_instance_type
  associate_public_ip_address = true
  key_name               = aws_key_pair.app.key_name
  subnet_id              = local.subnet_ids[0]
  vpc_security_group_ids = [aws_security_group.app.id]

  root_block_device {
    volume_size = var.app_volume_gb
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    domain_name       = var.domain_name
    letsencrypt_email = var.letsencrypt_email
    project           = var.project
  })

  tags = {
    Name    = "${local.name_prefix}-app"
    Project = var.project
  }

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

resource "aws_eip_association" "app" {
  instance_id   = aws_instance.app.id
  allocation_id = aws_eip.app.id
}
