import json
import http.client
import datetime
import os
import boto3

def error_if_not_exactly_one_record(event):
    number_of_records = len(event['Records'])
    if number_of_records != 1:
        raise Exception(
            f'Received SNS message with {number_of_records} records. This should never happen: AWS states all lambda SNS messages will always have exactly one record.')


def get_subject_and_message(event):
    subject = event['Records'][0]['Sns']['Subject']
    message = event['Records'][0]['Sns']['Message']
    return subject, message


def get_webhook():
    sm = boto3.client('secretsmanager')
    return json.loads(sm.get_secret_value(SecretId=os.environ['SLACK_WEBHOOK_SECRET_ID'])['SecretString'])


def get_zulu_timestamp(unix_time_milliseconds):
    return datetime.datetime.fromtimestamp(unix_time_milliseconds // 1000, tz=datetime.timezone(datetime.timedelta(0))).isoformat().replace('+00:00', 'Z')


def format_urls(urls):
    formatted_urls = ''
    first = True
    for url in urls:
        if first:
            first = False
        else:
            formatted_urls += ' - '
        formatted_urls += f"<{url['url']}|{url['text']}>"

    return formatted_urls


def format_stdf(stdf_message):
    stdf_parsed = json.loads(stdf_message)
    app_name = stdf_parsed['meta']['source']['app_name']
    alert_title = stdf_parsed['payload']['title']
    description = stdf_parsed['payload']['description']
    log_line = stdf_parsed['payload']['raw_data']
    provider = stdf_parsed['meta']['source']['provider']
    service_name = stdf_parsed['meta']['source']['service']
    account_id = stdf_parsed['meta']['source']['account_id']
    zulu_timestamp = get_zulu_timestamp(stdf_parsed['meta']['timestamp'])

    divider = {'type': 'divider'}
    header_section = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': f'*{app_name}*: *{alert_title}*'
        }
    }
    description_section = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': description
        }
    }
    log_line_section = {
        'type': 'section',
        'text': {
            'type': 'mrkdwn',
            'text': f'```{log_line}```'
        }
    }
    meta_section = {
        'type': 'section',
        'fields': [
            {
                'type': 'mrkdwn',
                'text': f'*Source:* {provider} {service_name}'
            },
            {
                'type': 'mrkdwn',
                'text': f'*Account id:* {account_id}'
            },
            {
                'type': 'mrkdwn',
                'text': f'*Timestamp*: {zulu_timestamp}'
            },
            {
                'type': 'mrkdwn',
                'text': '*Region:* us-east-1'
            }
        ]
    }
    blocks = [
        header_section,
        description_section,
        log_line_section,
        divider,
        meta_section,
        divider,
    ]

    urls = stdf_parsed['meta'].get('urls')
    if urls is not None:
        links = format_urls(urls)
        links_section = {
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': links
            }
        }
        blocks.append(links_section)

    event_id = stdf_parsed['meta']['source'].get('event_id')
    if event_id is not None:
        event_id_section = {
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': f'*Event id*: {event_id}'
                }
            ]
        }
        blocks.append(event_id_section)

    return {'blocks': blocks}


def format_fallback(message, fallback_reason):
    return {'text': f'{fallback_reason}. Failed to format the message. Using fallback mode!\n{message}'}


def post_to_slack(webhook, slack_message):
    dumped_message = json.dumps(slack_message)
    conn = http.client.HTTPSConnection(webhook['host'], 443)
    conn.request(
        'POST',
        webhook['path'],
        body=dumped_message,
        headers={
            'Content-Type': 'application/json'
        })

    status = conn.getresponse().status

    if status != http.HTTPStatus.OK:
        raise ValueError(f"Request to slack returned an error {status}")


def lambda_handler(event, context):
    error_if_not_exactly_one_record(event)
    subject, message = get_subject_and_message(event)
    webhook = get_webhook()

    if subject != 'stdfMessage' and not subject.startswith('stdf: '):
        fallback_slack_message = format_fallback(message, fallback_reason=subject)
        post_to_slack(webhook, fallback_slack_message)
        return

    try:
        slack_message = format_stdf(message)
        post_to_slack(webhook, slack_message)
        print("Message sent to Slack")
    except ValueError as error:
        fallback_slack_message = format_fallback(message, fallback_reason=str(error))
        post_to_slack(webhook, fallback_slack_message)
        print("Message sent to Slack in fallback mode")
