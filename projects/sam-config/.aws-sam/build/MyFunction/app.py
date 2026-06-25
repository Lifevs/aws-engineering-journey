import os
import json
import boto3

# Initialize the AppConfig Data client
appconfig = boto3.client('appconfigdata')

def lambda_handler(event, context):
    current_env = os.environ.get('APP_ENV', 'unknown')
    app_id = os.environ.get('APPCONFIG_APP_ID')
    env_id = os.environ.get('APPCONFIG_ENV_ID')
    profile_id = os.environ.get('APPCONFIG_PROFILE_ID')

    try:
        # 1. Start a configuration session
        session = appconfig.start_configuration_session(
            ApplicationIdentifier=app_id,
            EnvironmentIdentifier=env_id,
            ConfigurationProfileIdentifier=profile_id
        )

        # 2. Get the latest configuration using the token
        response = appconfig.get_latest_configuration(
            ConfigurationToken=session['InitialConfigurationToken']
        )

        # 3. Read and parse the JSON payload
        config_data = json.loads(response['Configuration'].read().decode('utf-8'))

        return {
            "statusCode": 200,
            "body": json.dumps({
                "environment": current_env,
                "feature_flags": config_data
            })
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }