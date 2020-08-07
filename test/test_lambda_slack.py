import os
import unittest.mock
import importlib
import json
import http

lambda_function = importlib.import_module('lambda_slack.lambda_function')


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


class TestGetWebhook(unittest.TestCase):
    def setUp(self):
        os.environ.clear()
        importlib.reload(lambda_function)

    @unittest.mock.patch('boto3.client')
    def test_get_webhook(self, mock_boto3_client):
        # Arrange
        expected_service_name = 'secretsmanager'
        expected_webhook = {
            'host': 'hooks.slack.com',
            'path': '/services/00000000000/AAAAAAAAAa/XXXXXXXXXXX'
        }
        expected_webhook_dumped = json.dumps(expected_webhook)
        expected_slack_webhook_secret_id = 'the-webhook-stuff-lives-here'
        expected_secretsmanager_response = {
            'ARN': 'string',
            'Name': 'string',
            'VersionId': 'string',
            'SecretBinary': 'bytes',
            'SecretString': expected_webhook_dumped,
            'VersionStages': [
                'string',
            ],
            'CreatedDate': '13231312312'
        }

        os.environ['SLACK_WEBHOOK_SECRET_ID'] = expected_slack_webhook_secret_id

        mock_secretsmanager_client = mock_boto3_client.return_value
        mock_secretsmanager_client.get_secret_value.return_value = expected_secretsmanager_response

        # Act
        actual_webhook = lambda_function.get_webhook()

        # Assert
        self.assertEqual(actual_webhook, expected_webhook)
        mock_boto3_client.assert_called_once_with(expected_service_name)
        mock_secretsmanager_client.get_secret_value.assert_called_once_with(SecretId=expected_slack_webhook_secret_id)


