import os
import unittest.mock
import importlib
import json

lambda_function = importlib.import_module('lambda_converter.lambda_function')


class TestGetSubjectAndMessage(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    def test_get_subject_and_message(self):
        # Arrange
        expected_message = '{"a": "b"}'
        expected_subject = 'stdfMessage'

        expected_event = {
            'Records': [
                {
                    'EventVersion': '1.0',
                    'EventSubscriptionArn': 'arn:aws:sns:us-east-2:123456789012:sns-lambda:21be56ed-a058-49f5-8c98-aedd2564c486',
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'SignatureVersion': '1',
                        'Timestamp': '2019-01-02T12:45:07.000Z',
                        'Signature': 'tcc6faL2yUC6dgZdmrwh1Y4cGa/ebXEkAi6RibDsvpi+tE/1+82j...65r==',
                        'SigningCertUrl': 'https://sns.us-east-2.amazonaws.com/SimpleNotificationService-ac565b8b1a6c5d002d285f9598aa1d9b.pem',
                        'MessageId': '95df01b4-ee98-5cb9-9903-4c221d41eb5e',
                        'Message': expected_message,
                        'MessageAttributes': {
                            'Test': {
                                'Type': 'String',
                                'Value': 'TestString'
                            },
                            'TestBinary': {
                                'Type': 'Binary',
                                'Value': 'TestBinary'
                            }
                        },
                        'Type': 'Notification',
                        'UnsubscribeUrl': 'https://sns.us-east-2.amazonaws.com/?Action=Unsubscribe&amp;SubscriptionArn=arn:aws:sns:us-east-2:123456789012:test-lambda:21be56ed-a058-49f5-8c98-aedd2564c486',
                        'TopicArn': 'arn:aws:sns:us-east-2:123456789012:sns-lambda',
                        'Subject': expected_subject
                    }
                }
            ]
        }

        # Act
        actual_subject, actual_message = lambda_function.get_subject_and_message(expected_event)

        # Assert
        self.assertEqual(actual_subject, expected_subject)
        self.assertEqual(actual_message, expected_message)


