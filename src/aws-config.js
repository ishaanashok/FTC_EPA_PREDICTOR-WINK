import { Amplify } from 'aws-amplify';
import { config } from './config';

const awsConfig = {
  Auth: {
    Cognito: {
      userPoolId: config.cognito.userPoolId,
      userPoolClientId: config.cognito.userPoolWebClientId,
      loginWith: {
        email: true,
        username: false
      },
      signUpVerificationMethod: 'code', // 'code' | 'link'
      userAttributes: {
        email: {
          required: true,
        },
      },
      allowGuestAccess: false,
      passwordFormat: {
        minLength: 8,
        requireLowercase: true,
        requireUppercase: true,
        requireNumbers: true,
        requireSpecialCharacters: true,
      },
    },
  },
};

Amplify.configure(awsConfig);

export default awsConfig;