class TestPostToSlack(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    @unittest.mock.patch('http.client')
    def test_post_to_slack(self, mock_http_client):
        # Arrange
        expected_https_port = 443
        expected_webhook_host = 'hooks.slack.com'
        expected_webhook_path = '/services/00000000000/AAAAAAAAAa/XXXXXXXXXXX'
        expected_headers = {
            'Content-Type': 'application/json'
        }
        expected_method = 'POST'
        expected_slack_message = {'bunch': 'of_slack_blocks'}
        expected_dumped_slack_message = json.dumps(expected_slack_message)

        expected_webhook = {
            'host': expected_webhook_host,
            'path': expected_webhook_path
        }

        mock_conn = mock_http_client.HTTPSConnection.return_value
        mock_conn.getresponse.return_value.status = http.HTTPStatus.OK

        # Act
        lambda_function.post_to_slack(expected_webhook, expected_slack_message)

        # Assert
        mock_http_client.HTTPSConnection.assert_called_once_with(expected_webhook_host, expected_https_port)
        mock_conn.request.assert_called_once_with(
            expected_method,
            expected_webhook_path,
            body=expected_dumped_slack_message,
            headers=expected_headers
        )

    @unittest.mock.patch('http.client')
    def test_post_to_slack_errored(self, mock_http_client):
        # Arrange
        expected_https_port = 443
        expected_webhook_host = "hooks.slack.com"
        expected_webhook_path = "/services/00000000000/AAAAAAAAAa/XXXXXXXXXXX"
        expected_headers = {
            'Content-Type': 'application/json'
        }
        expected_method = 'POST'
        expected_slack_message = {'bunch': 'of_slack_blocks'}
        expected_status = http.HTTPStatus.BAD_REQUEST
        expected_error = f"Request to slack returned an error {expected_status}"

        expected_webhook = {
            "host": expected_webhook_host,
            "path": expected_webhook_path
        }

        mock_conn = mock_http_client.HTTPSConnection.return_value
        mock_conn.getresponse.return_value.status = expected_status

        # Act
        with self.assertRaises(ValueError) as actual_exception_context:
            lambda_function.post_to_slack(expected_webhook, expected_slack_message)

        # Assert
        mock_http_client.HTTPSConnection.assert_called_once_with(expected_webhook_host, expected_https_port)
        mock_conn.request(expected_method, expected_webhook_path, expected_slack_message, expected_headers)
        self.assertIn(expected_error, str(actual_exception_context.exception))


class TestFormatUrls(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    def test_format_urls_singe_url(self):
        # Arrange
        expected_url_1 = {
            'url': 'http://example.com',
            'text': 'click this'
        }

        expected_urls = [expected_url_1]
        expected_formatted_urls = f"<{expected_url_1['url']}|{expected_url_1['text']}>"

        # Act
        actual_formatted_urls = lambda_function.format_urls(expected_urls)

        # Assert
        self.assertEqual(actual_formatted_urls, expected_formatted_urls)

    def test_format_urls_2_urls(self):
        # Arrange
        expected_url_1 = {
            'url': 'http://example.com',
            'text': 'click this'
        }
        expected_url_2 = {
            'url': 'http://corona.com',
            'text': 'virus'
        }

        expected_urls = [expected_url_1, expected_url_2]
        expected_formatted_urls = f"<{expected_url_1['url']}|{expected_url_1['text']}> - <{expected_url_2['url']}|{expected_url_2['text']}>"

        # Act
        actual_formatted_urls = lambda_function.format_urls(expected_urls)

        # Assert
        self.assertEqual(actual_formatted_urls, expected_formatted_urls)

    def test_format_urls_multi_urls(self):
        # Arrange
        expected_url_1 = {
            'url': 'http://example.com',
            'text': 'click this'
        }
        expected_url_2 = {
            'url': 'http://corona.com',
            'text': 'virus'
        }
        expected_url_3 = {
            'url': 'http://nintendo.com',
            'text': 'switch'
        }

        expected_urls = [expected_url_1, expected_url_2, expected_url_3]
        expected_formatted_urls = f"<{expected_url_1['url']}|{expected_url_1['text']}> - <{expected_url_2['url']}|{expected_url_2['text']}> - <{expected_url_3['url']}|{expected_url_3['text']}>"

        # Act
        actual_formatted_urls = lambda_function.format_urls(expected_urls)

        # Assert
        self.assertEqual(actual_formatted_urls, expected_formatted_urls)


class TestGetZuluTime(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    def test_get_zulu_timestamp(self):
        # Arrange
        expected_timestamp_milliseconds = 1582154420 * 1000
        expected_zulu_timestamp = '2020-02-19T23:20:20Z'

        # Act
        actual_zulu_timestamp = lambda_function.get_zulu_timestamp(expected_timestamp_milliseconds)

        # Assert
        self.assertEqual(actual_zulu_timestamp, expected_zulu_timestamp)


class TestFormatStdf(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    @unittest.mock.patch('lambda_slack.lambda_function.get_zulu_timestamp')
    @unittest.mock.patch('lambda_slack.lambda_function.format_urls')
    def test_format_stdf_happy_path(self, mock_format_urls, mock_get_zulu_timestamp):
        # Arrange
        expected_event_id = '000000000000000000000000000000000000000000000'
        expected_provider = 'AWS'
        expected_service_name = 'CloudWatch'
        expected_region = 'us-east-1'
        expected_account_id = '123456789012'
        expected_timestamp_zulu = '2020-02-20T02:20:20Z'
        mock_get_zulu_timestamp.return_value = expected_timestamp_zulu
        expected_timestamp_milliseconds = 1582154420 * 1000
        expected_log_line = '2020-03-26 08:36:27.000000000  0900 http_logs: {\'host\':\'10.112.250.161\',\'user\':null,\'method\':\'POST\',\'path\':\'/saml/SSO\',\'code\':302,\'size\':null,\'referer\':null,\'agent\':null}'

        expected_description = 'Something happened. A lot of things actually so this text is really long. This is a very detailed description innit.'
        expected_app_name = 'Jamf'
        expected_alert_title = 'BambooHR sync failed'

        expected_url_1 = {
            'url': 'http://example.com',
            'text': 'click this'
        }
        expected_url_2 = {
            'url': 'http://that.com',
            'text': 'click that'
        }

        expected_links = f"<{expected_url_1['url']}|{expected_url_1['text']}> - <{expected_url_2['url']}|{expected_url_2['text']}>"
        mock_format_urls.return_value = expected_links

        expected_formatted_message = {
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'*{expected_app_name}*: *{expected_alert_title}*'
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': expected_description
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'```{expected_log_line}```'
                    }
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'section',
                    'fields': [
                        {
                            'type': 'mrkdwn',
                            'text': f'*Source:* {expected_provider} {expected_service_name}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': f'*Account id:* {expected_account_id}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': f'*Timestamp*: {expected_timestamp_zulu}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': '*Region:* us-east-1'
                        }
                    ]
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': expected_links
                    }
                },
                {
                    'type': 'context',
                    'elements': [
                        {
                            'type': 'mrkdwn',
                            'text': f'*Event id*: {expected_event_id}'
                        }
                    ]
                }
            ]
        }

        expected_urls = [
            expected_url_1,
            expected_url_2
        ]

        expected_stdf_message = {
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
                    'service': expected_service_name,
                    'event_id': expected_event_id,
                    'app_name': expected_app_name
                },
                'urls': expected_urls
            },
            'stdf_version': 2,
        }

        expected_stdf_message_raw = json.dumps(expected_stdf_message)

        # Act
        actual_formatted_message = lambda_function.format_stdf(expected_stdf_message_raw)

        # Assert
        self.assertEqual(actual_formatted_message, expected_formatted_message)
        mock_format_urls.assert_called_once_with(expected_urls)
        mock_get_zulu_timestamp.assert_called_once_with(expected_timestamp_milliseconds)

    @unittest.mock.patch('lambda_slack.lambda_function.get_zulu_timestamp')
    @unittest.mock.patch('lambda_slack.lambda_function.format_urls')
    def test_format_stdf_no_urls_provided(self, mock_format_urls, mock_get_zulu_timestamp):
        # Arrange
        expected_event_id = '000000000000000000000000000000000000000000000'
        expected_provider = 'AWS'
        expected_service_name = 'CloudWatch'
        expected_region = 'us-east-1'
        expected_account_id = '123456789012'
        expected_timestamp_zulu = '2020-02-20T02:20:20Z'
        mock_get_zulu_timestamp.return_value = expected_timestamp_zulu
        expected_timestamp_milliseconds = 1582154420 * 1000
        expected_log_line = '2020-03-26 08:36:27.000000000  0900 http_logs: {\'host\':\'10.112.250.161\',\'user\':null,\'method\':\'POST\',\'path\':\'/saml/SSO\',\'code\':302,\'size\':null,\'referer\':null,\'agent\':null}'

        expected_description = 'Something happened. A lot of things actually so this text is really long. This is a very detailed description innit.'
        expected_app_name = 'Jamf'
        expected_alert_title = 'BambooHR sync failed'

        expected_formatted_message = {
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'*{expected_app_name}*: *{expected_alert_title}*'
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': expected_description
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'```{expected_log_line}```'
                    }
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'section',
                    'fields': [
                        {
                            'type': 'mrkdwn',
                            'text': f'*Source:* {expected_provider} {expected_service_name}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': f'*Account id:* {expected_account_id}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': f'*Timestamp*: {expected_timestamp_zulu}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': '*Region:* us-east-1'
                        }
                    ]
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'context',
                    'elements': [
                        {
                            'type': 'mrkdwn',
                            'text': f'*Event id*: {expected_event_id}'
                        }
                    ]
                }
            ]
        }

        expected_stdf_message = {
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
                    'service': expected_service_name,
                    'event_id': expected_event_id,
                    'app_name': expected_app_name
                },
            },
            'stdf_version': 2,
        }

        expected_stdf_message_raw = json.dumps(expected_stdf_message)

        # Act
        actual_formatted_message = lambda_function.format_stdf(expected_stdf_message_raw)

        # Assert
        self.assertEqual(actual_formatted_message, expected_formatted_message)
        mock_format_urls.assert_not_called()
        mock_get_zulu_timestamp.assert_called_once_with(expected_timestamp_milliseconds)

    @unittest.mock.patch('lambda_slack.lambda_function.get_zulu_timestamp')
    @unittest.mock.patch('lambda_slack.lambda_function.format_urls')
    def test_format_stdf_no_urls_no_event_id_provided(self, mock_format_urls, mock_get_zulu_timestamp):
        # Arrange
        expected_provider = 'AWS'
        expected_service_name = 'CloudWatch'
        expected_region = 'us-east-1'
        expected_account_id = '123456789012'
        expected_timestamp_zulu = '2020-02-20T02:20:20Z'
        mock_get_zulu_timestamp.return_value = expected_timestamp_zulu
        expected_timestamp_milliseconds = 1582154420 * 1000
        expected_log_line = '2020-03-26 08:36:27.000000000  0900 http_logs: {\'host\':\'10.112.250.161\',\'user\':null,\'method\':\'POST\',\'path\':\'/saml/SSO\',\'code\':302,\'size\':null,\'referer\':null,\'agent\':null}'

        expected_description = 'Something happened. A lot of things actually so this text is really long. This is a very detailed description innit.'
        expected_app_name = 'Jamf'
        expected_alert_title = 'BambooHR sync failed'

        expected_formatted_message = {
            'blocks': [
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'*{expected_app_name}*: *{expected_alert_title}*'
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': expected_description
                    }
                },
                {
                    'type': 'section',
                    'text': {
                        'type': 'mrkdwn',
                        'text': f'```{expected_log_line}```'
                    }
                },
                {
                    'type': 'divider'
                },
                {
                    'type': 'section',
                    'fields': [
                        {
                            'type': 'mrkdwn',
                            'text': f'*Source:* {expected_provider} {expected_service_name}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': f'*Account id:* {expected_account_id}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': f'*Timestamp*: {expected_timestamp_zulu}'
                        },
                        {
                            'type': 'mrkdwn',
                            'text': '*Region:* us-east-1'
                        }
                    ]
                },
                {
                    'type': 'divider'
                },
            ]
        }

        expected_stdf_message = {
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
                    'service': expected_service_name,
                    'app_name': expected_app_name
                },
            },
            'stdf_version': 2,
        }

        expected_stdf_message_raw = json.dumps(expected_stdf_message)

        # Act
        actual_formatted_message = lambda_function.format_stdf(expected_stdf_message_raw)

        # Assert
        self.assertEqual(actual_formatted_message, expected_formatted_message)
        mock_format_urls.assert_not_called()
        mock_get_zulu_timestamp.assert_called_once_with(expected_timestamp_milliseconds)


