import os
import unittest
import json
import terraform_validate


class TestTerraformConfig(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = os.path.join(os.path.dirname(os.path.realpath(__file__)), '..')
        return super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        return super().tearDownClass()

    def setUp(self):
        self.validator = terraform_validate.Validator(self.path)
        self.validator.error_if_property_missing()
        return super().setUp()

    def tearDown(self):
        return super().tearDown()

    def get_resources_by_type_and_name(self, resource_type, resource_name):
        all_of_type = self.validator.resources(resource_type)
        resources = terraform_validate.TerraformResourceList(all_of_type.validator, all_of_type.resource_types, {})
        for resource in all_of_type.resource_list:
            if resource.name == resource_name:
                resources.resource_list.append(resource)
        return resources

    def assert_resources_match(self, resources, spec):
        for resource_property in spec:
            resources.property(resource_property).should_equal(spec[resource_property])
        return

    def test_incoming_sns_topic(self):
        # Arrange
        expected_resource_type = 'aws_sns_topic'
        expected_resource_name = 'incoming'
        expected_number_of_resources = 1
        expected_properties = {
            'name': 'stdf-alert-pipeline-${var.name}-incoming',
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_incoming_sns_topic_policy(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_sns_topic_policy'
        expected_resource_name = 'incoming_cross_account'

        expected_properties = {
            'arn': 'aws_sns_topic.incoming.arn',
            'policy': 'data.aws_iam_policy_document.incoming_sns_cross_account.json'
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_incoming_sns_subscription(self):
        # Arrange
        expected_resource_type = 'aws_sns_topic_subscription'
        expected_resource_name = 'incoming'
        expected_number_of_resources = 1
        expected_properties = {
            'topic_arn': 'aws_sns_topic.incoming.arn',
            'protocol': 'lambda',
            'endpoint': 'aws_lambda_function.converter_lambda.arn',
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)


    def test_converter_lambda_permission(self):
        # Arrange
        expected_resource_type = 'aws_lambda_permission'
        expected_resource_name = 'converter_lambda_with_sns'
        expected_number_of_resources = 1
        expected_properties = {
            'statement_id': 'AllowExecutionFromSNS',
            'action': "lambda:InvokeFunction",
            'function_name': 'aws_lambda_function.converter_lambda.arn',
            'principal': 'sns.amazonaws.com',
            'source_arn': 'aws_sns_topic.incoming.arn'
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_converter_lambda_function(self):
        # Arrange
        expected_resource_type = 'aws_lambda_function'
        expected_resource_name = 'converter_lambda'
        expected_number_of_resources = 1

        expected_environment = {
            'variables': {
                'OUTGOING_SNS_TOPIC': 'aws_sns_topic.fanout.arn',
            }
        }

        expected_properties = {
            'filename': '${path.module}/lambda_converter.zip',
            'source_code_hash': 'data.archive_file.converter_lambda_zip.output_base64sha256',
            'function_name': 'stdf-alert-pipeline-${var.name}-converter',
            'description': 'Converts alerts from various formats into STDF',
            'handler': 'lambda_function.lambda_handler',
            'runtime': 'python3.11',
            'role': 'aws_iam_role.converter_lambda.arn',
            'environment': expected_environment,
            'timeout': 10,
            'memory_size': 128
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_converter_lambda_role(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_iam_role'
        expected_resource_name = 'converter_lambda'

        expected_assume_role_policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'sts:AssumeRole',
                    'Effect': 'Allow',
                    'Principal': {
                        'Service': 'lambda.amazonaws.com'
                    }
                }
            ]
        }

        expected_properties = {
            'name': 'stdf-alert-pipeline-${var.name}-converter',
            'path': '/',
            'assume_role_policy': json.dumps(expected_assume_role_policy, indent=2),
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_converter_lambda_role_policy(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_iam_role_policy'
        expected_resource_name = 'converter_lambda'

        expected_inline_role_policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        'sns:Publish'
                    ],
                    'Resource': [
                        '${aws_sns_topic.fanout.arn}'
                    ]
                }
            ]
        }

        expected_properties = {
            'name': 'stdf-alert-pipeline-${var.name}-converter',
            'role': 'aws_iam_role.converter_lambda.id',
            'policy': json.dumps(expected_inline_role_policy, indent=2),
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_converter_lambda_alarm(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_cloudwatch_metric_alarm'
        expected_resource_name = 'converter_lambda_alarm'

        expected_properties = {
            'alarm_name': 'stdf-alert-pipeline-${var.name}-converter-alarm',
            'alarm_description': 'STDF alert pipeline ${var.name} FAILED at the converter lambda!',
            'comparison_operator': 'GreaterThanOrEqualToThreshold',
            'evaluation_periods': '1',
            'metric_name': 'Errors',
            'namespace': 'AWS/Lambda',
            'dimensions': {
                'FunctionName': 'aws_lambda_function.converter_lambda.function_name'
            },
            'threshold': '1',
            'period': '60',
            'statistic': 'Sum',
            'treat_missing_data': 'missing',
            'insufficient_data_actions': [],
            'alarm_actions': ['var.fallback_sns'],
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_fanout_sns_topic(self):
        # Arrange
        expected_resource_type = 'aws_sns_topic'
        expected_resource_name = 'fanout'
        expected_number_of_resources = 1
        expected_properties = {
            'name': 'stdf-alert-pipeline-${var.name}-fanout',
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_fanout_sns_subscription(self):
        # Arrange
        expected_resource_type = 'aws_sns_topic_subscription'
        expected_resource_name = 'fanout'
        expected_number_of_resources = 1
        expected_properties = {
            'topic_arn': 'aws_sns_topic.fanout.arn',
            'protocol': 'lambda',
            'endpoint': 'aws_lambda_function.slack_lambda.arn',
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_slack_lambda_permission(self):
        # Arrange
        expected_resource_type = 'aws_lambda_permission'
        expected_resource_name = 'slack_lambda_with_sns'
        expected_number_of_resources = 1
        expected_properties = {
            'statement_id': 'AllowExecutionFromSNS',
            'action': "lambda:InvokeFunction",
            'function_name': 'aws_lambda_function.slack_lambda.arn',
            'principal': 'sns.amazonaws.com',
            'source_arn': 'aws_sns_topic.fanout.arn'
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_slack_lambda_function(self):
        # Arrange
        expected_resource_type = 'aws_lambda_function'
        expected_resource_name = 'slack_lambda'
        expected_number_of_resources = 1

        expected_environment = {
            'variables': {
                'SLACK_WEBHOOK_SECRET_ID': 'aws_secretsmanager_secret.slack_webhook.id',
            }
        }

        expected_properties = {
            'filename': '${path.module}/lambda_slack.zip',
            'source_code_hash': 'data.archive_file.slack_lambda_zip.output_base64sha256',
            'function_name': 'stdf-alert-pipeline-${var.name}-slack',
            'description': 'Posts STDF alerts to slack',
            'handler': 'lambda_function.lambda_handler',
            'runtime': 'python3.11',
            'role': 'aws_iam_role.slack_lambda.arn',
            'environment': expected_environment,
            'timeout': 10,
            'memory_size': 128
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_slack_lambda_role(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_iam_role'
        expected_resource_name = 'slack_lambda'

        expected_assume_role_policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Action': 'sts:AssumeRole',
                    'Effect': 'Allow',
                    'Principal': {
                        'Service': 'lambda.amazonaws.com'
                    }
                }
            ]
        }

        expected_properties = {
            'name': 'stdf-alert-pipeline-${var.name}-slack',
            'path': '/',
            'assume_role_policy': json.dumps(expected_assume_role_policy, indent=2),
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_slack_lambda_role_policy(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_iam_role_policy'
        expected_resource_name = 'slack_lambda'

        expected_inline_role_policy = {
            'Version': '2012-10-17',
            'Statement': [
                {
                    'Effect': 'Allow',
                    'Action': [
                        'secretsmanager:GetSecretValue'
                    ],
                    'Resource': [
                        '${aws_secretsmanager_secret.slack_webhook.arn}'
                    ]
                }
            ]
        }

        expected_properties = {
            'name': 'stdf-alert-pipeline-${var.name}-slack',
            'role': 'aws_iam_role.slack_lambda.id',
            'policy': json.dumps(expected_inline_role_policy, indent=2),
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_slack_lambda_alarm(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_cloudwatch_metric_alarm'
        expected_resource_name = 'slack_lambda_alarm'

        expected_properties = {
            'alarm_name': 'stdf-alert-pipeline-${var.name}-slack-alarm',
            'alarm_description': 'STDF alert pipeline ${var.name} FAILED at the slack lambda!',
            'comparison_operator': 'GreaterThanOrEqualToThreshold',
            'evaluation_periods': '1',
            'metric_name': 'Errors',
            'namespace': 'AWS/Lambda',
            'dimensions': {
                'FunctionName': 'aws_lambda_function.slack_lambda.function_name'
            },
            'threshold': '1',
            'period': '60',
            'statistic': 'Sum',
            'treat_missing_data': 'missing',
            'insufficient_data_actions': [],
            'alarm_actions': ['var.fallback_sns'],
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_slack_webhook_secret(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_secretsmanager_secret'
        expected_resource_name = 'slack_webhook'

        expected_properties = {
            'name': 'stdf-alert-pipeline-${var.name}-slack-webhook',
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_basic_execution_slack(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_iam_role_policy_attachment'
        expected_resource_name = 'slack_lambda_basic_execution_role_policy'

        expected_properties = {
            'role': 'aws_iam_role.slack_lambda.name',
            'policy_arn': 'data.aws_iam_policy.basic_execution_role_policy.arn'
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)

    def test_basic_execution_converter(self):
        # Arrange
        expected_number_of_resources = 1
        expected_resource_type = 'aws_iam_role_policy_attachment'
        expected_resource_name = 'converter_lambda_basic_execution_role_policy'

        expected_properties = {
            'role': 'aws_iam_role.converter_lambda.name',
            'policy_arn': 'data.aws_iam_policy.basic_execution_role_policy.arn'
        }

        # Act
        actual_resources = self.get_resources_by_type_and_name(expected_resource_type, expected_resource_name)

        # Assert
        self.assertEqual(len(actual_resources.resource_list), expected_number_of_resources)
        self.assert_resources_match(actual_resources, expected_properties)
