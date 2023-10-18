resource "aws_sns_topic" "incoming" {
  name = "stdf-alert-pipeline-${var.name}-incoming"
}

resource "aws_sns_topic_policy" "incoming_cross_account" {
  arn = aws_sns_topic.incoming.arn
  policy = data.aws_iam_policy_document.incoming_sns_cross_account.json
}

data "aws_iam_policy_document" "incoming_sns_cross_account" {
  statement {
    sid = "CrossAccount"
    actions = [
      "SNS:Publish"
    ]
    resources = [
      aws_sns_topic.incoming.arn
    ]
    effect = "Allow"
    principals {
      type = "AWS"
      identifiers = var.allowed_accounts
    }
  }

  statement {
    sid = "CrossAccountWithCloudWatch"
    actions = [
      "SNS:Publish"
    ]
    resources = [
      aws_sns_topic.incoming.arn
    ]
    effect = "Allow"
    principals {
      type = "AWS"
      identifiers = [
        "*"
      ]
    }
    condition {
      test = "StringEquals"
      variable = "AWS:SourceOwner"
      values = var.allowed_accounts
    }
  }

  statement {
    sid = "CloudWatchEventsToSNSTopic"
    effect = "Allow"
    principals {
      type = "Service"
      identifiers = [
        "events.amazonaws.com"
      ]
    }
    actions = [
      "SNS:Publish"
    ]
    resources = [
      aws_sns_topic.incoming.arn
    ]
  }
}

resource "aws_sns_topic_subscription" "incoming" {
  topic_arn = aws_sns_topic.incoming.arn
  protocol = "lambda"
  endpoint = aws_lambda_function.converter_lambda.arn
}

resource "aws_lambda_permission" "converter_lambda_with_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.converter_lambda.arn
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.incoming.arn
}

data "archive_file" "converter_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_converter"
  output_path = "${path.module}/lambda_converter.zip"
}

resource "aws_lambda_function" "converter_lambda" {
  filename         = "${path.module}/lambda_converter.zip"
  source_code_hash = data.archive_file.converter_lambda_zip.output_base64sha256
  function_name    = "stdf-alert-pipeline-${var.name}-converter"
  description      = "Converts alerts from various formats into STDF"
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.11"
  role             = aws_iam_role.converter_lambda.arn
  environment {
    variables = {
      OUTGOING_SNS_TOPIC = aws_sns_topic.fanout.arn
    }
  }
  timeout     = 10
  memory_size = 128
}

data "aws_iam_policy" "basic_execution_role_policy" {
  arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role" "converter_lambda" {
  name               = "stdf-alert-pipeline-${var.name}-converter"
  path               = "/"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      }
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy" "converter_lambda" {
  name   = "stdf-alert-pipeline-${var.name}-converter"
  role   = aws_iam_role.converter_lambda.id
  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sns:Publish"
      ],
      "Resource": [
        "${aws_sns_topic.fanout.arn}"
      ]
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "converter_lambda_basic_execution_role_policy" {
  role       = aws_iam_role.converter_lambda.name
  policy_arn = data.aws_iam_policy.basic_execution_role_policy.arn
}


resource "aws_cloudwatch_metric_alarm" "converter_lambda_alarm" {
  alarm_name          = "stdf-alert-pipeline-${var.name}-converter-alarm"
  alarm_description   = "STDF alert pipeline ${var.name} FAILED at the converter lambda!"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  dimensions = {
    FunctionName = aws_lambda_function.converter_lambda.function_name
  }
  threshold                 = "1"
  period                    = "60"
  statistic                 = "Sum"
  treat_missing_data        = "missing"
  insufficient_data_actions = []
  alarm_actions             = [var.fallback_sns]
}

resource "aws_sns_topic" "fanout" {
  name = "stdf-alert-pipeline-${var.name}-fanout"
}

resource "aws_sns_topic_subscription" "fanout" {
  topic_arn = aws_sns_topic.fanout.arn
  protocol = "lambda"
  endpoint = aws_lambda_function.slack_lambda.arn
}

resource "aws_lambda_permission" "slack_lambda_with_sns" {
  statement_id  = "AllowExecutionFromSNS"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.slack_lambda.arn
  principal     = "sns.amazonaws.com"
  source_arn    = aws_sns_topic.fanout.arn
}

data "archive_file" "slack_lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_slack"
  output_path = "${path.module}/lambda_slack.zip"
}

resource "aws_lambda_function" "slack_lambda" {
  filename         = "${path.module}/lambda_slack.zip"
  source_code_hash = data.archive_file.slack_lambda_zip.output_base64sha256
  function_name    = "stdf-alert-pipeline-${var.name}-slack"
  description      = "Posts STDF alerts to slack"
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.11"
  role             = aws_iam_role.slack_lambda.arn
  environment {
    variables = {
      SLACK_WEBHOOK_SECRET_ID = aws_secretsmanager_secret.slack_webhook.id
    }
  }
  timeout     = 10
  memory_size = 128
}

resource "aws_iam_role" "slack_lambda" {
  name               = "stdf-alert-pipeline-${var.name}-slack"
  path               = "/"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Action": "sts:AssumeRole",
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      }
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy" "slack_lambda" {
  name   = "stdf-alert-pipeline-${var.name}-slack"
  role   = aws_iam_role.slack_lambda.id
  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue"
      ],
      "Resource": [
        "${aws_secretsmanager_secret.slack_webhook.arn}"
      ]
    }
  ]
}
POLICY
}

resource "aws_iam_role_policy_attachment" "slack_lambda_basic_execution_role_policy" {
  role       = aws_iam_role.slack_lambda.name
  policy_arn = data.aws_iam_policy.basic_execution_role_policy.arn
}

resource "aws_cloudwatch_metric_alarm" "slack_lambda_alarm" {
  alarm_name          = "stdf-alert-pipeline-${var.name}-slack-alarm"
  alarm_description   = "STDF alert pipeline ${var.name} FAILED at the slack lambda!"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = "1"
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  dimensions = {
    FunctionName = aws_lambda_function.slack_lambda.function_name
  }
  threshold                 = "1"
  period                    = "60"
  statistic                 = "Sum"
  treat_missing_data        = "missing"
  insufficient_data_actions = []
  alarm_actions             = [var.fallback_sns]
}

resource "aws_secretsmanager_secret" "slack_webhook" {
  name = "stdf-alert-pipeline-${var.name}-slack-webhook"
}