class TestErrorIfNotExactlyOneRecord(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    def test_error_on_two_records(self):
        # Arrange
        expected_number_of_records = 2
        expected_error = f'Received SNS message with {expected_number_of_records} records. This should never happen: AWS states all lambda SNS messages will always have exactly one record.'

        expected_event = {
            'Records': [
                'a',
                'b'
            ]
        }

        # Act
        with self.assertRaises(Exception) as actual_exception_context:
            lambda_function.error_if_not_exactly_one_record(expected_event)

        # Assert
        self.assertIn(expected_error, str(actual_exception_context.exception))

    def test_error_on_zero_records(self):
        # Arrange
        expected_number_of_records = 0
        expected_error = f'Received SNS message with {expected_number_of_records} records. This should never happen: AWS states all lambda SNS messages will always have exactly one record.'

        expected_event = {
            'Records': [
            ]
        }

        # Act
        with self.assertRaises(Exception) as actual_exception_context:
            lambda_function.error_if_not_exactly_one_record(expected_event)

        # Assert
        self.assertIn(expected_error, str(actual_exception_context.exception))

    def test_no_error_on_one_record(self):
        # Arrange
        expected_result = None

        expected_event = {
            'Records': [
                'a'
            ]
        }

        # Act
        actual_result = lambda_function.error_if_not_exactly_one_record(expected_event)

        # Assert
        self.assertEqual(actual_result, expected_result)


class TestParseMetricToStdf(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    def test_parse_metric_to_stdf(self):
        # Arrange
        expected_service_name = 'CloudWatch'
        expected_app_name = 'Metric Alarm'

        expected_alarm_name = 'Example alarm name'
        expected_description = 'Example alarm description.'
        expected_account_id = '000000000000'
        expected_region = 'EU - Ireland'
        expected_timestamp = '2017-01-12T16:30:42.236+0000'
        expected_timestamp_milliseconds = 1484238642236
        expected_log_line = 'Threshold Crossed: 1 datapoint (10.0) was greater than or equal to the threshold (1.0).'
        expected_provider = 'AWS'
        expected_message = {
            'AlarmName': expected_alarm_name,
            'AlarmDescription': expected_description,
            'AWSAccountId': expected_account_id,
            'NewStateValue': 'ALARM',
            'NewStateReason': expected_log_line,
            'StateChangeTime': expected_timestamp,
            'Region': expected_region,
            'OldStateValue': 'OK',
            'Trigger': {
                'MetricName': 'DeliveryErrors',
                'Namespace': 'ExampleNamespace',
                'Statistic': 'SUM',
                'Unit': 'null',
                'Dimensions': [],
                'Period': 300,
                'EvaluationPeriods': 1,
                'ComparisonOperator': 'GreaterThanOrEqualToThreshold',
                'Threshold': 1.0
            }
        }
        expected_message_string = json.dumps(expected_message)

        expected_urls = [{
            'url': f'https://console.aws.amazon.com/cloudwatch/home#alarmsV2:alarm/{expected_alarm_name}',
            'text': 'Show alarm details'
        }]

        expected_stdf_message = {
            'payload': {
                'title': expected_alarm_name,
                'description': expected_description,
                'raw_data': expected_log_line
            },
            'meta': {
                'timestamp': expected_timestamp_milliseconds,
                'source': {
                    'provider': expected_provider,
                    'account_id': expected_account_id,
                    'region': expected_region,
                    'service': expected_service_name,
                    'app_name': expected_app_name
                },
                'urls': expected_urls
            },
            'stdf_version': 2,
        }
        expected_stdf_string = json.dumps(expected_stdf_message)

        # Act
        actual_stdf_string = lambda_function.parse_metric_to_stdf(expected_message_string)

        # Assert
        self.assertEqual(actual_stdf_string, expected_stdf_string)


class TestPostStdfToSns(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    @unittest.mock.patch('lambda_converter.lambda_function.boto3.client')
    def test_post_stdf_string_to_sns(self, mock_boto3_client):
        # Arrange
        expected_service_name = 'sns'
        expected_provider = 'AWS'
        expected_stdf_service_name = 'CloudWatch'
        expected_region = 'us-east-1'
        expected_account_id = '123456789012'
        expected_timestamp_milliseconds = 1582154420 * 1000
        expected_log_line = '2020-03-26 08:36:27.000000000  0900 http_logs: {\'host\':\'10.112.250.161\',\'user\':null,\'method\':\'POST\',\'path\':\'/saml/SSO\',\'code\':302,\'size\':null,\'referer\':null,\'agent\':null}'

        expected_description = 'Something happened. A lot of things actually so this text is really long. This is a very detailed description innit.'
        expected_app_name = 'Jamf'
        expected_alert_title = 'BambooHR sync failed!!'

        expected_stdf_message_json = {
            'payload': {
                'title': expected_alert_title,
                'description': expected_description,
                'raw_data': expected_log_line
            },
            'meta': {
                'timestamp': expected_timestamp_milliseconds,
                'source': {
                    'provider': expected_provider,
                    'account_id': expected_account_id,
                    'region': expected_region,
                    'service': expected_stdf_service_name,
                    'app_name': expected_app_name
                },
            },
            'stdf_version': 2,
        }
        expected_stdf_message = json.dumps(expected_stdf_message_json)

        expected_sns_topic = 'topic_name'
        expected_outgoing_subject = f'stdf: {expected_alert_title}'

        os.environ['OUTGOING_SNS_TOPIC'] = expected_sns_topic
        mock_sns_client = mock_boto3_client.return_value

        # Act
        lambda_function.post_stdf_string_to_sns(expected_stdf_message)

        # Assert
        mock_boto3_client.assert_called_once_with(expected_service_name)
        mock_sns_client.publish.assert_called_once_with(
            TopicArn=expected_sns_topic,
            Subject=expected_outgoing_subject,
            Message=expected_stdf_message
        )

    @unittest.mock.patch('lambda_converter.lambda_function.boto3.client')
    def test_post_stdf_string_to_sns_long(self, mock_boto3_client):
        # Arrange
        expected_max_subject_length = 99
        expected_service_name = 'sns'
        expected_provider = 'AWS'
        expected_stdf_service_name = 'CloudWatch'
        expected_region = 'us-east-1'
        expected_account_id = '123456789012'
        expected_timestamp_milliseconds = 1582154420 * 1000
        expected_log_line = '2020-03-26 08:36:27.000000000  0900 http_logs: {\'host\':\'10.112.250.161\',\'user\':null,\'method\':\'POST\',\'path\':\'/saml/SSO\',\'code\':302,\'size\':null,\'referer\':null,\'agent\':null}'

        expected_description = 'Something happened. A lot of things actually so this text is really long. This is a very detailed description innit.'
        expected_app_name = 'Jamf'
        expected_alert_title = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
        expected_alert_subject = 'stdf: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa[TRUNCATED]'

        expected_stdf_message_json = {
            'payload': {
                'title': expected_alert_title,
                'description': expected_description,
                'raw_data': expected_log_line
            },
            'meta': {
                'timestamp': expected_timestamp_milliseconds,
                'source': {
                    'provider': expected_provider,
                    'account_id': expected_account_id,
                    'region': expected_region,
                    'service': expected_stdf_service_name,
                    'app_name': expected_app_name
                },
            },
            'stdf_version': 2,
        }
        expected_stdf_message = json.dumps(expected_stdf_message_json)
        expected_sns_topic = 'topic_name'
        expected_outgoing_subject = f'stdf: {expected_alert_title}'[:expected_max_subject_length]

        os.environ['OUTGOING_SNS_TOPIC'] = expected_sns_topic
        mock_sns_client = mock_boto3_client.return_value

        # Act
        lambda_function.post_stdf_string_to_sns(expected_stdf_message)

        # Assert
        mock_boto3_client.assert_called_once_with(expected_service_name)
        mock_sns_client.publish.assert_called_once_with(
            TopicArn=expected_sns_topic,
            Subject=expected_alert_subject,
            Message=expected_stdf_message
        )


class TestPostUnrecognizedToSns(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    @unittest.mock.patch('lambda_converter.lambda_function.boto3.client')
    @unittest.mock.patch('lambda_converter.lambda_function.logging')
    def test_post_unrecognized_to_sns_and_warn(self, mock_logging, mock_boto3_client):
        # Arrange
        expected_service_name = 'sns'
        expected_message = '{"foo": "bar"}'
        expected_sns_topic = 'topic_name'
        expected_event = {}

        os.environ['OUTGOING_SNS_TOPIC'] = expected_sns_topic
        mock_sns_client = mock_boto3_client.return_value

        expected_logger = 'Unrecognized Message Format'

        # Act
        lambda_function.post_unrecognized_to_sns_and_warn(expected_message, expected_event)

        # Assert
        mock_boto3_client.assert_called_once_with(expected_service_name)
        mock_sns_client.publish.assert_called_once_with(
            TopicArn=expected_sns_topic,
            Subject='unrecognizedNonStdfMessage',
            Message=expected_message
        )
        mock_logging.getLogger.assert_called_once_with(expected_logger)
        mock_logging.getLogger.return_value.warn.assert_called_once_with(expected_event)


class TestLambdaHandler(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    @unittest.mock.patch('lambda_converter.lambda_function.error_if_not_exactly_one_record')
    @unittest.mock.patch('lambda_converter.lambda_function.get_subject_and_message')
    @unittest.mock.patch('lambda_converter.lambda_function.post_stdf_string_to_sns')
    @unittest.mock.patch('lambda_converter.lambda_function.post_unrecognized_to_sns_and_warn')
    @unittest.mock.patch('lambda_converter.lambda_function.parse_metric_to_stdf')
    def test_handle_incoming_stdf(self, mock_parse_metric_to_stdf, mock_post_unrecognized_to_sns_and_warn, mock_post_stdf_string_to_sns,
                                  mock_get_subject_and_message, mock_error_if_not_exactly_one_record):
        # Arrange
        expected_message = '{"a": "b"}'
        expected_subject = 'stdfMessage'

        expected_context = {}

        expected_event = {
            'Records': [
                {
                    'EventVersion': '1.0',
                    'EventSubscriptionArn': 'arn:aws:sns:us-east-2:123456789012:sns-lambda:21be56ed-a058-49f5-8c98-aedd2564c486',
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'SignatureVersion': '1',
                        'Timestamp': '2019-01-02T12:45:07.000Z',
                        'Signature': 'tcc6faL2yUC6dgZdmrwh1Y4cGa/ebXEkAi6RibDsvpi+tE/1+82j...65r==',
                        'SigningCertUrl': 'https://sns.us-east-2.amazonaws.com/SimpleNotificationService-ac565b8b1a6c5d002d285f9598aa1d9b.pem',
                        'MessageId': '95df01b4-ee98-5cb9-9903-4c221d41eb5e',
                        'Message': expected_message,
                        'MessageAttributes': {
                            'Test': {
                                'Type': 'String',
                                'Value': 'TestString'
                            },
                            'TestBinary': {
                                'Type': 'Binary',
                                'Value': 'TestBinary'
                            }
                        },
                        'Type': 'Notification',
                        'UnsubscribeUrl': 'https://sns.us-east-2.amazonaws.com/?Action=Unsubscribe&amp;SubscriptionArn=arn:aws:sns:us-east-2:123456789012:test-lambda:21be56ed-a058-49f5-8c98-aedd2564c486',
                        'TopicArn': 'arn:aws:sns:us-east-2:123456789012:sns-lambda',
                        'Subject': expected_subject
                    }
                }
            ]
        }

        mock_get_subject_and_message.return_value = (expected_subject, expected_message)

        # Act
        lambda_function.lambda_handler(expected_event, expected_context)

        # Assert
        mock_error_if_not_exactly_one_record.assert_called_once_with(expected_event)
        mock_get_subject_and_message.assert_called_once_with(expected_event)
        mock_post_stdf_string_to_sns.assert_called_once_with(expected_message)
        mock_post_unrecognized_to_sns_and_warn.assert_not_called()
        mock_parse_metric_to_stdf.assert_not_called()

    @unittest.mock.patch('lambda_converter.lambda_function.error_if_not_exactly_one_record')
    @unittest.mock.patch('lambda_converter.lambda_function.get_subject_and_message')
    @unittest.mock.patch('lambda_converter.lambda_function.post_stdf_string_to_sns')
    @unittest.mock.patch('lambda_converter.lambda_function.post_unrecognized_to_sns_and_warn')
    @unittest.mock.patch('lambda_converter.lambda_function.parse_metric_to_stdf')
    def test_handle_incoming_metric_alarm(self, mock_parse_metric_to_stdf, mock_post_unrecognized_to_sns_and_warn, mock_post_stdf_string_to_sns,
                                  mock_get_subject_and_message, mock_error_if_not_exactly_one_record):
        # Arrange
        expected_subject = 'ALARM: "Example alarm name" in EU - Ireland'
        expected_context = {}
        expected_message = {
            'AlarmName': 'Example alarm name',
            'AlarmDescription': 'Example alarm description.',
            'AWSAccountId': '000000000000',
            'NewStateValue': 'ALARM',
            'NewStateReason': 'Threshold Crossed: 1 datapoint (10.0) was greater than or equal to the threshold (1.0).',
            'StateChangeTime': '2017-01-12T16:30:42.236+0000', 'Region': 'EU - Ireland', 'OldStateValue': 'OK',
            'Trigger': {
                'MetricName': 'DeliveryErrors',
                'Namespace': 'ExampleNamespace',
                'Statistic': 'SUM',
                'Unit': 'null',
                'Dimensions': [],
                'Period': 300,
                'EvaluationPeriods': 1,
                'ComparisonOperator': 'GreaterThanOrEqualToThreshold',
                'Threshold': 1.0
            }
        }
        expected_message_string = json.dumps(expected_message)
        expected_metric_alarm = {
            'Message': expected_message_string,
            'Subject': expected_subject
        }
        expected_event = {
            'Records': [
                {
                    'EventVersion': '1.0',
                    'EventSubscriptionArn': 'arn:aws:sns:us-east-2:123456789012:sns-lambda:21be56ed-a058-49f5-8c98-aedd2564c486',
                    'EventSource': 'aws:sns',
                    'Sns': expected_metric_alarm
                }
            ]
        }
        expected_stdf_message_string = '{"stdf": 2}'

        mock_get_subject_and_message.return_value = (expected_subject, expected_message_string)
        mock_parse_metric_to_stdf.return_value = expected_stdf_message_string

        # Act
        lambda_function.lambda_handler(expected_event, expected_context)

        # Assert
        mock_error_if_not_exactly_one_record.assert_called_once_with(expected_event)
        mock_get_subject_and_message.assert_called_once_with(expected_event)
        mock_post_stdf_string_to_sns.assert_called_once_with(expected_stdf_message_string)
        mock_parse_metric_to_stdf.assert_called_once_with(expected_message_string)
        mock_post_unrecognized_to_sns_and_warn.assert_not_called()

    @unittest.mock.patch('lambda_converter.lambda_function.error_if_not_exactly_one_record')
    @unittest.mock.patch('lambda_converter.lambda_function.get_subject_and_message')
    @unittest.mock.patch('lambda_converter.lambda_function.post_stdf_string_to_sns')
    @unittest.mock.patch('lambda_converter.lambda_function.post_unrecognized_to_sns_and_warn')
    @unittest.mock.patch('lambda_converter.lambda_function.parse_metric_to_stdf')
    def test_handle_incoming_unrecognized(self, mock_parse_metric_to_stdf, mock_post_unrecognized_to_sns_and_warn, mock_post_stdf_string_to_sns,
                                          mock_get_subject_and_message, mock_error_if_not_exactly_one_record):
        # Arrange
        expected_message = '{"a": "b"}'
        expected_subject = 'unrecognizedMessage'

        expected_context = {}

        expected_event = {
            'Records': [
                {
                    'EventVersion': '1.0',
                    'EventSubscriptionArn': 'arn:aws:sns:us-east-2:123456789012:sns-lambda:21be56ed-a058-49f5-8c98-aedd2564c486',
                    'EventSource': 'aws:sns',
                    'Sns': {
                        'SignatureVersion': '1',
                        'Timestamp': '2019-01-02T12:45:07.000Z',
                        'Signature': 'tcc6faL2yUC6dgZdmrwh1Y4cGa/ebXEkAi6RibDsvpi+tE/1+82j...65r==',
                        'SigningCertUrl': 'https://sns.us-east-2.amazonaws.com/SimpleNotificationService-ac565b8b1a6c5d002d285f9598aa1d9b.pem',
                        'MessageId': '95df01b4-ee98-5cb9-9903-4c221d41eb5e',
                        'Message': expected_message,
                        'MessageAttributes': {
                            'Test': {
                                'Type': 'String',
                                'Value': 'TestString'
                            },
                            'TestBinary': {
                                'Type': 'Binary',
                                'Value': 'TestBinary'
                            }
                        },
                        'Type': 'Notification',
                        'UnsubscribeUrl': 'https://sns.us-east-2.amazonaws.com/?Action=Unsubscribe&amp;SubscriptionArn=arn:aws:sns:us-east-2:123456789012:test-lambda:21be56ed-a058-49f5-8c98-aedd2564c486',
                        'TopicArn': 'arn:aws:sns:us-east-2:123456789012:sns-lambda',
                        'Subject': expected_subject
                    }
                }
            ]
        }

        mock_get_subject_and_message.return_value = (expected_subject, expected_message)

        # Act
        lambda_function.lambda_handler(expected_event, expected_context)

        # Assert
        mock_error_if_not_exactly_one_record.assert_called_once_with(expected_event)
        mock_get_subject_and_message.assert_called_once_with(expected_event)
        mock_post_unrecognized_to_sns_and_warn.assert_called_once_with(expected_message, expected_event)
        mock_post_stdf_string_to_sns.assert_not_called()
        mock_parse_metric_to_stdf.assert_not_called()
