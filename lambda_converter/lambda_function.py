import json
import boto3
import os
import logging
import datetime


def error_if_not_exactly_one_record(event):
    number_of_records = len(event['Records'])
    if (number_of_records != 1):
        raise Exception(
            f'Received SNS message with {number_of_records} records. This should never happen: AWS states all lambda SNS messages will always have exactly one record.')


def get_subject_and_message(event):
    subject = event['Records'][0]['Sns']['Subject']
    message = event['Records'][0]['Sns']['Message']
    return subject, message


def parse_metric_to_stdf(message):
    parsed_message = json.loads(message)
    aws_time_format = '%Y-%m-%dT%H:%M:%S.%f%z'
    timestamp = int(datetime.datetime.strptime(parsed_message['StateChangeTime'], aws_time_format).timestamp() * 1000)
    alarm_name = parsed_message['AlarmName']
    stdf_message = {
        'payload': {
            'title': alarm_name,
            'description': parsed_message['AlarmDescription'],
            'raw_data': parsed_message['NewStateReason']
        },
        'meta': {
            'timestamp': timestamp,
            'source': {
                'provider': 'AWS',
                'account_id': parsed_message['AWSAccountId'],
                'region': parsed_message['Region'],
                'service': 'CloudWatch',
                'app_name': 'Metric Alarm'
            },
            'urls': [{
                'url': f'https://console.aws.amazon.com/cloudwatch/home#alarmsV2:alarm/{alarm_name}',
                'text': 'Show alarm details'
            }]
        },
        'stdf_version': 2,
    }

    return json.dumps(stdf_message)


def post_stdf_string_to_sns(message):
    sns = boto3.client('sns')
    subject = f'stdf: {json.loads(message)["payload"]["title"]}'
    sns.publish(
        TopicArn=os.getenv('OUTGOING_SNS_TOPIC'),
        Subject=(subject[:88] + '[TRUNCATED]') if len(subject) > 99 else subject,
        Message=message
    )


def post_unrecognized_to_sns_and_warn(message, event):
    log = logging.getLogger('Unrecognized Message Format')
    log.warn(event)
    sns = boto3.client('sns')
    sns.publish(
        TopicArn=os.getenv('OUTGOING_SNS_TOPIC'),
        Subject='unrecognizedNonStdfMessage',
        Message=message
    )


def log_event(event):
    print(event)


def lambda_handler(event, context):
    log_event(event)
    error_if_not_exactly_one_record(event)
    subject, message = get_subject_and_message(event)

    try: 
        if subject == 'stdfMessage' or json.loads(message).get('message_type') == 'stdfMessage':
            post_stdf_string_to_sns(message)
        elif subject is not None and subject.startswith('ALARM: '):
            stdf_message = parse_metric_to_stdf(message)
            post_stdf_string_to_sns(stdf_message)
        else:
            post_unrecognized_to_sns_and_warn(message, event)
    except json.JSONDecodeError:
        post_unrecognized_to_sns_and_warn(message, event)
