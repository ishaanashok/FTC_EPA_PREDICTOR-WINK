const config = {
    ftcApi: {
        username: 'ishaanashok',
        key: '62C6B474-AE61-46FF-BBA7-DC513DC8E012',
        baseUrl: 'https://ftc-api.firstinspires.org/v2.0'
    },
    awsApi: {
        baseUrl: 'https://emgquhzu1f.execute-api.us-east-1.amazonaws.com/stage',
        endpoints: {
            teams: '/api/teams',
            events: '/api/events',
            matches: '/api/matches'
        }
    },
    currentSeason: 2024,
    defaultTournamentLevel: 'qual',
    pagination: {
        defaultPage: 1,
        pageSize: 25
    }
};

export default config;