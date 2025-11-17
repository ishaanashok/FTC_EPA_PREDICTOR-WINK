export const config = {
  // FTC API Configuration
  useAWSAPI: true,
  apiBaseUrl: 'https://irm64hxrp4.execute-api.us-east-1.amazonaws.com/stage',
  currentSeason: 2025,
  
  // AWS Cognito Configuration
  cognito: {
    userPoolId: 'us-east-1_Xc6eVYE2q',
    userPoolWebClientId: '5inga948jpumclbfe6083jv8o9',
    region: 'us-east-1'
  }
};