class TestFormatFallBack(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    def test_format_fallback(self):
        # Arrange
        expected_message = 'raw hardcore log message'
        expected_fallback_reason = 'parsing error'
        expected_text = f'{expected_fallback_reason}. Failed to format the message. Using fallback mode!\n{expected_message}'
        expected_fallback_message = {
            'text': expected_text
        }

        # Act
        actual_fallback_message = lambda_function.format_fallback(expected_message, expected_fallback_reason)

        # Assert
        self.assertEqual(actual_fallback_message, expected_fallback_message)


class TestLambdaHandler(unittest.TestCase):
    def setUp(self):
        importlib.reload(lambda_function)

    @unittest.mock.patch('lambda_slack.lambda_function.error_if_not_exactly_one_record')
    @unittest.mock.patch('lambda_slack.lambda_function.get_subject_and_message')
    @unittest.mock.patch('lambda_slack.lambda_function.get_webhook')
    @unittest.mock.patch('lambda_slack.lambda_function.format_stdf')
    @unittest.mock.patch('lambda_slack.lambda_function.format_fallback')
    @unittest.mock.patch('lambda_slack.lambda_function.post_to_slack')
    def test_handle_incoming_stdf(self, mock_post_to_slack, mock_format_fallback, mock_format_stdf, mock_get_webhook,
                                  mock_get_subject_and_message, mock_error_if_not_exactly_one_record):
        # Arrange
        expected_message = '{"a": "b"}'
        expected_subject = 'stdfMessage'
        expected_slack_message = 'slackmessage'
        expected_webhook = {
            'host': 'http://a.a',
            'path': '/a/b/c'
        }

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
        mock_get_webhook.return_value = expected_webhook
        mock_format_stdf.return_value = expected_slack_message

        # Act
        lambda_function.lambda_handler(expected_event, expected_context)

        # Assert
        mock_error_if_not_exactly_one_record.assert_called_once_with(expected_event)
        mock_get_subject_and_message.assert_called_once_with(expected_event)
        mock_get_webhook.assert_called_once()
        mock_format_stdf.assert_called_once_with(expected_message)
        mock_post_to_slack.assert_called_once_with(expected_webhook, expected_slack_message)
        mock_format_fallback.assert_not_called()

    @unittest.mock.patch('lambda_slack.lambda_function.error_if_not_exactly_one_record')
    @unittest.mock.patch('lambda_slack.lambda_function.get_subject_and_message')
    @unittest.mock.patch('lambda_slack.lambda_function.get_webhook')
    @unittest.mock.patch('lambda_slack.lambda_function.format_stdf')
    @unittest.mock.patch('lambda_slack.lambda_function.format_fallback')
    @unittest.mock.patch('lambda_slack.lambda_function.post_to_slack')
    def test_handle_incoming_stdf_extended(self, mock_post_to_slack, mock_format_fallback, mock_format_stdf, mock_get_webhook,
                                  mock_get_subject_and_message, mock_error_if_not_exactly_one_record):
        # Arrange
        expected_message = '{"a": "b"}'
        expected_subject = 'stdf: some alert happened!'
        expected_slack_message = 'slackmessage'
        expected_webhook = {
            'host': 'http://a.a',
            'path': '/a/b/c'
        }

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
        mock_get_webhook.return_value = expected_webhook
        mock_format_stdf.return_value = expected_slack_message

        # Act
        lambda_function.lambda_handler(expected_event, expected_context)

        # Assert
        mock_error_if_not_exactly_one_record.assert_called_once_with(expected_event)
        mock_get_subject_and_message.assert_called_once_with(expected_event)
        mock_get_webhook.assert_called_once()
        mock_format_stdf.assert_called_once_with(expected_message)
        mock_post_to_slack.assert_called_once_with(expected_webhook, expected_slack_message)
        mock_format_fallback.assert_not_called()


    @unittest.mock.patch('lambda_slack.lambda_function.error_if_not_exactly_one_record')
    @unittest.mock.patch('lambda_slack.lambda_function.get_subject_and_message')
    @unittest.mock.patch('lambda_slack.lambda_function.get_webhook')
    @unittest.mock.patch('lambda_slack.lambda_function.format_stdf')
    @unittest.mock.patch('lambda_slack.lambda_function.format_fallback')
    @unittest.mock.patch('lambda_slack.lambda_function.post_to_slack')
    def test_handle_incoming_unknown(self, mock_post_to_slack, mock_format_fallback, mock_format_stdf, mock_get_webhook,
                                     mock_get_subject_and_message, mock_error_if_not_exactly_one_record):
        # Arrange
        expected_message = '{"a": "b"}'
        expected_subject = 'unknownMessage'
        expected_slack_message = 'slackmessage'
        expected_slack_message_fallback = 'fallbackmessage'
        expected_webhook = {
            'host': 'http://a.a',
            'path': '/a/b/c'
        }

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
        mock_get_webhook.return_value = expected_webhook
        mock_format_stdf.return_value = expected_slack_message
        mock_format_fallback.return_value = expected_slack_message_fallback

        # Act
        lambda_function.lambda_handler(expected_event, expected_context)

        # Assert
        mock_error_if_not_exactly_one_record.assert_called_once_with(expected_event)
        mock_get_subject_and_message.assert_called_once_with(expected_event)
        mock_get_webhook.assert_called_once()
        mock_format_fallback.assert_called_once_with(expected_message, fallback_reason=expected_subject)
        mock_post_to_slack.assert_called_once_with(expected_webhook, expected_slack_message_fallback)
        mock_format_stdf.assert_not_called()

    @unittest.mock.patch('lambda_slack.lambda_function.error_if_not_exactly_one_record')
    @unittest.mock.patch('lambda_slack.lambda_function.get_subject_and_message')
    @unittest.mock.patch('lambda_slack.lambda_function.get_webhook')
    @unittest.mock.patch('lambda_slack.lambda_function.format_stdf')
    @unittest.mock.patch('lambda_slack.lambda_function.format_fallback')
    @unittest.mock.patch('lambda_slack.lambda_function.post_to_slack')
    def test_handle_incoming_postfailed(self, mock_post_to_slack, mock_format_fallback, mock_format_stdf,
                                        mock_get_webhook, mock_get_subject_and_message,
                                        mock_error_if_not_exactly_one_record):
        # Arrange
        expected_message = '{"a": "b"}'
        expected_subject = 'stdfMessage'
        expected_slack_message = 'slackmessage'
        expected_slack_message_fallback = 'fallbackmessage'
        expected_error = '403'
        expected_webhook = {
            'host': 'http://a.a',
            'path': '/a/b/c'
        }

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

        expected_post_to_slack_calls = [
            unittest.mock.call(expected_webhook, expected_slack_message),
            unittest.mock.call(expected_webhook, expected_slack_message_fallback)
        ]

        expected_post_to_slack_side_effect = [
            ValueError(expected_error),
            None
        ]

        mock_post_to_slack.side_effect = expected_post_to_slack_side_effect
        mock_get_subject_and_message.return_value = (expected_subject, expected_message)
        mock_get_webhook.return_value = expected_webhook
        mock_format_stdf.return_value = expected_slack_message
        mock_format_fallback.return_value = expected_slack_message_fallback

        # Act
        lambda_function.lambda_handler(expected_event, expected_context)

        # Assert
        mock_error_if_not_exactly_one_record.assert_called_once_with(expected_event)
        mock_get_subject_and_message.assert_called_once_with(expected_event)
        mock_get_webhook.assert_called_once()
        mock_format_stdf.assert_called_once_with(expected_message)
        mock_format_fallback.assert_called_once_with(expected_message, fallback_reason=expected_error)
        mock_post_to_slack.assert_has_calls(expected_post_to_slack_calls)
