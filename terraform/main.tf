provider "aws" {
  region     = var.aws_region
  access_key = var.aws_access_key
  secret_key = var.aws_secret_key
}

# 1. CREACIÓN DEL BUCKET
resource "aws_s3_bucket" "lambda_bucket" {
  bucket = "fastapi-subasta-code-bucket"
}

# 2. SUBIDA DEL ZIP AL BUCKET
resource "aws_s3_object" "lambda_zip_upload" {
  bucket = aws_s3_bucket.lambda_bucket.id
  key    = "function_lambda.zip"
  source = "${path.module}/../function_lambda.zip"
  etag   = filemd5("${path.module}/../function_lambda.zip")
  content_type = "application/zip"

  depends_on = [aws_s3_bucket.lambda_bucket]
}

# 3. IAM Role para la Lambda
resource "aws_iam_role" "lambda_exec_role" {
  name = "lambda_execution_role_subasta"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# 4. Política en línea para permitir a Lambda interactuar con otros servicios
resource "aws_iam_role_policy" "lambda_policy" {
  name = "lambda_subasta_policy"
  role = aws_iam_role.lambda_exec_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Permiso para CloudWatch Logs
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "*"
      },
      # Permiso para DynamoDB
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:Query"
        ]
        Resource = "*"
      },
      # Permiso para SQS
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage"
        ]
        Resource = "*"
      },
      # Permiso para SNS
      {
        Effect = "Allow"
        Action = [
          "sns:Publish",
          "sns:CreateTopic",
          "sns:Subscribe",
          "sns:ListSubscriptionsByTopic"
        ]
        Resource = "*"
      }
    ]
  })
}

resource "aws_dynamodb_table" "auction_items" {
  name           = "AuctionItems"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "id"

  attribute {
    name = "id"
    type = "S"
  }

  tags = {
    Environment = "prod"
    Project     = "subasta"
  }
}

resource "aws_dynamodb_table" "bids" {
  name           = "AuctionBids"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key     = "item_id"
  range_key    = "user_email"

  attribute {
    name = "item_id"
    type = "S"
  }

  attribute {
    name = "user_email"
    type = "S"
  }

  tags = {
    Environment = "prod"
    Project     = "subasta"
  }
}

resource "aws_lambda_function" "auction_api" {
  function_name    = "AuctionAPI"
  handler          = "lambda_function.handler"
  runtime          = "python3.8"
  role             = aws_iam_role.lambda_exec_role.arn
  s3_bucket     = aws_s3_bucket.lambda_bucket.bucket
  s3_key        = aws_s3_object.lambda_zip_upload.key
  timeout       = 30

  environment {
    variables = {
      SQS_QUEUE_URL        = aws_sqs_queue.bids_queue.id
      SNS_TOPIC_ARN        = aws_sns_topic.auction_notifications.arn
      DYNAMODB_TABLE_ITEMS = aws_dynamodb_table.auction_items.name
      DYNAMODB_TABLE_BIDS  = aws_dynamodb_table.bids.name
    }
  }

  depends_on = [
    aws_sqs_queue.bids_queue,
    aws_sns_topic.auction_notifications,
    aws_dynamodb_table.auction_items,
    aws_dynamodb_table.bids
  ]
}

resource "aws_api_gateway_rest_api" "auction_api" {
  name        = "AuctionAPI"
  description = "API for real-time auctions"
}

resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.auction_api.id
  parent_id   = aws_api_gateway_rest_api.auction_api.root_resource_id
  path_part   = "{proxy+}"
}

resource "aws_api_gateway_method" "proxy" {
  rest_api_id   = aws_api_gateway_rest_api.auction_api.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "lambda" {
  rest_api_id = aws_api_gateway_rest_api.auction_api.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy.http_method

  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auction_api.invoke_arn
}

# ROOT endpoint (para /)
resource "aws_api_gateway_method" "root" {
  rest_api_id   = aws_api_gateway_rest_api.auction_api.id
  resource_id   = aws_api_gateway_rest_api.auction_api.root_resource_id
  http_method   = "ANY"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "root_lambda" {
  rest_api_id             = aws_api_gateway_rest_api.auction_api.id
  resource_id             = aws_api_gateway_rest_api.auction_api.root_resource_id
  http_method             = aws_api_gateway_method.root.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.auction_api.invoke_arn
}

resource "aws_api_gateway_deployment" "auction_api" {
  depends_on  = [aws_api_gateway_integration.lambda, aws_api_gateway_integration.root_lambda]
  rest_api_id = aws_api_gateway_rest_api.auction_api.id
}

resource "aws_api_gateway_stage" "prod" {
  deployment_id = aws_api_gateway_deployment.auction_api.id
  rest_api_id   = aws_api_gateway_rest_api.auction_api.id
  stage_name    = "prod"
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.auction_api.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_api_gateway_rest_api.auction_api.execution_arn}/*/*"
}

resource "aws_sqs_queue" "bids_queue" {
  name = "BidsQueue"
}

# SNS Topic (sin suscripciones quemadas)
resource "aws_sns_topic" "auction_notifications" {
  name = "AuctionNotifications"
}