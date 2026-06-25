import os
import json
import boto3
from botocore.exceptions import ClientError

appconfig = boto3.client('appconfigdata')

# 1. Define a safe, hardcoded fallback in case AppConfig dies
DEFAULT_FEATURE_FLAGS = {
    "new_payment_ui": False,
    "fallback_mode": True
}

def lambda_handler(event, context):
    current_env = os.environ.get('APP_ENV', 'unknown')
    app_id = os.environ.get('APPCONFIG_APP_ID')
    env_id = os.environ.get('APPCONFIG_ENV_ID')
    profile_id = os.environ.get('APPCONFIG_PROFILE_ID')

    feature_flags = DEFAULT_FEATURE_FLAGS

    try:
        session = appconfig.start_configuration_session(
            ApplicationIdentifier=app_id,
            EnvironmentIdentifier=env_id,
            ConfigurationProfileIdentifier=profile_id
        )

        response = appconfig.get_latest_configuration(
            ConfigurationToken=session['InitialConfigurationToken']
        )

        # 2. Only override the defaults if AppConfig succeeds AND returns data
        config_data = response['Configuration'].read().decode('utf-8')
        if config_data:
            feature_flags = json.loads(config_data)

    except ClientError as e:
        # 3. Catch the exact AWS error (e.g., ResourceNotFoundException)
        print(f"AppConfig error caught: {e.response['Error']['Code']}. Using default flags.")
    except Exception as e:
        # Catch any other unexpected parsing errors
        print(f"Unexpected error: {str(e)}. Using default flags.")

    # 4. The API ALWAYS returns a 200 Success, even if AppConfig is broken
    return {
        "statusCode": 200,
        "body": json.dumps({
            "environment": current_env,
            "feature_flags": feature_flags
        })
    }